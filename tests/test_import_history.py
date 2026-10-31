"""llmslim import / llmslim.memory.import_history: every format, the safety limits, idempotency and the CLI.

The fixtures in tests/fixtures/import are synthetic: made-up people, projects and conversations in the shapes Claude
Code transcripts, ChatGPT and Claude.ai data exports, Mem0 exports and generic JSONL have. No test reads a real home
folder: the ones that exercise ``~`` point HOME and USERPROFILE at a temporary folder first.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from llmslim.cli import main
from llmslim.memory import (
    HistoryImportError,
    ImportedSession,
    ImportLimits,
    ImportReport,
    InMemoryStore,
    Memory,
    Scope,
    SQLiteStore,
    import_history,
)
from llmslim.memory import _import_reader as reader
from llmslim.memory._import_sources import parse_time
from llmslim.memory._redact import redact
from llmslim.memory.compat import Mem0Memory

FIXTURES = Path(__file__).parent / "fixtures" / "import"
CLAUDE_CODE = FIXTURES / "claude-code"
CHATGPT = FIXTURES / "chatgpt"
CLAUDE_AI = FIXTURES / "claude-ai"
MEM0 = FIXTURES / "mem0" / "export.json"
GENERIC = FIXTURES / "jsonl" / "history.jsonl"
SESSION_1 = "11111111-1111-4111-8111-111111111111"
SESSION_2 = "22222222-2222-4222-8222-222222222222"
# Text in the fixtures that must never be imported by default.
NEVER = (
    "THINKING-MARKER",
    "COMPACT-SUMMARY-MARKER",
    "REMINDER-MARKER",
    "SUBAGENT-MARKER",
    "SIDECHAIN-MARKER",
    "ABANDONED-BRANCH-MARKER",
    "ABANDONED-REPLY-MARKER",
    "PROFILE-MARKER",
    "ATTACHMENT-MARKER",
)


@pytest.fixture(autouse=True)
def _no_ambient_configuration(monkeypatch):
    for name in ("LLMSLIM_MEMORY_DB", "LLMSLIM_USER_ID", "LLMSLIM_AGENT_ID", "CLAUDE_CONFIG_DIR"):
        monkeypatch.delenv(name, raising=False)


def _all(memory: Memory, user: str = "default"):
    return memory.get_all(user_id=user)


def _text(memory: Memory, user: str = "default") -> str:
    return "\n".join(item.content for item in _all(memory, user))


def _write_jsonl(path: Path, records, *, newline: str = "\n", bom: bool = False) -> Path:
    body = newline.join(json.dumps(r, ensure_ascii=False) for r in records) + newline
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8"))
    return path


def _cc_line(
    uuid: str,
    role: str,
    content,
    *,
    session: str = "s-1",
    ts: str = "2026-01-01T10:00:00Z",
    **extra,
):
    record = {
        "type": role,
        "uuid": uuid,
        "parentUuid": None,
        "sessionId": session,
        "timestamp": ts,
        "isSidechain": False,
        "message": {"role": role, "content": content},
    }
    if role == "assistant":
        record["message"]["id"] = extra.pop("message_id", f"msg-{uuid}")
    record.update(extra)
    return record


def _conversation(messages, *, cid="conv-x", current=None, title="T"):
    """A ChatGPT conversation from (node_id, parent, role, text, time) tuples."""
    mapping = {"root": {"id": "root", "message": None, "parent": None, "children": []}}
    for node_id, parent, role, text, when in messages:
        mapping[node_id] = {
            "id": node_id,
            "parent": parent,
            "children": [],
            "message": {
                "id": node_id,
                "author": {"role": role},
                "create_time": when,
                "content": {"content_type": "text", "parts": [text]},
                "metadata": {},
                "recipient": "all",
            },
        }
        mapping[parent]["children"].append(node_id)
    conversation = {
        "title": title,
        "create_time": 1700000000,
        "mapping": mapping,
        "conversation_id": cid,
    }
    if current is not None:
        conversation["current_node"] = current
    return conversation


# --------------------------------------------------------------------------- Claude Code


def test_claude_code_imports_what_the_user_and_assistant_said():
    memory = Memory()
    report = import_history(CLAUDE_CODE, memory, format="claude-code")
    assert report.format == "claude-code" and report.ok and not report.dry_run
    assert report.files == 2  # the subagent transcript in the session's folder is not a session
    assert report.imported == 7 and report.duplicates == 0 and report.malformed == 0
    assert report.skipped == {
        "attachment": 1,
        "meta": 8,
        "subagent": 1,
        "thinking": 1,
        "tool_output": 2,
    }
    turns = _all(memory)
    shop = [t for t in turns if t.run_id == f"claude-code:{SESSION_1}"]
    assert [t.role for t in shop] == ["user", "assistant", "assistant", "user", "assistant"]
    assert shop[0].content.startswith("Our staging database runs on port 6543")
    # A reply written as one line per content block is one turn, at its first block's time.
    assert shop[1].content == "I'll update the staging config to use port 6543."
    assert shop[1].created_at == datetime(2026, 3, 2, 9, 1, 5, 480000, tzinfo=timezone.utc)
    # The injected reminder is removed; the image beside the text is skipped.
    assert shop[3].content == "Also, staging deploys happen on Thursdays at 14:00 UTC."
    assert shop[0].metadata["project"] == "/home/dev/shop"
    assert shop[0].metadata["source"] == "claude-code"
    assert shop[0].metadata["source_id"] == "u-0003"
    text = _text(memory)
    for marker in (*NEVER, "TOOL-OUTPUT-MARKER", "API Error", "/clear", "interrupted"):
        assert marker not in text
    assert {s.session_id for s in report.sessions} == {SESSION_1, SESSION_2}


def test_claude_code_with_tool_output_imports_calls_and_results_as_tool_turns():
    memory = Memory()
    report = import_history(CLAUDE_CODE, memory, format="claude-code", include_tool_output=True)
    assert report.imported == 9
    assert "tool_output" not in report.skipped and report.skipped["thinking"] == 1
    tools = [t for t in _all(memory) if t.role == "tool"]
    assert tools[0].content.startswith("[tool call] Bash: ")
    assert '"command": "cat config/staging.yaml"' in tools[0].content
    assert tools[1].content.startswith("[tool result] db:")
    assert "TOOL-OUTPUT-MARKER" in tools[1].content
    assert "THINKING-MARKER" not in _text(memory)


def test_claude_code_shell_and_command_output_lines_are_tool_output(tmp_path):
    lines = [
        _cc_line("a", "user", "<bash-input>ls -la</bash-input>"),
        _cc_line(
            "b",
            "user",
            "<bash-stdout>\x1b[32mtotal 0\x1b[0m</bash-stdout><bash-stderr></bash-stderr>",
        ),
        _cc_line("c", "user", "<local-command-stdout>Set model to opus</local-command-stdout>"),
        _cc_line("d", "user", "<div>Real text that opens with markup</div>"),
    ]
    path = _write_jsonl(tmp_path / "s.jsonl", lines)
    plain = Memory()
    report = import_history(path, plain, format="claude-code")
    assert report.skipped["tool_output"] == 3
    assert _text(plain) == "<div>Real text that opens with markup</div>"
    tooled = Memory()
    import_history(path, tooled, format="claude-code", include_tool_output=True)
    contents = [t.content for t in _all(tooled) if t.role == "tool"]
    assert contents == [
        "[tool call] shell: ls -la",
        "[tool result] total 0",
        "[tool result] Set model to opus",
    ]


@pytest.mark.parametrize(
    "where",
    [
        lambda root: root,  # the Claude folder, with projects/ inside
        lambda root: root / "projects",
        lambda root: root / "projects" / "-home-dev-shop",
        lambda root: root / "projects" / "-home-dev-shop" / f"{SESSION_1}.jsonl",
    ],
)
def test_claude_code_reads_a_file_a_project_the_projects_folder_or_the_claude_folder(where):
    memory = Memory()
    report = import_history(where(CLAUDE_CODE), memory, format="claude-code")
    assert {t.run_id for t in _all(memory)} >= {f"claude-code:{SESSION_1}"}
    assert report.imported in (5, 7)


def test_claude_code_folder_without_transcripts_is_an_error(tmp_path):
    with pytest.raises(HistoryImportError, match="no Claude Code transcripts"):
        import_history(tmp_path, Memory(), format="claude-code")


def test_a_symlinked_claude_folder_works(tmp_path):
    real = tmp_path / "real-claude"
    shutil.copytree(CLAUDE_CODE, real)
    link = tmp_path / ".claude"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not let the test create a symbolic link")
    memory = Memory()
    assert import_history(link, memory, format="claude-code").imported == 7


def test_tilde_is_expanded_to_the_home_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    shutil.copytree(CLAUDE_CODE, tmp_path / ".claude")
    memory = Memory()
    report = import_history("~/.claude", memory, format="claude-code")
    assert report.imported == 7
    assert report.source == str(tmp_path / ".claude")


def test_the_cli_defaults_to_the_claude_folder_in_home(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    shutil.copytree(CLAUDE_CODE, home / ".claude")
    db = tmp_path / "memory.db"
    assert main(["import", "claude-code", "--db", str(db)]) == 0
    assert "7 imported" in capsys.readouterr().out
    elsewhere = tmp_path / "config"
    shutil.copytree(CLAUDE_CODE, elsewhere)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(elsewhere))
    assert main(["import", "claude-code", "--db", str(db)]) == 0
    assert "0 imported, 7 already there" in capsys.readouterr().out


def test_a_resumed_session_copied_into_a_new_file_is_not_imported_twice(tmp_path):
    source = CLAUDE_CODE / "projects" / "-home-dev-shop" / f"{SESSION_1}.jsonl"
    project = tmp_path / "projects" / "p"
    project.mkdir(parents=True)
    shutil.copy(source, project / "first.jsonl")
    shutil.copy(source, project / "second.jsonl")
    report = import_history(tmp_path, Memory(), format="claude-code")
    assert report.imported == 5 and report.duplicates == 5


# --------------------------------------------------------------------------- ChatGPT


def test_chatgpt_imports_the_visible_thread_from_current_node():
    memory = Memory()
    report = import_history(CHATGPT, memory, format="chatgpt")
    assert report.imported == 7
    assert report.skipped == {"other_branch": 2, "system": 2, "thinking": 1, "tool_output": 2}
    lisbon = [t for t in _all(memory) if t.run_id == "chatgpt:conv-0001"]
    assert [t.content for t in lisbon] == [
        "I'm planning a trip to Lisbon in May.",
        "Lisbon in May is lovely: mild and sunny.",
        "My budget for the Lisbon trip is 1200 euros.",
        "That is about 171 euros a day for a week.",
        "Here is the hotel I booked.",  # the image part beside it is skipped
    ]
    assert lisbon[0].created_at == datetime.fromtimestamp(1714550400, tz=timezone.utc)
    # No create_time: it takes the time of the turn before it, so the order holds.
    assert lisbon[4].created_at == lisbon[3].created_at
    assert lisbon[0].metadata["title"] == "Lisbon trip"
    text = _text(memory)
    for marker in (*NEVER, "TOOL-OUTPUT-MARKER", "print(1200"):
        assert marker not in text


def test_chatgpt_with_tool_output_keeps_code_and_its_result():
    memory = Memory()
    import_history(CHATGPT, memory, format="chatgpt", include_tool_output=True)
    tools = [t.content for t in _all(memory) if t.role == "tool"]
    assert tools == [
        "[tool call] python: print(1200 / 7)",
        "[tool result] 171.42857142857142 TOOL-OUTPUT-MARKER",
    ]


def test_chatgpt_branch_selection_follows_current_node_not_the_newest_child(tmp_path):
    conversation = _conversation(
        [
            ("u1", "root", "user", "first question", 1),
            ("a-old", "u1", "assistant", "the answer kept on screen", 2),
            ("a-new", "u1", "assistant", "a regenerated answer the user moved away from", 3),
        ],
        current="a-old",
    )
    (tmp_path / "conversations.json").write_text(json.dumps([conversation]), encoding="utf-8")
    memory = Memory()
    report = import_history(tmp_path, memory, format="chatgpt")
    assert _text(memory) == "first question\nthe answer kept on screen"
    assert report.skipped["other_branch"] == 1


def test_chatgpt_without_current_node_takes_the_newest_branch(tmp_path):
    conversation = _conversation(
        [
            ("u1", "root", "user", "hello", 1),
            ("a1", "u1", "assistant", "old reply", 2),
            ("a2", "u1", "assistant", "new reply", 3),
        ]
    )
    (tmp_path / "conversations.json").write_text(json.dumps([conversation]), encoding="utf-8")
    memory = Memory()
    import_history(tmp_path / "conversations.json", memory, format="chatgpt")
    assert _text(memory) == "hello\nnew reply"


def test_chatgpt_reads_the_export_zip_in_place(tmp_path):
    archive = tmp_path / "chatgpt-export.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(CHATGPT / "conversations.json", "export-2026/conversations.json")
        zf.writestr("export-2026/chat.html", "<html></html>")
        zf.writestr("export-2026/user.json", "{}")
    memory = Memory()
    report = import_history(archive, memory)  # format detected from the zip's contents
    assert report.format == "chatgpt" and report.imported == 7
    assert sorted(p.name for p in tmp_path.iterdir()) == ["chatgpt-export.zip"]  # nothing extracted


def test_chatgpt_reading_across_chunk_boundaries_gives_the_same_turns(monkeypatch):
    whole = Memory()
    import_history(CHATGPT, whole, format="chatgpt")
    monkeypatch.setattr(reader, "_CHUNK", 7)
    chunked = Memory()
    import_history(CHATGPT, chunked, format="chatgpt")
    assert [(t.id, t.content) for t in _all(chunked)] == [(t.id, t.content) for t in _all(whole)]


# --------------------------------------------------------------------------- Claude.ai


def test_claude_ai_imports_text_blocks_and_skips_thinking_tools_and_attachments():
    memory = Memory()
    report = import_history(CLAUDE_AI, memory, format="claude-ai")
    assert report.imported == 3
    assert report.skipped == {"attachment": 1, "thinking": 1, "tool_output": 2}
    turns = _all(memory)
    assert [t.role for t in turns] == ["user", "assistant", "user"]
    assert turns[1].content == "North-facing balconies get little direct sun; try cherry tomatoes."
    assert turns[2].content == "Thanks! Here is my soil test."  # an older export: text only
    # +05:30 and Z timestamps compare as instants.
    assert turns[2].created_at == datetime(2025, 4, 10, 8, 5, tzinfo=timezone.utc)
    assert turns[0].run_id == "claude-ai:ca-conv-1"
    assert "ATTACHMENT-MARKER" not in _text(memory) and "THINKING-MARKER" not in _text(memory)
    # An empty conversation adds no session.
    assert [s.session_id for s in report.sessions] == ["ca-conv-1"]


def test_claude_ai_follows_parent_uuids_to_the_newest_branch(tmp_path):
    root = "00000000-0000-4000-8000-000000000000"
    messages = [
        {
            "uuid": "m1",
            "parent_message_uuid": root,
            "sender": "human",
            "text": "Plan a menu.",
            "created_at": "2025-01-01T10:00:00Z",
        },
        {
            "uuid": "m2",
            "parent_message_uuid": "m1",
            "sender": "assistant",
            "text": "Old menu.",
            "created_at": "2025-01-01T10:00:05Z",
        },
        {
            "uuid": "m3",
            "parent_message_uuid": root,
            "sender": "human",
            "text": "Plan a vegan menu.",
            "created_at": "2025-01-01T10:01:00Z",
        },
        {
            "uuid": "m4",
            "parent_message_uuid": "m3",
            "sender": "assistant",
            "text": "Vegan menu.",
            "created_at": "2025-01-01T10:01:05Z",
        },
    ]
    (tmp_path / "conversations.json").write_text(
        json.dumps([{"uuid": "c", "name": "Menu", "chat_messages": messages}]), encoding="utf-8"
    )
    memory = Memory()
    report = import_history(tmp_path, memory, format="claude-ai")
    assert _text(memory) == "Plan a vegan menu.\nVegan menu."
    assert report.skipped["other_branch"] == 2


# --------------------------------------------------------------------------- Mem0


def test_mem0_export_keeps_each_memorys_scope_and_time():
    memory = Memory()
    report = import_history(MEM0, memory, format="mem0")
    assert report.imported == 3
    asha = _all(memory, "asha")
    assert [t.content for t in asha] == [
        "Is allergic to peanuts",
        "Prefers window seats on flights",
    ]
    assert asha[0].role == "user"
    assert asha[0].created_at == datetime(2025, 7, 20, 8, 26, 2, 374498, tzinfo=timezone.utc)
    assert asha[1].run_id == "trip-2025" and asha[0].run_id is None
    ravi = _all(memory, "ravi")
    assert ravi[0].agent_id == "career-coach"
    assert ravi[0].metadata["source_id"] == "9b1f6c0e-0000-4000-8000-000000000003"


@pytest.mark.parametrize(
    "shape",
    [
        lambda items: items,
        lambda items: {"results": items, "count": len(items), "next": None},
        lambda items: {"count": len(items), "memories": items},
    ],
)
def test_mem0_accepts_a_list_get_all_results_or_memories(tmp_path, shape):
    items = json.loads(MEM0.read_text(encoding="utf-8"))["results"]
    path = tmp_path / "mem0.json"
    path.write_text(json.dumps(shape(items)), encoding="utf-8")
    report = import_history(path, Memory())
    assert report.format == "mem0" and report.imported == 3


def test_mem0_as_jsonl(tmp_path):
    items = json.loads(MEM0.read_text(encoding="utf-8"))["results"]
    path = _write_jsonl(tmp_path / "mem0.jsonl", items)
    report = import_history(path, Memory(), format="mem0")
    assert report.imported == 3


def test_after_importing_a_mem0_export_the_mem0_facade_finds_it(tmp_path):
    db = tmp_path / "memory.db"
    import_history(MEM0, str(db), format="mem0")
    facade = Mem0Memory(str(db))
    hits = facade.search("What is Asha allergic to?", filters={"user_id": "asha"})
    assert any("peanuts" in hit["memory"] for hit in hits["results"])
    trip = facade.get_all(filters={"user_id": "asha", "run_id": "trip-2025"})
    assert [hit["memory"] for hit in trip["results"]] == ["Prefers window seats on flights"]


def test_a_fixed_user_id_overrides_the_ids_in_the_file():
    memory = Memory()
    import_history(MEM0, memory, format="mem0", user_id="me", agent_id="importer")
    turns = _all(memory, "me")
    assert len(turns) == 3 and {t.agent_id for t in turns} == {"importer"}
    assert not _all(memory, "asha")


# --------------------------------------------------------------------------- generic JSONL


def test_generic_jsonl_roles_sessions_and_content_parts():
    memory = Memory()
    report = import_history(GENERIC, memory, format="jsonl")
    assert report.imported == 4
    assert report.skipped == {"system": 1, "tool_output": 1}
    turns = _all(memory)
    assert [(t.run_id, t.role) for t in turns] == [
        ("s-1", "user"),
        ("s-1", "assistant"),
        ("s-2", "user"),
        ("s-2", "assistant"),
    ]
    assert turns[2].content == "I switched to the night shift in February."
    assert turns[2].created_at == datetime.fromtimestamp(1738576800, tz=timezone.utc)
    assert turns[3].created_at == turns[2].created_at  # no timestamp: the one before it


def test_generic_jsonl_per_line_user_ids_unless_one_is_fixed(tmp_path):
    path = _write_jsonl(
        tmp_path / "multi.jsonl",
        [
            {"role": "user", "content": "I am Lena.", "user_id": "lena"},
            {"role": "user", "content": "I am Omar.", "user_id": "omar"},
            {"role": "user", "content": "No user here."},
        ],
    )
    memory = Memory()
    import_history(path, memory, format="jsonl")
    assert _text(memory, "lena") == "I am Lena."
    assert _text(memory, "omar") == "I am Omar."
    assert _text(memory, "default") == "No user here."
    fixed = Memory()
    import_history(path, fixed, format="jsonl", user_id="me")
    assert len(_all(fixed, "me")) == 3


def test_a_folder_of_jsonl_files(tmp_path):
    _write_jsonl(tmp_path / "a.jsonl", [{"role": "user", "content": "from a"}])
    _write_jsonl(tmp_path / "b.jsonl", [{"role": "user", "content": "from b"}])
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    memory = Memory()
    report = import_history(tmp_path, memory, format="jsonl")
    assert report.files == 2 and _text(memory) in ("from a\nfrom b", "from b\nfrom a")


# --------------------------------------------------------------------------- hostile and broken input


def test_an_empty_file_imports_nothing_without_an_error(tmp_path):
    for name, fmt in (
        ("empty.jsonl", "jsonl"),
        ("conversations.json", "chatgpt"),
        ("e.json", "mem0"),
    ):
        path = tmp_path / name
        path.write_bytes(b"")
        report = import_history(path, Memory(), format=fmt)
        assert report.imported == 0 and report.malformed == 0 and report.ok


def test_a_truncated_last_line_is_counted_and_the_rest_imported(tmp_path):
    path = tmp_path / "cut.jsonl"
    path.write_text(
        json.dumps({"role": "user", "content": "complete line"})
        + "\n"
        + '{"role": "user", "content": "cut sh',
        encoding="utf-8",
    )
    memory = Memory()
    report = import_history(path, memory, format="jsonl")
    assert report.imported == 1 and report.malformed == 1
    assert _text(memory) == "complete line"


def test_a_truncated_export_keeps_the_complete_conversations(tmp_path):
    text = (CHATGPT / "conversations.json").read_text(encoding="utf-8")
    cut = text[: text.index('"title": "Keyboard"') + 30]
    (tmp_path / "conversations.json").write_text(cut, encoding="utf-8")
    memory = Memory()
    report = import_history(tmp_path, memory, format="chatgpt")
    assert len(report.sessions) == 1 and report.malformed == 1 and report.ok
    with pytest.raises(HistoryImportError, match="--strict"):
        import_history(tmp_path, Memory(), format="chatgpt", strict=True)


def test_bom_and_crlf_are_read(tmp_path):
    records = [
        {"role": "user", "content": "with a BOM"},
        {"role": "assistant", "content": "and CRLF"},
    ]
    path = _write_jsonl(tmp_path / "bom.jsonl", records, newline="\r\n", bom=True)
    memory = Memory()
    assert import_history(path, memory).imported == 2
    assert _text(memory) == "with a BOM\nand CRLF"
    export = tmp_path / "export"
    export.mkdir()
    (export / "conversations.json").write_bytes(
        b"\xef\xbb\xbf" + (CHATGPT / "conversations.json").read_bytes().replace(b"\n", b"\r\n")
    )
    assert import_history(export, Memory()).imported == 7


def test_utf16_is_refused_with_a_clear_message(tmp_path):
    path = tmp_path / "ps.jsonl"
    path.write_bytes(json.dumps({"role": "user", "content": "hi"}).encode("utf-16"))
    with pytest.raises(HistoryImportError, match="UTF-16"):
        import_history(path, Memory(), format="jsonl")
    doc = tmp_path / "conversations.json"
    doc.write_bytes("[]".encode("utf-16"))
    with pytest.raises(HistoryImportError, match="UTF-16"):
        import_history(doc, Memory(), format="chatgpt")


def test_invalid_utf8_in_a_line_is_malformed(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(
        b'{"role": "user", "content": "\xff\xfe"}\n{"role": "user", "content": "ok"}\n'
    )
    report = import_history(path, Memory(), format="jsonl")
    assert report.malformed == 1 and report.imported == 1


def test_a_huge_line_is_skipped_without_being_held(tmp_path):
    limits = ImportLimits(max_record_bytes=1000)
    path = tmp_path / "huge.jsonl"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"role": "user", "content": "before"}) + "\n")
        handle.write(json.dumps({"role": "user", "content": "x" * 50_000}) + "\n")
        handle.write(json.dumps({"role": "user", "content": "after"}) + "\n")
    memory = Memory()
    report = import_history(path, memory, format="jsonl", limits=limits)
    assert report.skipped["too_large"] == 1
    assert _text(memory) == "before\nafter"
    with pytest.raises(HistoryImportError, match="record limit"):
        import_history(path, Memory(), format="jsonl", limits=limits, strict=True)


def test_a_huge_conversation_in_an_export_is_skipped(tmp_path):
    small = _conversation([("u1", "root", "user", "short and kept", 1)], cid="small")
    big = _conversation([("u1", "root", "user", "y" * 20_000, 1)], cid="big")
    (tmp_path / "conversations.json").write_text(json.dumps([big, small]), encoding="utf-8")
    memory = Memory()
    report = import_history(
        tmp_path, memory, format="chatgpt", limits=ImportLimits(max_record_bytes=5000)
    )
    assert report.skipped["too_large"] == 1 and _text(memory) == "short and kept"


def test_a_turn_over_max_turn_chars_is_skipped(tmp_path):
    path = _write_jsonl(
        tmp_path / "t.jsonl",
        [{"role": "user", "content": "z" * 600}, {"role": "user", "content": "fits"}],
    )
    limits = ImportLimits(max_turn_chars=500)
    memory = Memory()
    report = import_history(path, memory, limits=limits)
    assert report.skipped["too_large"] == 1 and _text(memory) == "fits"
    assert report.sessions[0].skipped == 1
    with pytest.raises(HistoryImportError, match="max_turn_chars"):
        import_history(path, Memory(), limits=limits, strict=True)


def test_a_nesting_bomb_is_skipped_before_parsing(tmp_path):
    bomb = "[" * 200_000 + "]" * 200_000
    path = tmp_path / "bomb.jsonl"
    path.write_text(
        '{"role": "user", "content": "kept"}\n{"role": "user", "content": ' + bomb + "}\n",
        encoding="utf-8",
    )
    report = import_history(path, Memory(), format="jsonl")
    assert report.skipped["too_deep"] == 1 and report.imported == 1
    # The same as an element of an export, and as a whole document, with no RecursionError.
    doc = tmp_path / "conversations.json"
    doc.write_text(
        "[" + bomb + "," + json.dumps(_conversation([("u", "root", "user", "fine", 1)])) + "]",
        encoding="utf-8",
    )
    report = import_history(doc, Memory(), format="chatgpt")
    assert report.skipped["too_deep"] == 1 and report.imported == 1
    doc.write_text("[" * 300_000, encoding="utf-8")
    report = import_history(doc, Memory(), format="chatgpt")
    assert report.imported == 0 and report.skipped.get("too_deep", 0) + report.malformed >= 1


def test_nesting_inside_strings_does_not_count():
    deep_text = json.dumps({"content": "[[[[[[" * 100 + '\\"{{{{'})
    assert not reader.too_deep(deep_text, 4)
    assert reader.too_deep(json.dumps({"a": [[[[1]]]]}), 4)


def test_a_file_over_max_file_bytes_is_refused(tmp_path):
    path = _write_jsonl(tmp_path / "big.jsonl", [{"role": "user", "content": "x" * 5000}])
    with pytest.raises(HistoryImportError, match="file limit"):
        import_history(path, Memory(), limits=ImportLimits(max_file_bytes=1000))


def test_a_stream_that_grows_past_the_limit_while_read_stops():
    stream = reader.BoundedStream(io.BytesIO(b"a" * 100), "growing", 10)
    with pytest.raises(HistoryImportError, match="file limit"):
        stream.read(100)


def test_a_zip_bomb_is_refused(tmp_path):
    archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("conversations.json", b"[" + b" " * (20 << 20) + b"]")
    with pytest.raises(HistoryImportError, match="zip bomb"):
        import_history(archive, Memory(), format="chatgpt")


def test_a_zip_member_over_the_file_limit_is_refused(tmp_path):
    archive = tmp_path / "big.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("conversations.json", "[" + " " * 5000 + "]")
    with pytest.raises(HistoryImportError, match="file limit"):
        import_history(
            archive, Memory(), format="chatgpt", limits=ImportLimits(max_file_bytes=4000)
        )


@pytest.mark.parametrize(
    "name", ["../conversations.json", "/etc/passwd", "a/../../evil", "C:/Windows/x", "..\\evil"]
)
def test_zip_path_traversal_names_refuse_the_archive(tmp_path, name):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("conversations.json", "[]")
        zf.writestr(name, "pwned")
    with pytest.raises(HistoryImportError, match="unsafe entry name"):
        import_history(archive, Memory(), format="chatgpt")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["evil.zip"]


def test_a_zip_with_too_many_entries_or_without_conversations_is_refused(tmp_path):
    archive = tmp_path / "many.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for k in range(5):
            zf.writestr(f"f{k}.txt", "x")
    with pytest.raises(HistoryImportError, match="max_zip_members"):
        import_history(archive, Memory(), format="chatgpt", limits=ImportLimits(max_zip_members=3))
    with pytest.raises(HistoryImportError, match="has no conversations.json"):
        import_history(archive, Memory(), format="chatgpt")
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(HistoryImportError, match="not a readable zip"):
        import_history(broken, Memory(), format="chatgpt")


def test_a_damaged_or_encrypted_zip_entry_is_a_clear_error(tmp_path):
    damaged = tmp_path / "damaged.zip"
    with zipfile.ZipFile(damaged, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("conversations.json", "[" + json.dumps("x" * 200) + "]")
    data = bytearray(damaged.read_bytes())
    at = data.index(b"xxxx")
    data[at : at + 4] = b"yyyy"  # the stored bytes no longer match their CRC
    damaged.write_bytes(bytes(data))
    with pytest.raises(HistoryImportError, match="can't read"):
        import_history(damaged, Memory(), format="chatgpt")
    locked = tmp_path / "locked.zip"
    with zipfile.ZipFile(locked, "w") as zf:
        zf.writestr("conversations.json", "[]")
    data = bytearray(locked.read_bytes())
    data[data.index(b"PK\x01\x02") + 8] |= 0x1  # the "encrypted" bit of the central directory entry
    locked.write_bytes(bytes(data))
    with pytest.raises(HistoryImportError, match="encrypted"):
        import_history(locked, Memory(), format="chatgpt")


def test_unfamiliar_blocks_and_roles_are_skipped_and_counted(tmp_path):
    """Shapes a newer client may write: server tools, unknown block types, non-text content, unknown senders."""
    cc = _write_jsonl(
        tmp_path / "cc.jsonl",
        [
            _cc_line(
                "u", "user", ["not a block", {"type": "video"}, {"type": "text", "text": "   "}]
            ),
            _cc_line(
                "a",
                "assistant",
                [
                    "not a block",
                    {
                        "type": "server_tool_use",
                        "id": "srv_1",
                        "name": "web_search",
                        "input": {"query": "q"},
                    },
                    {
                        "type": "web_search_tool_result",
                        "tool_use_id": "srv_1",
                        "content": [{"type": "text", "text": "found"}],
                    },
                    {"type": "image", "source": {}},
                    {"type": "mystery"},
                    {"type": "text", "text": "first part"},
                ],
                message_id="msg-1",
            ),
            _cc_line(
                "b", "assistant", [{"type": "text", "text": "second part"}], message_id="msg-1"
            ),
            _cc_line(
                "c", "assistant", [{"type": "text", "text": "no message id"}], message_id=None
            ),
        ],
    )
    memory = Memory()
    report = import_history(cc, memory, format="claude-code", include_tool_output=True)
    assert report.skipped == {"attachment": 1, "unsupported": 4}
    contents = [t.content for t in _all(memory)]
    assert contents == [
        '[tool call] web_search: {"query": "q"}',
        "[tool result] found",
        "first part\n\nsecond part",  # one reply written over two lines
        "no message id",
    ]
    conversation = _conversation([("u1", "root", "user", "hello", 1)])
    mapping = conversation["mapping"]
    extra = {
        "w": {"author": {"role": "wizard"}, "content": {"content_type": "text", "parts": ["?"]}},
        "c": {
            "author": {"role": "user"},
            "content": {"content_type": "custom_widget", "parts": []},
        },
        "e": {"author": {"role": "assistant"}, "content": {"content_type": "text", "parts": [""]}},
        "t": {
            "author": {"role": "tool"},
            "content": {"content_type": "multimodal_text", "parts": []},
        },
        "v": {
            "author": {"role": "user"},
            "content": {
                "content_type": "multimodal_text",
                "parts": [{"content_type": "audio_transcription", "text": "spoken words"}],
            },
        },
        "x": {"author": "nobody", "content": "not a dict"},
    }
    parent = "u1"
    for node_id, message in extra.items():
        mapping[node_id] = {
            "id": node_id,
            "parent": parent,
            "children": [],
            "message": {"id": node_id, "create_time": None, **message},
        }
        mapping[parent]["children"].append(node_id)
        parent = node_id
    conversation["current_node"] = parent
    (tmp_path / "conversations.json").write_text(json.dumps([conversation]), encoding="utf-8")
    gpt = Memory()
    report = import_history(
        tmp_path / "conversations.json", gpt, format="chatgpt", include_tool_output=True
    )
    assert _text(gpt) == "hello\nspoken words"
    assert report.skipped == {"empty": 2, "unsupported": 2} and report.malformed == 1
    claude = tmp_path / "claude-ai.json"
    claude.write_text(
        json.dumps(
            [
                {
                    "uuid": "c",
                    "chat_messages": [
                        "not a message",
                        {"uuid": "m0", "sender": "system", "text": "?"},
                        {
                            "uuid": "m1",
                            "sender": "assistant",
                            "content": [
                                "not a block",
                                {"type": "tool_use", "name": "calc", "input": {"x": 1}},
                                {"type": "tool_result", "content": "2"},
                                {"type": "image"},
                                {"type": "mystery"},
                            ],
                        },
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    ai = Memory()
    report = import_history(claude, ai, format="claude-ai", include_tool_output=True)
    assert [t.content for t in _all(ai)] == ['[tool call] calc: {"x": 1}', "[tool result] 2"]
    assert report.malformed == 1
    assert report.skipped == {"attachment": 1, "empty": 1, "unsupported": 3}


def test_malformed_lines_are_counted_or_stop_a_strict_import(tmp_path):
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        "not json\n"
        + json.dumps(["a list, not an object"])
        + "\n"
        + json.dumps({"role": "wizard", "content": "unknown role"})
        + "\n"
        + json.dumps({"role": "user", "content": 42})
        + "\n"
        + json.dumps({"role": "user", "content": "good"})
        + "\n"
        + '{"role": "user", "content": "a huge number", "n": '
        + "1" * 100
        + "}\n",
        encoding="utf-8",
    )
    report = import_history(path, Memory(), format="jsonl")
    assert report.malformed == 5 and report.imported == 1
    with pytest.raises(HistoryImportError, match="line 1"):
        import_history(path, Memory(), format="jsonl", strict=True)


def test_records_in_the_wrong_shape_are_malformed(tmp_path):
    (tmp_path / "conversations.json").write_text(
        json.dumps([1, {"no": "mapping"}, []]), encoding="utf-8"
    )
    assert import_history(tmp_path, Memory(), format="chatgpt").malformed == 3
    assert import_history(tmp_path, Memory(), format="claude-ai").malformed == 3
    cc = _write_jsonl(
        tmp_path / "cc.jsonl",
        [["list"], {"type": "user"}, {"type": "user", "message": {"content": 5}}],
    )
    assert import_history(cc, Memory(), format="claude-code").malformed == 3
    mem0 = tmp_path / "m.json"
    mem0.write_text(json.dumps([{"id": "1"}, "text", {"memory": "   "}]), encoding="utf-8")
    report = import_history(mem0, Memory(), format="mem0")
    assert report.malformed == 2 and report.skipped["empty"] == 1


def test_a_document_that_is_not_json_is_an_error(tmp_path):
    (tmp_path / "conversations.json").write_text("hello", encoding="utf-8")
    with pytest.raises(HistoryImportError, match="not valid JSON"):
        import_history(tmp_path, Memory(), format="chatgpt")
    (tmp_path / "conversations.json").write_text('[{"mapping": {}} {"x": 1}]', encoding="utf-8")
    report = import_history(tmp_path, Memory(), format="chatgpt")
    assert report.errors and "expected ','" in report.errors[0]


def test_a_missing_path_is_an_error(tmp_path):
    for fmt in ("claude-code", "chatgpt", "claude-ai", "mem0", "jsonl", "auto"):
        with pytest.raises(HistoryImportError, match="does not exist|has no"):
            import_history(tmp_path / "nope", Memory(), format=fmt)


def test_one_unreadable_transcript_does_not_stop_the_others(tmp_path):
    project = tmp_path / "projects" / "p"
    project.mkdir(parents=True)
    _write_jsonl(project / "good.jsonl", [_cc_line("a", "user", "kept")])
    _write_jsonl(project / "big.jsonl", [_cc_line("b", "user", "x" * 5000)])
    memory = Memory()
    report = import_history(
        tmp_path, memory, format="claude-code", limits=ImportLimits(max_file_bytes=2000)
    )
    assert _text(memory) == "kept" and len(report.errors) == 1 and not report.ok
    with pytest.raises(HistoryImportError):
        import_history(
            tmp_path,
            Memory(),
            format="claude-code",
            limits=ImportLimits(max_file_bytes=2000),
            strict=True,
        )


# --------------------------------------------------------------------------- reading JSON in pieces


def _records(text: str, list_keys=(), **limits):
    stream = reader.BoundedStream(io.BytesIO(text.encode("utf-8")), "doc", 1 << 30)
    return list(reader.iter_document(stream, ImportLimits(**limits), list_keys))


def test_the_document_reader_handles_strings_scalars_and_objects(monkeypatch):
    monkeypatch.setattr(reader, "_CHUNK", 3)
    text = json.dumps(['a "quoted" [bracket] {brace} \\ back', 12, -3.5, True, None, {"k": ["v"]}])
    assert _records(text) == [
        ("ok", 'a "quoted" [bracket] {brace} \\ back'),
        ("ok", 12),
        ("ok", -3.5),
        ("ok", True),
        ("ok", None),
        ("ok", {"k": ["v"]}),
    ]
    assert _records('{"count": 2, "results": [1, 2], "next": null}', ("results",)) == [
        ("ok", 1),
        ("ok", 2),
    ]
    assert _records('{"title": "one conversation", "mapping": {}}') == [
        ("ok", {"title": "one conversation", "mapping": {}})
    ]
    assert _records("[]") == [] and _records("   ") == []
    assert _records("[1] trailing") == [("ok", 1), ("malformed", None)]
    assert _records("[1, 2") == [("ok", 1), ("ok", 2), ("malformed", None)]
    assert _records('{"a": "' + "x" * 50 + '"}', max_record_bytes=20) == [("too_large", None)]
    with pytest.raises(HistoryImportError, match="trailing comma"):
        _records("[1,]")
    with pytest.raises(HistoryImportError, match="member name"):
        _records("{1: 2}")


# --------------------------------------------------------------------------- idempotency


def test_importing_again_adds_nothing(tmp_path):
    db = tmp_path / "memory.db"
    for source, fmt in (
        (CLAUDE_CODE, "claude-code"),
        (CHATGPT, "chatgpt"),
        (CLAUDE_AI, "claude-ai"),
        (MEM0, "mem0"),
        (GENERIC, "jsonl"),
    ):
        first = import_history(source, str(db), format=fmt)
        again = import_history(source, str(db), format=fmt)
        assert first.imported > 0
        assert again.imported == 0 and again.duplicates == first.imported, fmt
    with sqlite3.connect(db) as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM llmslim_memory").fetchone()[0] == 7 + 7 + 3 + 3 + 4
        )


def test_only_new_lines_are_imported_when_a_file_grows(tmp_path):
    path = tmp_path / "log.jsonl"
    _write_jsonl(
        path,
        [
            {"role": "user", "content": "ok", "session_id": "s"},
            {"role": "assistant", "content": "ok", "session_id": "s"},
        ],
    )
    memory = Memory()
    assert import_history(path, memory).imported == 2
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"role": "user", "content": "ok", "session_id": "s"}) + "\n")
    report = import_history(path, memory)
    # Same text, same role, no ids: the third "ok" is a new turn, the first two are the ones stored before.
    assert report.imported == 1 and report.duplicates == 2


def test_the_same_history_for_two_users_is_stored_for_both(tmp_path):
    db = str(tmp_path / "memory.db")
    import_history(GENERIC, db, user_id="a")
    report = import_history(GENERIC, db, user_id="b")
    assert report.imported == 4 and report.duplicates == 0


def test_a_memory_a_store_or_a_path_can_receive_the_turns(tmp_path):
    store = InMemoryStore()
    assert import_history(GENERIC, store).imported == 4
    assert import_history(GENERIC, store).duplicates == 4
    nested = tmp_path / "a" / "b" / "memory.db"
    assert (
        import_history(GENERIC, nested).imported == 4
    )  # the folder is created, like llmslim mcp does
    with pytest.raises(TypeError, match="memory must be"):
        import_history(GENERIC, 42)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="dry_run"):
        import_history(GENERIC, None)


def test_a_turn_stored_by_a_concurrent_import_counts_as_a_duplicate():
    class Racing(InMemoryStore):
        """Fails the first batch as if another import stored one of its turns first."""

        def __init__(self) -> None:
            super().__init__()
            self.batches = 0

        def add(self, items):
            self.batches += 1
            if self.batches == 1:
                super().add(items[:1])
                raise ValueError("memory id already exists")
            super().add(items)

    store = Racing()
    report = import_history(GENERIC, store)
    assert report.imported + report.duplicates == 4 and report.duplicates == 1
    assert len(store.list(Scope(user_id="default"))) == 4


def test_a_store_that_cannot_write_is_a_clear_error():
    class Broken(InMemoryStore):
        def add(self, items):
            raise OSError("disk full")

    with pytest.raises(HistoryImportError, match="could not store"):
        import_history(GENERIC, Broken())


# --------------------------------------------------------------------------- time, text and options


def test_mixed_timezones_and_missing_timestamps(tmp_path):
    path = _write_jsonl(
        tmp_path / "tz.jsonl",
        [
            {"role": "user", "content": "first, no time", "session_id": "a"},
            {
                "role": "assistant",
                "content": "in India",
                "timestamp": "2025-03-01T15:30:00+05:30",
                "session_id": "a",
            },
            {
                "role": "user",
                "content": "in UTC",
                "timestamp": "2025-03-01T10:05:00Z",
                "session_id": "a",
            },
            {
                "role": "assistant",
                "content": "compact offset, 7 digits",
                "timestamp": "2025-03-01T03:10:00.1234567-0700",
                "session_id": "a",
            },
            {"role": "user", "content": "epoch ms", "timestamp": 1740823800000, "session_id": "a"},
            {
                "role": "user",
                "content": "naive means UTC",
                "timestamp": "2025-03-01 10:20:00",
                "session_id": "a",
            },
            {
                "role": "user",
                "content": "unreadable",
                "timestamp": "last Tuesday",
                "session_id": "a",
            },
            {"role": "user", "content": "a session with no time at all", "session_id": "b"},
        ],
    )
    before = datetime.now(timezone.utc)
    memory = Memory()
    import_history(path, memory)
    after = datetime.now(timezone.utc)
    by_text = {t.content: t.created_at for t in _all(memory)}
    utc = timezone.utc
    assert by_text["in India"] == datetime(2025, 3, 1, 10, 0, tzinfo=utc)
    assert by_text["first, no time"] == by_text["in India"]  # leading: the first known time
    assert by_text["in UTC"] == datetime(2025, 3, 1, 10, 5, tzinfo=utc)
    assert by_text["compact offset, 7 digits"] == datetime(
        2025, 3, 1, 10, 10, 0, 123456, tzinfo=utc
    )
    assert by_text["epoch ms"] == datetime(2025, 3, 1, 10, 10, tzinfo=utc)
    assert by_text["naive means UTC"] == datetime(2025, 3, 1, 10, 20, tzinfo=utc)
    assert by_text["unreadable"] == by_text["naive means UTC"]
    assert before <= by_text["a session with no time at all"] <= after


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2025-01-02T03:04:05Z", datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
        ("2025-01-02", datetime(2025, 1, 2, tzinfo=timezone.utc)),
        ("1735787045", datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
        (1735787045.5, datetime(2025, 1, 2, 3, 4, 5, 500000, tzinfo=timezone.utc)),
        (datetime(2025, 1, 2), datetime(2025, 1, 2, tzinfo=timezone.utc)),
        ("2025-01-02T03:04:05.1+0100", datetime(2025, 1, 2, 2, 4, 5, 100000, tzinfo=timezone.utc)),
        ("", None),
        ("nonsense", None),
        (True, None),
        (float("nan"), None),
        (1e30, None),
        ([2025], None),
        ("9" * 70, None),
    ],
)
def test_parse_time(value, expected):
    assert parse_time(value) == expected


def test_non_latin_text_is_kept_exactly_and_found():
    memory = Memory()
    import_history(CLAUDE_CODE, memory, format="claude-code")
    notes = [t for t in _all(memory) if t.run_id == f"claude-code:{SESSION_2}"]
    assert (
        notes[0].content == "मेरा पसंदीदा संपादक Helix है। Remember that my favourite editor is Helix."
    )
    assert notes[1].content.endswith("了解しました。")
    assert notes[0].created_at == datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc)
    context = memory.search("Which editor is my favourite?", user_id="default", budget=60)
    assert "Helix" in context.text


def test_dry_run_writes_nothing(tmp_path):
    missing = tmp_path / "sub" / "never.db"
    report = import_history(CLAUDE_CODE, str(missing), format="claude-code", dry_run=True)
    assert report.dry_run and report.imported == 7
    assert not missing.exists() and not missing.parent.exists()
    db = tmp_path / "memory.db"
    import_history(GENERIC, str(db))
    store = SQLiteStore(db)
    store.close()
    files_before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.iterdir()
        if p.is_file()
    }
    report = import_history(GENERIC, str(db), dry_run=True)
    assert report.imported == 0 and report.duplicates == 4
    report = import_history(CHATGPT, str(db), dry_run=True)
    assert report.imported == 7
    files_after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.iterdir()
        if p.is_file()
    }
    assert files_after == files_before
    memory = Memory()
    assert import_history(CHATGPT, memory, dry_run=True).imported == 7
    assert _all(memory) == []
    assert import_history(CHATGPT, None, dry_run=True).imported == 7


def test_dry_run_on_a_file_that_is_not_a_memory_is_an_error(tmp_path):
    other = tmp_path / "other.db"
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE t (x)")
    with pytest.raises(HistoryImportError, match="LLMSlim memory"):
        import_history(GENERIC, str(other), dry_run=True)


def test_since_and_until(tmp_path):
    memory = Memory()
    report = import_history(
        CLAUDE_CODE, memory, format="claude-code", since="2026-03-02T09:01:10Z", until="2026-03-05"
    )
    assert [t.content[:20] for t in _all(memory)] == [
        "Done: config/staging",
        "Also, staging deploy",
        "Noted: staging deplo",
    ]
    assert report.skipped["outside_window"] == 4
    with pytest.raises(ValueError, match="since must be"):
        import_history(CLAUDE_CODE, Memory(), format="claude-code", since="soon")
    epoch = Memory()
    import_history(GENERIC, epoch, since=datetime(2025, 2, 1, tzinfo=timezone.utc))
    assert len(_all(epoch)) == 2


def test_limit_stops_and_a_second_run_finishes(tmp_path):
    db = str(tmp_path / "memory.db")
    first = import_history(CHATGPT, db, limit=3)
    assert first.imported == 3 and first.limited
    second = import_history(CHATGPT, db)
    assert second.imported == 4 and second.duplicates == 3 and not second.limited
    exact = import_history(GENERIC, str(tmp_path / "other.db"), limit=4)
    assert exact.imported == 4 and not exact.limited
    with pytest.raises(ValueError, match="limit"):
        import_history(GENERIC, db, limit=0)


def test_round_trip_import_then_search_finds_the_fact():
    memory = Memory()
    import_history(CLAUDE_CODE, memory, format="claude-code")
    filler = [
        {
            "role": "user" if k % 2 == 0 else "assistant",
            "content": f"Unrelated chat number {k} about gardening, recipes and the weather in town.",
            "session_id": f"f{k // 10}",
            "timestamp": f"2026-02-{1 + k // 10:02d}T10:{k % 60:02d}:00Z",
        }
        for k in range(120)
    ]
    for record in filler:
        memory.add(
            [record], user_id="default", run_id=record["session_id"], timestamp=record["timestamp"]
        )
    context = memory.search(
        "What port does the staging database run on?", user_id="default", budget=150
    )
    assert context.compressed
    assert "6543" in context.text


def test_unknown_format_and_bad_ids():
    with pytest.raises(ValueError, match="format must be"):
        import_history(GENERIC, Memory(), format="slack")
    with pytest.raises(ValueError):
        import_history(GENERIC, Memory(), user_id="  ")


def test_limits_are_validated():
    with pytest.raises(ValueError, match="max_depth"):
        ImportLimits(max_depth=0)
    with pytest.raises(ValueError, match="max_file_bytes"):
        ImportLimits(max_file_bytes=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_zip_ratio"):
        ImportLimits(max_zip_ratio=1)


def test_the_report_and_progress_callback():
    seen = []
    report = import_history(CHATGPT, Memory(), on_session=seen.append)
    assert isinstance(report, ImportReport) and all(isinstance(s, ImportedSession) for s in seen)
    assert [s.session_id for s in seen] == ["conv-0001", "conv-0002"]
    data = report.to_dict()
    assert data["sessions"] == 2 and data["imported"] == 7 and data["skipped_total"] == 7
    assert data["session_details"][0]["title"] == "Lisbon trip"
    json.dumps(data)
    with pytest.raises(TypeError):
        report.skipped["new"] = 1  # type: ignore[index]


# --------------------------------------------------------------------------- auto-detection


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (CLAUDE_CODE, "claude-code"),
        (CLAUDE_CODE / "projects" / "-home-dev-shop" / f"{SESSION_1}.jsonl", "claude-code"),
        (CHATGPT, "chatgpt"),
        (CHATGPT / "conversations.json", "chatgpt"),
        (CLAUDE_AI, "claude-ai"),
        (MEM0, "mem0"),
        (GENERIC, "jsonl"),
        (GENERIC.parent, "jsonl"),
    ],
)
def test_auto_detects_the_format(path, expected):
    assert import_history(path, Memory(), dry_run=True).format == expected


def test_auto_detect_reads_claude_ai_exports_from_a_zip(tmp_path):
    archive = tmp_path / "data-2025.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(CLAUDE_AI / "conversations.json", "conversations.json")
        zf.writestr("users.json", "[]")
    assert import_history(archive, Memory()).format == "claude-ai"


def test_auto_detect_says_when_it_cannot_tell(tmp_path):
    path = tmp_path / "odd.json"
    path.write_text(json.dumps([{"hello": "world"}]), encoding="utf-8")
    with pytest.raises(HistoryImportError, match="can't tell the format"):
        import_history(path, Memory())
    folder = tmp_path / "folder"
    folder.mkdir()
    with pytest.raises(HistoryImportError):
        import_history(folder, Memory())


# --------------------------------------------------------------------------- redaction


def _key(*parts: str) -> str:
    """Joined at run time, so no credential-shaped literal sits in the source."""
    return "".join(parts)


@pytest.mark.parametrize(
    ("text", "kind", "gone"),
    [
        (f"my key is {_key('sk-', 'proj-', 'Ab3' * 10)} ok", "openai-key", _key("sk-", "proj-")),
        (f"use {_key('sk-ant-', 'api03-', 'Zz9' * 12)}", "anthropic-key", "api03"),
        (f"id {_key('AKIA', 'IOSFODNN7EXAMPLE')} here", "aws-access-key", "IOSFODNN7"),
        (
            f"aws_secret_access_key = {_key('wJalrXUtnFEMI/K7MDENG/', 'bPxRfiCYEXAMPLEKEY')}",
            "aws-secret-key",
            "bPxRfiCY",
        ),
        (
            _key(
                "-----BEGIN RSA ",
                "PRIVATE KEY-----\nMIIEow\nIBAAKC\n-----END RSA ",
                "PRIVATE KEY-----",
            ),
            "private-key",
            "MIIEow",
        ),
        (
            _key("-----BEGIN OPENSSH ", "PRIVATE KEY-----\nb3BlbnNzaA cut off"),
            "private-key",
            "b3BlbnNzaA",
        ),
        ("Authorization: Bearer abcdefghijklmnop1234567890", "bearer-token", "abcdefghijklmnop"),
        (f"token {_key('gh', 'p_', 'a1' * 18)}", "github-token", "a1a1a1"),
        (f"{_key('xo', 'xb-', '1234-5678-abcdefgh')}", "slack-token", "abcdefgh"),
        (f"{_key('AI', 'za', 'B' * 35)}", "google-api-key", "BBBBB"),
        (f"{_key('sk', '_live_', 'a1b2' * 6)}", "stripe-key", "a1b2a1b2"),
        (
            _key("eyJ", "hbGciOiJIUzI1", ".eyJ", "zdWIiOiIxMjM0", ".", "SflKxwRJSMeKKF2QT4"),
            "jwt",
            "SflKxw",
        ),
        ("postgresql://app:s3cretpass@db.example.com/prod", "url-password", "s3cretpass"),
        ('api_key = "abcd1234efgh5678"', "secret", "abcd1234efgh5678"),
        ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "basic-auth", "dXNlcjpw"),
    ],
)
def test_redaction_catches_obvious_credentials(text, kind, gone):
    redacted, found = redact(text)
    assert gone not in redacted
    assert f"[REDACTED:{kind}]" in redacted
    assert found[kind] >= 1


@pytest.mark.parametrize(
    "text",
    [
        "Please ask for the risk-assessment-framework-documentation",
        'api_key = os.environ["OPENAI_API_KEY"]',
        "password: is required",
        "max_tokens: 4096",
        "The sk-learn library and the task-runner-configuration-guidelines",
        "Bearer of bad news",
    ],
)
def test_redaction_leaves_ordinary_text_alone(text):
    assert redact(text) == (text, {})


def test_import_redacts_before_storing_and_counts_it(tmp_path):
    secret = _key("sk-", "proj-", "Q7x" * 10)
    path = _write_jsonl(
        tmp_path / "s.jsonl",
        [
            {"role": "user", "content": f"My OpenAI key is {secret}, keep it safe."},
            {"role": "assistant", "content": "Bearer abcdefghijklmnop1234567890 is a token too."},
        ],
    )
    memory = Memory()
    report = import_history(path, memory)
    assert secret not in _text(memory)
    assert "[REDACTED:openai-key]" in _text(memory)
    assert report.redactions == {"bearer-token": 1, "openai-key": 1}
    raw = Memory()
    assert import_history(path, raw, redact=False).redactions == {}
    assert secret in _text(raw)


def test_a_turn_that_is_only_a_secret_is_still_stored_redacted(tmp_path):
    path = _write_jsonl(
        tmp_path / "k.jsonl", [{"role": "user", "content": _key("sk-", "Ab1" * 10)}]
    )
    memory = Memory()
    import_history(path, memory)
    assert _text(memory) == "[REDACTED:openai-key]"


def test_titles_are_redacted_too(tmp_path):
    secret = _key("sk-", "Zz1" * 10)
    conversation = _conversation([("u1", "root", "user", "hi", 1)], title=f"key {secret}")
    (tmp_path / "conversations.json").write_text(json.dumps([conversation]), encoding="utf-8")
    memory = Memory()
    report = import_history(tmp_path, memory)
    assert secret not in report.sessions[0].title
    assert secret not in json.dumps(dict(_all(memory)[0].metadata))


# --------------------------------------------------------------------------- the command line


def test_cli_imports_and_prints_a_summary(tmp_path, capsys):
    db = tmp_path / "memory.db"
    assert main(["import", "auto", str(CHATGPT), "--db", str(db)]) == 0
    captured = capsys.readouterr()
    assert "Imported ChatGPT history" in captured.out
    assert "7 imported, 0 already there, 7 skipped" in captured.out
    assert "conv-0001 'Lisbon trip': 5 turns, 5 new" in captured.err
    assert main(["import", "chatgpt", str(CHATGPT), "--db", str(db), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["imported"] == 0 and data["duplicates"] == 7


def test_cli_options_reach_the_import(tmp_path, capsys, monkeypatch):
    db = tmp_path / "memory.db"
    monkeypatch.setenv("LLMSLIM_USER_ID", "from-env")
    code = main(
        [
            "import",
            "claude-code",
            str(CLAUDE_CODE),
            "--db",
            str(db),
            "--agent-id",
            "cc",
            "--since",
            "2026-03-02",
            "--until",
            "2026-03-04",
            "--limit",
            "2",
            "--include-tool-output",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "stopped at --limit" in out and "(user from-env)" in out
    memory = Memory(str(db))
    turns = memory.get_all(user_id="from-env", agent_id="cc")
    assert len(turns) == 2


def test_cli_dry_run_and_no_redact(tmp_path, capsys):
    db = tmp_path / "memory.db"
    path = _write_jsonl(
        tmp_path / "s.jsonl", [{"role": "user", "content": _key("sk-", "Ab1" * 10)}]
    )
    assert main(["import", "jsonl", str(path), "--db", str(db), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Would import" in out and "dry run: nothing was stored" in out and "redacted:" in out
    assert not db.exists()
    assert main(["import", "jsonl", str(path), "--db", str(db), "--no-redact"]) == 0
    assert _key("sk-", "Ab1" * 10) in _text(Memory(str(db)))


def test_cli_exit_codes(tmp_path, capsys):
    db = str(tmp_path / "memory.db")
    # 1: the input can't be imported.
    assert main(["import", "chatgpt", str(tmp_path / "missing.zip"), "--db", db]) == 1
    assert "does not exist" in capsys.readouterr().err
    bad = tmp_path / "bad.jsonl"
    bad.write_text("not json\n", encoding="utf-8")
    assert main(["import", "jsonl", str(bad), "--db", db]) == 0  # skipped and counted
    assert "malformed:   1" in capsys.readouterr().out
    assert main(["import", "jsonl", str(bad), "--db", db, "--strict"]) == 1
    odd = tmp_path / "odd.json"
    odd.write_text("[{}]", encoding="utf-8")
    assert main(["import", "auto", str(odd), "--db", db]) == 1
    assert "can't tell the format" in capsys.readouterr().err
    (tmp_path / "conversations.json").write_text('[{"mapping": {}} {"x": 1}]', encoding="utf-8")
    assert (
        main(["import", "chatgpt", str(tmp_path), "--db", db]) == 1
    )  # partial: listed as an error
    assert "error:" in capsys.readouterr().out
    # 2: a usage error.
    for argv in (
        ["import", "slack", str(GENERIC)],
        ["import", "chatgpt"],
        ["import", "jsonl", str(GENERIC), "--since", "whenever"],
        ["import", "jsonl", str(GENERIC), "--limit", "0"],
        ["import", "jsonl", str(GENERIC), "--limit", "many"],
    ):
        with pytest.raises(SystemExit) as raised:
            main([*argv, "--db", db])
        assert raised.value.code == 2, argv
    capsys.readouterr()


def test_cli_store_errors_are_reported_not_raised(tmp_path, capsys):
    not_a_db = tmp_path / "file.db"
    not_a_db.write_text("this is not a database", encoding="utf-8")
    assert main(["import", "jsonl", str(GENERIC), "--db", str(not_a_db)]) == 1
    assert "llmslim import: error:" in capsys.readouterr().err


def test_cli_output_survives_a_console_that_cannot_show_the_text(tmp_path, monkeypatch):
    conversation = _conversation([("u1", "root", "user", "नमस्ते", 1)], title="नमस्ते 你好")
    (tmp_path / "conversations.json").write_text(json.dumps([conversation]), encoding="utf-8")
    raw = io.BytesIO()
    narrow = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr("sys.stderr", narrow)
    monkeypatch.setattr("sys.stdout", narrow)
    assert main(["import", "chatgpt", str(tmp_path), "--db", str(tmp_path / "m.db")]) == 0
    narrow.flush()
    assert b"Imported ChatGPT" in raw.getvalue()


def test_cli_help_lists_the_formats(capsys):
    with pytest.raises(SystemExit):
        main(["import", "--help"])
    out = capsys.readouterr().out
    for name in (
        "claude-code",
        "chatgpt",
        "claude-ai",
        "mem0",
        "jsonl",
        "--include-tool-output",
        "--dry-run",
    ):
        assert name in out


def test_turn_times_are_kept_across_a_day_boundary_in_another_zone():
    memory = Memory()
    import_history(CLAUDE_AI, memory, format="claude-ai")
    times = [t.created_at for t in _all(memory)]
    assert times == sorted(times)
    assert times[-1] - times[0] == timedelta(minutes=5)
