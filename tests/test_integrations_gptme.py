"""LLMSlimContextProvider with real gptme objects. Skipped when gptme is not installed.

No model is called: gptme's own rule-based compaction path is driven with a
conversation that has a large tool result.
"""

from __future__ import annotations

import importlib.metadata
from datetime import datetime, timedelta

import pytest

pytest.importorskip("gptme.tools.autocompact.context_provider")

from gptme.config import Config, ProjectConfig, UserConfig
from gptme.logmanager import LogManager
from gptme.message import Message
from gptme.tools.autocompact import context_provider as gptme_providers
from gptme.tools.autocompact import hook as gptme_hook
from gptme.tools.autocompact.context_provider import (
    CompactionResult,
    CompressionConfig,
    ContextProvider,
    DefaultContextProvider,
    get_context_provider,
    list_providers,
    register_provider,
)

from llmslim import count_tokens
from llmslim.integrations import gptme as adapter
from llmslim.integrations import gptme_plugin
from llmslim.integrations.gptme import LLMSlimContextProvider, source_digest
from llmslim.integrations.gptme_plugin import init_plugin
from tests._history_corpus import FAILURE, NOTES, SYSTEM_PROMPT, TASK, make_log

START = datetime(2026, 10, 13, 9, 0, 0)


def _conversation():
    """A gptme log: system prompt, task, a tool call, two long tool results, notes, recent turns."""
    texts = [
        ("system", SYSTEM_PROMPT),
        ("user", TASK),
        ("assistant", "Running the test suite.\n```shell\npytest -q\n```"),
        ("system", "Ran command: `pytest -q`\n" + make_log(lines=400)),
        ("assistant", NOTES * 3),
        ("system", "Ran command: `pytest -q tests/test_refund.py`\n" + make_log("tests", 200)),
        ("user", "Keep going."),
        ("assistant", "Switching refund.py to Decimal."),
    ]
    return [
        Message(role, text, timestamp=START + timedelta(seconds=i), pinned=i == 0)
        for i, (role, text) in enumerate(texts)
    ]


def _tokens(messages):
    return sum(count_tokens(m.content) for m in messages)


@pytest.fixture(autouse=True)
def _restore_gptme_default_provider():
    yield
    register_provider("default", DefaultContextProvider)


def _entry_point(group):
    return next(
        (
            ep
            for ep in importlib.metadata.entry_points(group=group)
            if ep.value.startswith("llmslim.")
        ),
        None,
    )


def test_is_a_gptme_context_provider():
    provider = LLMSlimContextProvider()
    assert isinstance(provider, ContextProvider)
    assert provider.name == "llmslim"
    assert provider.keep_recent == 6 and provider.min_tokens == 200


def test_registered_through_the_context_providers_entry_point():
    ep = _entry_point("gptme.context_providers")
    if ep is None:
        pytest.skip("llmslim is not installed as a distribution (no entry points)")
    assert ep.name == "llmslim"
    assert ep.load() is LLMSlimContextProvider
    # gptme's registry finds it by name.
    gptme_providers._registry_initialized = False
    assert "llmslim" in list_providers()
    assert isinstance(get_context_provider("llmslim"), LLMSlimContextProvider)


def test_compress_keeps_structure_and_fits_the_limit():
    messages = _conversation()
    limit = _tokens(messages) // 3
    config = CompressionConfig(limit=limit, keep_head=2)
    result = LLMSlimContextProvider(keep_recent=2).compress(messages, config)

    assert isinstance(result, CompactionResult)
    compacted = result.messages
    assert len(compacted) == len(messages)
    assert [m.role for m in compacted] == [m.role for m in messages]
    assert [m.timestamp for m in compacted] == [m.timestamp for m in messages]
    assert _tokens(compacted) <= limit
    # System prompt and task are kept and pinned, like gptme's own compaction does.
    assert compacted[0].content == SYSTEM_PROMPT and compacted[1].content == TASK
    assert compacted[0].pinned and compacted[1].pinned
    # The assistant message with a tool call is untouched; the recent turns too.
    assert compacted[2].content == messages[2].content
    assert [m.content for m in compacted[-2:]] == [m.content for m in messages[-2:]]
    # Tool results are compressed and keep the failure.
    for i in (3, 5):
        assert count_tokens(compacted[i].content) < count_tokens(messages[i].content)
        assert FAILURE in compacted[i].content
    assert result.covered_through == len(messages) - 1
    assert result.limitations and "LLMSlim" in result.limitations[0]
    # The input is not modified.
    assert messages[3].content.endswith("[99%]")


def test_source_digest_matches_gptme():
    messages = _conversation()
    result = LLMSlimContextProvider().compress(messages, CompressionConfig(limit=10**6))
    assert result.source_digest == source_digest(messages)
    gptme_digest = getattr(gptme_providers, "_compute_source_digest", None)
    if gptme_digest is not None:
        assert result.source_digest == gptme_digest(messages)


def test_large_tool_results_are_capped_even_when_recent():
    messages = _conversation()
    config = CompressionConfig(limit=10**6, max_tool_result_tokens=300)
    provider = LLMSlimContextProvider(keep_recent=4)
    assert provider.should_compress(messages, config)
    compacted = provider.compress(messages, config).messages
    assert count_tokens(compacted[5].content) <= 300  # among the last four messages
    assert FAILURE in compacted[5].content
    assert compacted[4].content == messages[4].content  # notes are under no cap
    assert not provider.should_compress(compacted, config)


def test_nothing_to_do_returns_the_messages_unchanged():
    messages = _conversation()[:3]
    config = CompressionConfig(limit=10**6)
    provider = LLMSlimContextProvider()
    assert not provider.should_compress(messages, config)
    result = provider.compress(messages, config)
    assert [m.content for m in result.messages] == [m.content for m in messages]
    assert result.limitations == []


def test_over_the_limit_drops_oldest_with_a_placeholder():
    messages = _conversation()
    head = _tokens(messages[:3]) + _tokens(messages[-2:])
    config = CompressionConfig(limit=head + 40, keep_head=2)
    result = LLMSlimContextProvider(keep_recent=2, min_tokens=10**6).compress(messages, config)
    assert "omitted by LLMSlim" in result.messages[3].content
    assert any("placeholder" in note for note in result.limitations)


def test_without_a_limit_uses_gptme_default_of_80_percent_of_the_model_context():
    from gptme.llm.models import get_default_model, get_model

    model = get_default_model() or get_model("gpt-4")
    assert adapter._resolve_limit(CompressionConfig()) == int(0.8 * model.context)


def test_plugin_entry_point_loads_through_gptme():
    if _entry_point("gptme.plugins") is None:
        pytest.skip("llmslim is not installed as a distribution (no entry points)")
    from gptme.plugins.entrypoints import discover_entrypoint_plugins

    discover_entrypoint_plugins.cache_clear()
    (plugin,) = discover_entrypoint_plugins(frozenset({"llmslim"}))
    assert plugin is gptme_plugin.plugin
    assert plugin.name == "llmslim" and plugin.init is init_plugin


def test_plugin_init_does_nothing_without_opt_in():
    init_plugin(Config(user=UserConfig(plugin={"llmslim": {"keep_recent": 3}})))
    assert type(get_context_provider("default")) is DefaultContextProvider


def test_plugin_init_makes_llmslim_the_default_with_project_overrides():
    config = Config(
        user=UserConfig(plugin={"llmslim": {"compaction": True, "keep_recent": 3}}),
        project=ProjectConfig(plugin={"llmslim": {"min_tokens": 100}}),
    )
    init_plugin(config)
    provider = get_context_provider("default")
    assert isinstance(provider, LLMSlimContextProvider)
    assert provider.keep_recent == 3 and provider.min_tokens == 100
    assert type(provider).__module__ == "llmslim.integrations.gptme"


def test_plugin_init_rejects_unknown_options():
    config = Config(user=UserConfig(plugin={"llmslim": {"compaction": True, "keep": 3}}))
    with pytest.raises(ValueError):
        init_plugin(config)


def test_configured_keeps_a_callable_scorer_unbound():
    def scorer(query, texts):
        return [0.0 for _ in texts]

    provider = LLMSlimContextProvider.configured(relevance=scorer)()
    assert provider.relevance is scorer


@pytest.mark.parametrize(
    "kwargs",
    [{"keep_recent": -1}, {"keep_recent": True}, {"min_tokens": -5}, {"relevance": "psychic"}],
)
def test_invalid_options(kwargs):
    with pytest.raises(ValueError):
        LLMSlimContextProvider(**kwargs)


def test_gptme_autocompact_hook_uses_llmslim(tmp_path):
    """gptme's own post-turn hook, with LLMSlim registered as the default provider."""
    init_plugin(Config(user=UserConfig(plugin={"llmslim": {"compaction": True, "keep_recent": 2}})))
    messages = [
        Message("system", SYSTEM_PROMPT, pinned=True),
        Message("user", TASK),
        Message("assistant", "Running the tests.\n```shell\npytest -q\n```"),
        Message("system", "Ran command: `pytest -q`\n" + make_log(lines=400)),
        Message("assistant", "One test fails; reading refund.py."),
        Message("user", "Go on."),
    ]
    manager = LogManager(log=messages, logdir=tmp_path)
    gptme_hook._last_autocompact_time = 0.0
    notices = list(gptme_hook.autocompact_hook(manager))
    assert notices and "Auto-compacted" in notices[-1].content
    compacted = manager.log.messages
    assert len(compacted) == len(messages)
    assert count_tokens(compacted[3].content) < count_tokens(messages[3].content) // 10
    assert FAILURE in compacted[3].content
    assert [m.content for m in compacted[:3]] == [m.content for m in messages[:3]]
