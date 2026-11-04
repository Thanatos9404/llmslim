"""Edge cases of ``llmslim import`` over malformed, odd and hostile exports.

What tests/test_import_history.py covers is not repeated here. These probe the boundaries around it: a file cut at
every byte, records in the wrong shape, unusual roles, duplicated ids, encodings, a large file streamed, the dry run
and its files on disk, and credentials in every place they could leak (stored text, metadata, the report, progress
lines and errors). Every input is synthetic.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from llmslim.cli import main
from llmslim.memory import (
    HistoryImportError,
    ImportLimits,
    InMemoryStore,
    Memory,
    SQLiteStore,
    import_history,
)
from llmslim.memory import _import_reader as reader

UTC = timezone.utc


@pytest.fixture(autouse=True)
def _no_ambient_configuration(monkeypatch):
    for name in ("LLMSLIM_MEMORY_DB", "LLMSLIM_USER_ID", "LLMSLIM_AGENT_ID", "CLAUDE_CONFIG_DIR"):
        monkeypatch.delenv(name, raising=False)


def _key(*parts: str) -> str:
    """Joined at run time, so no credential-shaped literal sits in the source."""
    return "".join(parts)


SECRET = _key("sk-", "proj-", "Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0")
SECRET_TAIL = "Ij7Kl8Mn9Op0"


def _jsonl(path: Path, records, *, newline: str = "\n", bom: bool = False) -> Path:
    body = newline.join(json.dumps(r, ensure_ascii=False) for r in records) + newline
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8"))
    return path


def _message(node_id, parent, role, text, when=1700000000, **extra):
    message = {
        "id": node_id,
        "author": {"role": role},
        "create_time": when,
        "content": {"content_type": "text", "parts": [text]},
        "metadata": {},
        "recipient": "all",
    }
    message.update(extra)
    return {"id": node_id, "parent": parent, "children": [], "message": message}


def _chatgpt(nodes, *, cid="conv", title="T", current=None, create_time=1700000000):
    mapping = {"root": {"id": "root", "message": None, "parent": None, "children": []}}
    for node in nodes:
        mapping[node["id"]] = node
        mapping[node["parent"]]["children"].append(node["id"])
    conversation = {
        "conversation_id": cid,
        "title": title,
        "create_time": create_time,
        "mapping": mapping,
    }
    if current is not None:
        conversation["current_node"] = current
    return conversation


def _export(conversations, ascii_only=True) -> bytes:
    return json.dumps(conversations, ensure_ascii=ascii_only, indent=1).encode("utf-8")


def _contents(memory: Memory, user: str = "default"):
    return [item.content for item in memory.get_all(user_id=user)]


# --------------------------------------------------------------------------- a file cut short, anywhere


def _three_conversations():
    return [
        _chatgpt(
            [
                _message(f"u{k}", "root", "user", f"question {k} about pumpkins", 1700000000 + k),
                _message(f"a{k}", f"u{k}", "assistant", f"answer {k}: grow them", 1700000001 + k),
            ],
            cid=f"c{k}",
            title=f"title {k}",
            current=f"a{k}",
        )
        for k in range(3)
    ]


def test_an_export_cut_at_any_byte_keeps_the_complete_conversations(tmp_path):
    raw = _export(_three_conversations())
    path = tmp_path / "conversations.json"
    path.write_bytes(raw)
    full = Memory()
    import_history(path, full, format="chatgpt")
    everything = _contents(full)
    assert len(everything) == 6
    for cut in range(0, len(raw) + 1, 5):
        path.write_bytes(raw[:cut])
        memory = Memory()
        report = import_history(path, memory, format="chatgpt")
        assert report.ok, cut
        assert report.malformed <= 1, cut
        kept = _contents(memory)
        # Only whole conversations, and in their order: a prefix of the complete import.
        assert kept == everything[: len(kept)] and len(kept) % 2 == 0, cut


def test_a_jsonl_file_cut_at_any_byte_keeps_its_complete_lines(tmp_path):
    records = [{"role": "user", "content": f"line {k} with é and 日本"} for k in range(4)]
    raw = "".join(json.dumps(r) + "\n" for r in records).encode("utf-8")
    path = tmp_path / "cut.jsonl"
    for cut in range(len(raw) + 1):
        path.write_bytes(raw[:cut])
        memory = Memory()
        report = import_history(path, memory, format="jsonl")
        complete = raw[:cut].count(b"\n")
        assert report.ok and report.imported in (complete, complete + 1), cut
        assert report.malformed <= 1 and report.imported + report.malformed <= 4, cut
        assert _contents(memory) == [r["content"] for r in records][: report.imported], cut


@pytest.mark.parametrize("chunk", [1, 2, 3, 5, 8, 13])
def test_a_json_export_read_in_tiny_chunks_gives_the_same_turns(tmp_path, monkeypatch, chunk):
    # Multi-byte characters, escapes and quotes split across every chunk boundary.
    conversation = _chatgpt(
        [
            _message("u", "root", "user", 'Ünïcödé "quoted" \\ back\\slash 😀 日本語 \u200d\u0301'),
            _message("a", "u", "assistant", '{[not]} a "nest" ]]}} 🇮🇳 עברית العربية'),
        ],
        current="a",
    )
    raw = json.dumps([conversation, conversation | {"conversation_id": "c2"}], ensure_ascii=False)
    (tmp_path / "conversations.json").write_bytes(raw.encode("utf-8"))
    whole = Memory()
    import_history(tmp_path, whole, format="chatgpt")
    monkeypatch.setattr(reader, "_CHUNK", chunk)
    chunked = Memory()
    import_history(tmp_path, chunked, format="chatgpt")
    assert [(t.id, t.content) for t in chunked.get_all(user_id="default")] == [
        (t.id, t.content) for t in whole.get_all(user_id="default")
    ]
    assert len(_contents(whole)) == 4


# --------------------------------------------------------------------------- wrong shapes and roles


@pytest.mark.parametrize(
    "document",
    [
        "{}",  # an object, not a list of conversations
        '{"mapping": "not an object"}',
        '[1, "two", null, true, []]',
        '[{"title": "no mapping"}]',
        '[{"mapping": {"a": {"message": {"author": "nobody", "content": {}}}}}]',
    ],
)
def test_conversations_in_the_wrong_shape_are_counted_never_raised(tmp_path, document):
    (tmp_path / "conversations.json").write_text(document, encoding="utf-8")
    memory = Memory()
    report = import_history(tmp_path, memory, format="chatgpt")
    assert report.imported == 0 and report.ok
    assert report.malformed + sum(report.skipped.values()) >= 1 or report.sessions
    assert _contents(memory) == []


def test_chatgpt_roles_and_recipients_that_are_not_a_person_speaking(tmp_path):
    nodes = [
        _message("u", "root", "user", "what I asked"),
        _message("sys", "u", "system", "SYSTEM-PROMPT"),
        _message("crit", "sys", "critic", "CRITIC-NOTE"),
        _message("upper", "crit", "USER", "UPPERCASE-ROLE"),
        _message("call", "upper", "assistant", "print(1)", recipient="python"),
        _message("out", "call", "tool", "1"),
        _message("noauthor", "out", "user", "NO-AUTHOR"),
        _message("a", "noauthor", "assistant", "what it answered"),
    ]
    del nodes[6]["message"]["author"]
    (tmp_path / "conversations.json").write_text(
        json.dumps([_chatgpt(nodes, current="a")]), encoding="utf-8"
    )
    memory = Memory()
    report = import_history(tmp_path, memory, format="chatgpt")
    assert _contents(memory) == ["what I asked", "what it answered"]
    assert report.skipped["system"] == 1 and report.skipped["tool_output"] == 2
    assert report.skipped["unsupported"] == 2  # critic, USER
    assert report.malformed == 1  # the message with no author
    with_tools = Memory()
    import_history(tmp_path, with_tools, format="chatgpt", include_tool_output=True)
    assert _contents(with_tools) == [
        "what I asked",
        "[tool call] python: print(1)",
        "[tool result] 1",
        "what it answered",
    ]


def test_mem0_roles_other_than_assistant_are_the_users_and_bad_records_are_counted(tmp_path):
    memories = [
        {"id": "m1", "memory": "likes tea", "user_id": "asha", "role": "assistant"},
        {"id": "m2", "memory": "lives in Pune", "user_id": "asha", "role": "system"},
        {
            "id": "m3",
            "memory": "from metadata",
            "user_id": "asha",
            "metadata": {"role": "assistant"},
        },
        {"id": "m4", "memory": "odd role", "user_id": "asha", "role": ["a", "list"]},
        {"id": "m5", "memory": 42, "user_id": "asha"},  # not text
        {"id": "m6", "text": "text instead of memory", "user_id": "asha"},
        {"id": "m7", "memory": "   ", "user_id": "asha"},
        "a string, not a memory",
    ]
    path = tmp_path / "mem0.json"
    path.write_text(json.dumps({"results": memories, "count": 8}), encoding="utf-8")
    memory = Memory()
    report = import_history(path, memory, format="mem0")
    turns = {t.content: t.role for t in memory.get_all(user_id="asha")}
    assert turns == {
        "likes tea": "assistant",
        "lives in Pune": "user",
        "from metadata": "assistant",
        "odd role": "user",
        "text instead of memory": "user",
    }
    assert report.malformed == 2 and report.skipped["empty"] == 1


@pytest.mark.parametrize(
    "line",
    [
        "[1, 2]",
        '"just a string"',
        '{"role": "user"}',
        '{"role": "narrator", "content": "x"}',
        '{"role": 5, "content": "x"}',
        '{"role": "user", "content": 7}',
        '{"role": "user", "content": {"text": "x"}}',
        '{"role": "user", "content": "x", "timestamp": "not a time"}',
    ],
)
def test_jsonl_lines_in_the_wrong_shape(tmp_path, line):
    path = tmp_path / "odd.jsonl"
    path.write_text(line + "\n" + json.dumps({"role": "user", "content": "fine"}) + "\n")
    memory = Memory()
    report = import_history(path, memory, format="jsonl")
    assert report.ok and "fine" in _contents(memory)
    if "not a time" in line:  # an unreadable time is not malformed: it takes its neighbour's
        assert report.imported == 2 and report.malformed == 0
        assert import_history(path, Memory(), format="jsonl", strict=True).imported == 2
    else:
        assert report.imported == 1 and report.malformed == 1
        with pytest.raises(HistoryImportError, match="--strict"):
            import_history(path, Memory(), format="jsonl", strict=True)


# --------------------------------------------------------------------------- ids and idempotency


def test_a_source_id_said_twice_is_one_turn_and_scopes_keep_their_own(tmp_path):
    path = _jsonl(
        tmp_path / "dupes.jsonl",
        [
            {"role": "user", "content": "first wording", "id": "same", "session_id": "s1"},
            {"role": "user", "content": "second wording", "id": "same", "session_id": "s1"},
            {"role": "user", "content": "other session", "id": "same", "session_id": "s2"},
            {"role": "user", "content": "other user", "id": "same", "user_id": "bob"},
            {"role": "user", "content": "numeric id", "id": 7},
            {"role": "user", "content": "numeric id again", "id": 7},
        ],
    )
    memory = Memory()
    report = import_history(path, memory, format="jsonl")
    assert report.imported == 4 and report.duplicates == 2
    assert sorted(_contents(memory)) == ["first wording", "numeric id", "other session"]
    assert _contents(memory, "bob") == ["other user"]


def test_identical_lines_without_ids_are_each_kept_and_imported_once(tmp_path):
    same = {"role": "user", "content": "ok", "timestamp": "2026-01-01T00:00:00Z"}
    path = _jsonl(tmp_path / "same.jsonl", [same, same, same])
    db = str(tmp_path / "m.db")
    assert import_history(path, db, format="jsonl").imported == 3
    again = import_history(path, db, format="jsonl")
    assert again.imported == 0 and again.duplicates == 3
    # One more identical line is one more turn.
    _jsonl(path, [same, same, same, same])
    assert import_history(path, db, format="jsonl").imported == 1


def test_the_zip_its_folder_and_its_json_are_the_same_import(tmp_path):
    raw = _export(_three_conversations())
    folder = tmp_path / "export"
    folder.mkdir()
    (folder / "conversations.json").write_bytes(raw)
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("conversations.json", raw)
    db = str(tmp_path / "m.db")
    assert import_history(archive, db, format="chatgpt").imported == 6
    for source in (folder, folder / "conversations.json", archive):
        report = import_history(source, db, format="auto")
        assert report.format == "chatgpt" and report.imported == 0 and report.duplicates == 6
    assert import_history(archive, db, format="chatgpt", user_id="someone-else").imported == 6


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    st.lists(
        st.fixed_dictionaries(
            {
                "role": st.sampled_from(["user", "human", "assistant", "ai", "model", "USER"]),
                "content": st.text(
                    alphabet=st.characters(blacklist_categories=("Cs",)), min_size=0, max_size=40
                ),
            },
            optional={
                "id": st.one_of(st.integers(0, 5), st.sampled_from(["a", "b", "c"])),
                "session_id": st.sampled_from(["s1", "s2"]),
                "timestamp": st.one_of(
                    st.integers(-2_000_000_000, 4_000_000_000),
                    st.sampled_from(["2026-01-01T00:00:00Z", "2026-01-01T05:30:00+05:30", "x"]),
                ),
            },
        ),
        max_size=12,
    )
)
def test_any_jsonl_imports_verbatim_and_a_second_run_adds_nothing(tmp_path_factory, records):
    folder = tmp_path_factory.mktemp("prop")
    path = _jsonl(folder / "h.jsonl", records)
    memory = Memory(InMemoryStore())
    first = import_history(path, memory, format="jsonl", redact=False)
    stored = memory.get_all(user_id="default")
    assert first.imported == len(stored)
    # Every stored turn is exactly a line's content, and no line's text is stored twice under one source id.
    contents = [r["content"] for r in records if r["content"].strip()]
    assert sorted(t.content for t in stored) == sorted(c for _, c in _expected(records))
    assert all(t.content in contents for t in stored)
    second = import_history(path, memory, format="jsonl", redact=False)
    assert second.imported == 0 and second.duplicates == first.imported + first.duplicates


def _expected(records):
    """(identity, content) of each line the import keeps: the first line of each source id per session."""
    seen = set()
    counts: dict = {}
    for r in records:
        if not r["content"].strip():
            continue
        session = r.get("session_id")
        if "id" in r:
            identity = (session, "id", str(r["id"]))
        else:
            raw_time = "" if "timestamp" not in r else str(r["timestamp"])
            digest = (r["role"].lower(), raw_time, r["content"])
            counts[(session, digest)] = counts.get((session, digest), 0) + 1
            identity = (session, "content", digest, counts[(session, digest)])
        if identity in seen:
            continue
        seen.add(identity)
        yield identity, r["content"]


# --------------------------------------------------------------------------- encodings


def test_a_mem0_export_with_a_bom_and_crlf_and_a_claude_ai_export_with_both(tmp_path):
    mem0 = tmp_path / "mem0.json"
    body = json.dumps([{"id": "1", "memory": "likes tea", "user_id": "u"}], indent=1)
    mem0.write_bytes(b"\xef\xbb\xbf" + body.replace("\n", "\r\n").encode("utf-8"))
    memory = Memory()
    assert import_history(mem0, memory, format="auto").imported == 1
    claude = tmp_path / "claude"
    claude.mkdir()
    conversation = {
        "uuid": "conv-1",
        "name": "Tea",
        "created_at": "2026-01-01T00:00:00Z",
        "chat_messages": [
            {"uuid": "m1", "sender": "human", "text": "hello\r\nthere", "created_at": "2026-01-01"},
        ],
    }
    text = json.dumps([conversation], indent=2).replace("\n", "\r\n")
    (claude / "conversations.json").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    memory = Memory()
    assert import_history(claude, memory, format="auto").imported == 1
    assert _contents(memory) == ["hello\r\nthere"]  # the text's own line breaks are kept verbatim


def test_latin1_bytes_in_a_json_export_are_a_clear_error(tmp_path, capsys):
    path = tmp_path / "mem0.json"
    path.write_bytes(b'[{"id": "1", "memory": "caf\xe9", "user_id": "u"}]')
    with pytest.raises(HistoryImportError, match="not UTF-8"):
        import_history(path, Memory(), format="mem0")
    assert main(["import", "mem0", str(path), "--db", str(tmp_path / "m.db")]) == 1
    err = capsys.readouterr().err
    assert "not UTF-8" in err and "Traceback" not in err


@pytest.mark.parametrize("bom", ["utf-16-le", "utf-16-be"])
def test_utf16_mem0_and_claude_code_files_are_refused(tmp_path, bom):
    text = json.dumps([{"memory": "x"}])
    path = tmp_path / "mem0.json"
    path.write_bytes(("\ufeff" + text).encode(bom))
    with pytest.raises(HistoryImportError, match="UTF-16"):
        import_history(path, Memory(), format="mem0")
    transcript = tmp_path / "t.jsonl"
    transcript.write_bytes(("\ufeff" + json.dumps({"type": "user"}) + "\n").encode(bom))
    # A Claude Code transcript that can't be read is listed under errors, and the others are still read.
    report = import_history(transcript, Memory(), format="claude-code")
    assert not report.ok and "UTF-16" in report.errors[0]


def test_nul_bytes_control_characters_and_mixed_newlines_are_stored_verbatim(tmp_path):
    odd = "a\x00b\x01c\r\nd\re\nf\u2028g\u2029h\x7f\u200b\ufeffi"
    path = _jsonl(tmp_path / "odd.jsonl", [{"role": "user", "content": odd}])
    db = str(tmp_path / "m.db")
    assert import_history(path, db, format="jsonl").imported == 1
    assert _contents(Memory(db)) == [odd]


# --------------------------------------------------------------------------- size


def test_a_large_jsonl_file_streams_and_imports_again_as_nothing(tmp_path):
    turns = 12_000
    path = tmp_path / "big.jsonl"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for k in range(turns):
            record = {
                "role": "user" if k % 2 == 0 else "assistant",
                "content": f"turn {k}: " + "word " * 20,
                "session_id": f"s{k // 1000}",
                "timestamp": 1700000000 + k,
            }
            handle.write(json.dumps(record) + "\n")
    assert path.stat().st_size > 1_500_000
    db = str(tmp_path / "big.db")
    report = import_history(path, db, format="jsonl")
    assert report.imported == turns and len(report.sessions) == 12 and report.ok
    again = import_history(path, db, format="jsonl")
    assert again.imported == 0 and again.duplicates == turns
    memory = Memory(db)
    context = memory.search("turn 9876", user_id="default", budget=300)
    assert "turn 9876:" in context.text and context.tokens <= 300


def test_a_record_just_under_and_just_over_the_record_limit(tmp_path):
    limits = ImportLimits(max_record_bytes=200)
    under = json.dumps({"role": "user", "content": "u" * 150})
    over = json.dumps({"role": "user", "content": "o" * 250})
    path = tmp_path / "edge.jsonl"
    path.write_text(f"{under}\n{over}\n{under}\n", encoding="utf-8")
    report = import_history(path, Memory(), format="jsonl", limits=limits)
    # The second short line is the same text again, so it is a turn of its own (its occurrence is in its id).
    assert report.imported == 2 and report.skipped["too_large"] == 1


# --------------------------------------------------------------------------- the dry run


def test_a_dry_run_on_a_path_with_spaces_and_unicode_creates_nothing(tmp_path, capsys):
    source = _jsonl(tmp_path / "my history é.jsonl", [{"role": "user", "content": "hi"}])
    target = tmp_path / "new folder 日本 #1" / "mem ory%20.db"
    code = main(["import", "jsonl", str(source), "--db", str(target), "--dry-run", "--json"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True and report["imported"] == 1
    assert not target.parent.exists()


def test_a_dry_run_sees_writes_a_running_process_has_not_checkpointed(tmp_path):
    db = tmp_path / "busy.db"
    source = _jsonl(
        tmp_path / "h.jsonl", [{"role": "user", "content": f"line {k}"} for k in range(5)]
    )
    live = Memory(
        str(db)
    )  # stays open, as `llmslim mcp` would: the newest writes are in the -wal file
    import_history(source, live, format="jsonl")
    assert (tmp_path / "busy.db-wal").exists()

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    before = {name: digest(tmp_path / name) for name in ("busy.db", "busy.db-wal")}
    report = import_history(source, str(db), format="jsonl", dry_run=True)
    assert report.imported == 0 and report.duplicates == 5
    assert {name: digest(tmp_path / name) for name in before} == before
    live.store.close()


# --------------------------------------------------------------------------- credentials


def test_credentials_are_redacted_wherever_an_import_shows_or_stores_text(tmp_path, capsys):
    folder = tmp_path / "export"
    folder.mkdir()
    conversation = _chatgpt(
        [
            _message("u", "root", "user", f"my key is {SECRET} keep it"),
            _message("call", "u", "assistant", f"use {SECRET}", recipient="python"),
            _message("out", "call", "tool", f"echo {SECRET}"),
            _message("a", "out", "assistant", "done"),
        ],
        title=f"key {SECRET}",
        current="a",
    )
    (folder / "conversations.json").write_text(json.dumps([conversation]), encoding="utf-8")
    db = tmp_path / "m.db"
    # Progress lines (stderr) and the summary (stdout).
    args = ["import", "chatgpt", str(folder), "--db", str(db), "--include-tool-output"]
    assert main(args) == 0
    shown = capsys.readouterr()
    assert SECRET_TAIL not in shown.out + shown.err
    assert "openai-key" in shown.out
    # The JSON report of a dry run.
    assert main([*args, "--json", "--dry-run"]) == 0
    assert SECRET_TAIL not in capsys.readouterr().out
    # Everything stored: text and metadata.
    stored = Memory(str(db)).get_all(user_id="default")
    assert len(stored) == 4
    for item in stored:
        assert SECRET_TAIL not in item.content
        assert SECRET_TAIL not in json.dumps(dict(item.metadata))
    # And a --strict error names the record, not its text.
    path = _jsonl(tmp_path / "long.jsonl", [{"role": "user", "content": SECRET + " " + "x" * 300}])
    with pytest.raises(HistoryImportError) as raised:
        import_history(
            path, Memory(), format="jsonl", strict=True, limits=ImportLimits(max_turn_chars=100)
        )
    assert SECRET_TAIL not in str(raised.value)


def test_a_secret_split_across_content_parts_and_lines(tmp_path):
    path = _jsonl(
        tmp_path / "parts.jsonl",
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"first {SECRET}"},
                    {"type": "image_url", "image_url": {"url": "data:,"}},
                    {"type": "input_text", "text": "password: hunter2hunter2X9"},
                ],
            }
        ],
    )
    memory = Memory()
    report = import_history(path, memory, format="jsonl")
    (text,) = _contents(memory)
    assert SECRET_TAIL not in text and "hunter2hunter2X9" not in text
    assert report.redactions == {"openai-key": 1, "secret": 1}


# --------------------------------------------------------------------------- the command line


def test_cli_usage_errors_exit_2_and_json_output_is_one_document(tmp_path, capsys):
    source = _jsonl(tmp_path / "h.jsonl", [{"role": "user", "content": "hi"}])
    db = str(tmp_path / "m.db")
    for argv in (["--limit", "-1"], ["--since", "2026-13-45"], ["--until", ""]):
        with pytest.raises(SystemExit) as raised:
            main(["import", "jsonl", str(source), "--db", db, *argv])
        assert raised.value.code == 2, argv
    capsys.readouterr()
    assert main(["import", "jsonl", str(source), "--db", db, "--json"]) == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)  # one JSON document, nothing else on stdout
    assert report["imported"] == 1 and captured.err == ""


def test_an_import_into_a_store_that_rejects_writes_partway_can_be_run_again(tmp_path, monkeypatch):
    # A failure in the middle of a batch (the database went away): what was stored stays, nothing is half-stored,
    # and running the import again stores the rest exactly once.
    from llmslim.memory import _import

    monkeypatch.setattr(_import, "_BATCH", 10)
    records = [{"role": "user", "content": f"turn {k}", "id": f"t{k}"} for k in range(35)]
    path = _jsonl(tmp_path / "h.jsonl", records)
    store = InMemoryStore()
    real_add = store.add
    calls = {"n": 0}

    def flaky_add(items):
        calls["n"] += 1
        if calls["n"] >= 3:  # from the third write on, and for the turn-by-turn retry too
            raise ConnectionError("the database went away")
        real_add(items)

    monkeypatch.setattr(store, "add", flaky_add)
    with pytest.raises(HistoryImportError, match="went away"):
        import_history(path, Memory(store), format="jsonl")
    stored = len(Memory(store).get_all(user_id="default"))
    assert stored == 20  # two whole batches
    monkeypatch.setattr(store, "add", real_add)
    report = import_history(path, Memory(store), format="jsonl")
    assert report.imported == 15 and report.duplicates == 20
    assert sorted(_contents(Memory(store))) == sorted(r["content"] for r in records)


def test_since_and_until_compare_instants_not_text(tmp_path):
    path = _jsonl(
        tmp_path / "zones.jsonl",
        [
            {
                "role": "user",
                "content": "kolkata morning",
                "timestamp": "2026-01-01T05:00:00+05:30",
            },
            {"role": "user", "content": "utc midnight", "timestamp": "2025-12-31T23:30:00Z"},
            {
                "role": "user",
                "content": "new york evening",
                "timestamp": "2025-12-31T19:00:00-05:00",
            },
        ],
    )
    memory = Memory()
    report = import_history(
        path, memory, format="jsonl", since="2025-12-31T23:30:00Z", until="2026-01-01T00:00:00Z"
    )
    # All three are within [23:30, 00:00) UTC except "new york evening" (00:00 UTC, excluded).
    assert sorted(_contents(memory)) == ["kolkata morning", "utc midnight"]
    assert report.skipped["outside_window"] == 1
    times = sorted(t.created_at for t in memory.get_all(user_id="default"))
    assert times == [datetime(2025, 12, 31, 23, 30, tzinfo=UTC)] * 2


def test_auto_detection_on_an_ambiguous_or_empty_file(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")
    with pytest.raises(HistoryImportError, match="can't tell"):
        import_history(empty, Memory(), format="auto")
    both = tmp_path / "both.jsonl"
    # The first record that says what it is decides: here a JSONL turn, before a Mem0 memory.
    _jsonl(both, [{"x": 1}, {"role": "user", "content": "hi"}, {"memory": "fact"}])
    assert import_history(both, Memory(), format="auto").format == "jsonl"


def test_a_claude_code_folder_with_odd_files_beside_the_transcripts(tmp_path):
    project = tmp_path / "projects" / "-home-me-app"
    project.mkdir(parents=True)
    line = {
        "type": "user",
        "uuid": "u1",
        "sessionId": "s1",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"role": "user", "content": "what I said"},
    }
    (project / "s1.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")
    (project / "notes.txt").write_text("not a transcript", encoding="utf-8")
    (project / "empty.jsonl").write_bytes(b"")
    (project / "binary.jsonl").write_bytes(bytes(range(256)))
    (project / "s1").mkdir()  # a session's own folder (subagents): not a session
    (project / "s1" / "agent.jsonl").write_text(
        json.dumps({**line, "uuid": "u2", "message": {"role": "user", "content": "SUBAGENT"}})
        + "\n",
        encoding="utf-8",
    )
    memory = Memory()
    report = import_history(tmp_path, memory, format="claude-code")
    assert _contents(memory) == ["what I said"] and report.ok
    assert report.files == 3 and report.malformed >= 1


def test_a_zip_whose_conversations_json_is_in_a_folder_and_one_that_is_not_a_zip(tmp_path):
    raw = _export(_three_conversations())
    nested = tmp_path / "nested.zip"
    with zipfile.ZipFile(nested, "w") as zipped:
        zipped.writestr("export-2026/conversations.json", raw)
        zipped.writestr("export-2026/deeper/conversations.json", b"[]")
    assert import_history(nested, Memory(), format="chatgpt").imported == 6
    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"PK\x03\x04 but not really a zip")
    with pytest.raises(HistoryImportError, match="not a readable zip"):
        import_history(fake, Memory(), format="chatgpt")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr("other.json", b"[]")
    (tmp_path / "no-conversations.zip").write_bytes(buffer.getvalue())
    with pytest.raises(HistoryImportError, match="has no conversations.json"):
        import_history(tmp_path / "no-conversations.zip", Memory(), format="chatgpt")


def test_a_sqlite_target_that_is_not_writable_is_an_error_not_a_traceback(tmp_path, capsys):
    source = _jsonl(tmp_path / "h.jsonl", [{"role": "user", "content": "hi"}])
    folder_as_db = tmp_path / "a-folder.db"
    folder_as_db.mkdir()
    assert main(["import", "jsonl", str(source), "--db", str(folder_as_db)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("llmslim import: error:") and "Traceback" not in err
    store = SQLiteStore(tmp_path / "ok.db")
    store.close()
