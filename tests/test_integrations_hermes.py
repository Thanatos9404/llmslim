"""LLMSlimContextEngine against Hermes Agent's real ContextEngine ABC and plugin loader.

Skipped when Hermes Agent is not importable. Current Hermes is not installed from
PyPI, so point HERMES_AGENT_SRC at a Hermes checkout (with its dependencies
installed) to test against it; an installed hermes-agent works too. No model is
called.
"""

from __future__ import annotations

import copy
import importlib
import importlib.metadata
import json
import os
import sys
import textwrap

import pytest

if os.environ.get("HERMES_AGENT_SRC"):
    sys.path.insert(0, os.environ["HERMES_AGENT_SRC"])

context_engine = pytest.importorskip("agent.context_engine")
if not hasattr(context_engine, "ContextEngine"):  # pragma: no cover - an unrelated "agent" package.
    pytest.skip("agent.context_engine is not Hermes Agent's", allow_module_level=True)

from llmslim import count_tokens
from llmslim.integrations.hermes import CONFIG_KEYS, LLMSlimContextEngine, plugin_settings
from tests._history_corpus import FAILURE, NOTES, SYSTEM_PROMPT, TASK, make_log
from tests._integration_corpus import PreferringScorer

ContextEngine = context_engine.ContextEngine


def _call(call_id, command="pytest -q"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": "terminal", "arguments": json.dumps({"command": command})},
            }
        ],
    }


def _conversation():
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TASK},
        _call("c1"),
        {"role": "tool", "tool_call_id": "c1", "content": make_log(lines=400)},
        {"role": "assistant", "content": NOTES * 3},
        {"role": "user", "content": "Keep going."},
        _call("c2", "pytest -q tests/test_refund.py"),
        {"role": "tool", "tool_call_id": "c2", "content": make_log(lines=300)},
        {"role": "assistant", "content": "Switching refund.py to Decimal."},
        {"role": "user", "content": "Add the changelog entry too."},
        {"role": "assistant", "content": "Done; the entry is under Fixed."},
        {"role": "user", "content": "Thanks, now run everything once more."},
    ]


def _tokens(messages):
    return sum(count_tokens(m["content"]) for m in messages if isinstance(m["content"], str))


def _engine(context_length=8000, **kwargs):
    """An engine as Hermes sets it up: built by the plugin, then told the model's window."""
    kwargs.setdefault("protect_first_n", 1)
    kwargs.setdefault("protect_last_n", 4)
    engine = LLMSlimContextEngine(**kwargs)
    engine.update_model(model="test-model", context_length=context_length)
    return engine


def _tool_pairs(messages):
    calls = [c["id"] for m in messages for c in m.get("tool_calls") or []]
    results = [m["tool_call_id"] for m in messages if m["role"] == "tool"]
    return calls, results


def test_is_a_hermes_context_engine():
    engine = LLMSlimContextEngine()
    assert isinstance(engine, ContextEngine)
    assert engine.name == "llmslim"
    assert (engine.threshold_percent, engine.protect_first_n, engine.protect_last_n) == (0.75, 3, 6)


def test_usage_and_thresholds():
    engine = _engine()
    assert engine.context_length == 8000 and engine.threshold_tokens == 6000
    engine.update_from_response({"prompt_tokens": 6500, "completion_tokens": 20})
    assert engine.last_total_tokens == 6520
    assert engine.should_compress() and not engine.should_compress(100)
    engine.update_from_response({"prompt_tokens": "bad", "completion_tokens": None})
    assert engine.last_prompt_tokens == 0 and not engine.should_compress()
    assert engine.get_status()["context_length"] == 8000
    assert LLMSlimContextEngine(context_length=1000).threshold_tokens == 750


def test_compress_keeps_head_tail_and_tool_pairs():
    engine = _engine()
    messages = _conversation()
    before = copy.deepcopy(messages)
    assert engine.should_compress_preflight(messages)
    assert engine.has_content_to_compress(messages)
    out = engine.compress(messages, current_tokens=_tokens(messages) + 500)

    assert len(out) == len(messages)
    assert messages == before, "the input list and its dicts are not modified"
    # Head and tail are the very same objects: byte-identical for the prompt cache.
    assert out[0] is messages[0] and out[1] is messages[1]
    assert all(a is b for a, b in zip(out[-4:], messages[-4:]))
    # Tool calls and results stay paired; only text content changed.
    assert _tool_pairs(out) == _tool_pairs(messages)
    assert out[2] is messages[2]
    assert [m["role"] for m in out] == [m["role"] for m in messages]
    for i in (3, 7):
        assert count_tokens(out[i]["content"]) < count_tokens(messages[i]["content"])
        assert FAILURE in out[i]["content"]
    budget = int(8000 * engine.target_percent) - 500
    assert _tokens(out) <= budget
    assert engine.compression_count == 1
    assert engine.last_fit is not None and engine.last_fit.fits


def test_a_second_compaction_leaves_the_compacted_prefix_byte_identical():
    engine = _engine()
    first = engine.compress(_conversation())
    assert engine.compression_count == 1
    grown = first + [
        _call("c3", "pytest -q tests/test_invoice.py"),
        {"role": "tool", "tool_call_id": "c3", "content": make_log("invoice", 400)},
        {"role": "assistant", "content": NOTES * 4},
        {"role": "user", "content": "Ship it."},
        {"role": "assistant", "content": "Opening the pull request."},
        {"role": "user", "content": "Go."},
    ]
    # Room for the first compaction's output and the new turns once the new log is compressed.
    engine.target_percent = (_tokens(first) + count_tokens(NOTES * 4) + 600) / 8000
    second = engine.compress(grown)
    prefix = len(first)
    assert [json.dumps(m) for m in second[:prefix]] == [json.dumps(m) for m in first]
    assert count_tokens(second[prefix + 1]["content"]) < count_tokens(grown[prefix + 1]["content"])
    assert _tool_pairs(second) == _tool_pairs(grown)
    assert engine.compression_count == 2


def test_the_prefix_is_compressed_again_when_the_new_turns_are_not_enough():
    engine = _engine()
    first = engine.compress(_conversation())
    grown = first + [{"role": "user", "content": "One more thing."}]
    engine.target_percent = 0.6 * _tokens(first) / 8000
    second = engine.compress(grown)
    assert [json.dumps(m) for m in second[: len(first)]] != [json.dumps(m) for m in first]
    assert _tokens(second) < _tokens(first)
    assert engine.compression_count == 2


def test_focus_topic_is_the_query():
    scorer = PreferringScorer("decimal")
    engine = _engine(relevance=scorer)
    engine.compress(_conversation(), focus_topic="rounding with Decimal")
    assert scorer.calls


def test_multimodal_and_system_messages_are_left_alone():
    engine = _engine(protect_first_n=0, protect_last_n=1)
    image = [
        {"type": "text", "text": NOTES * 4},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": image},
        {"role": "system", "content": "Note: " + NOTES * 4},
        {"role": "tool", "tool_call_id": "x", "content": make_log(lines=300)},
        {"role": "user", "content": "Next."},
    ]
    out = engine.compress(messages)
    assert out[1] is messages[1] and out[2] is messages[2]
    assert out[3] is not messages[3]


def test_nothing_to_do():
    engine = _engine()
    short = _conversation()[:3]
    assert engine.compress(short) == short
    assert not engine.has_content_to_compress(short)
    assert LLMSlimContextEngine().compress(_conversation()) == _conversation()  # no context length


def test_engines_copy_and_reset():
    engine = _engine()
    engine.compress(_conversation())
    clone = copy.deepcopy(engine)  # Hermes gives every agent its own copy
    assert clone.compression_count == 1 and clone.context_length == 8000
    clone.on_session_reset()
    assert clone.compression_count == 0 and clone.last_fit is None
    assert engine.compression_count == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_percent": 0.8},
        {"target_percent": 0},
        {"threshold_percent": 1.5},
        {"protect_first_n": -1},
        {"protect_last_n": True},
        {"min_tokens": -1},
        {"relevance": "psychic"},
    ],
)
def test_invalid_options(kwargs):
    with pytest.raises(ValueError):
        LLMSlimContextEngine(**kwargs)


class _Context:
    def __init__(self, settings):
        self.settings = settings

    def get_config(self, key, default=None):
        return self.settings.get(key, default)


def test_plugin_settings_use_get_config_when_hermes_has_it():
    ctx = _Context({"target_percent": 0.4, "unrelated": 1})
    assert plugin_settings(ctx) == {"target_percent": 0.4}
    assert set(CONFIG_KEYS) >= {"target_percent", "protect_last_n"}


def _hermes_home(tmp_path, monkeypatch, plugin_id, settings):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "config.yaml").write_text(
        textwrap.dedent(
            f"""\
            plugins:
              enabled: [{plugin_id}]
              entries:
                {plugin_id}:
                  settings: {json.dumps(settings)}
            context:
              engine: llmslim
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def _discover():
    plugins = importlib.import_module("hermes_cli.plugins")
    plugins.discover_plugins(force=True)
    return plugins.get_plugin_context_engine()


def test_hermes_loads_the_entry_point_plugin(tmp_path, monkeypatch):
    if not any(
        ep.value == "llmslim.integrations.hermes"
        for ep in importlib.metadata.entry_points(group="hermes_agent.plugins")
    ):
        pytest.skip("llmslim is not installed as a distribution (no entry points)")
    pytest.importorskip("hermes_cli.plugins")
    _hermes_home(tmp_path, monkeypatch, "llmslim", {"target_percent": 0.4, "protect_last_n": 2})
    engine = _discover()
    assert isinstance(engine, LLMSlimContextEngine)
    assert engine.target_percent == 0.4 and engine.protect_last_n == 2


def test_hermes_loads_a_directory_plugin(tmp_path, monkeypatch):
    pytest.importorskip("hermes_cli.plugins")
    home = _hermes_home(tmp_path, monkeypatch, "llmslim-engine", {"protect_first_n": 1})
    plugin = home / "plugins" / "llmslim-engine"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text(
        "name: llmslim-engine\nversion: 1.0.0\ndescription: LLMSlim context engine\n",
        encoding="utf-8",
    )
    (plugin / "__init__.py").write_text(
        "from llmslim.integrations.hermes import register  # noqa: F401\n", encoding="utf-8"
    )
    engine = _discover()
    assert isinstance(engine, LLMSlimContextEngine)
    assert engine.protect_first_n == 1
