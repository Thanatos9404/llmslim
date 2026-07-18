"""Tests for llmslim.rewrite.base — provider abstraction layer."""

from __future__ import annotations

import pytest

from llmslim.rewrite.base import (
    BaseRewriteProvider,
    CallableProvider,
    RewriteRequest,
)

# ─────────────────────────────────────────────────────────────────────
# RewriteRequest
# ─────────────────────────────────────────────────────────────────────


class TestRewriteRequest:
    """RewriteRequest is a frozen dataclass with sensible defaults."""

    def test_minimal_construction(self):
        req = RewriteRequest(text="hello world")
        assert req.text == "hello world"
        assert req.target_ratio == 0.5
        assert req.content_type is None
        assert req.constraints == []
        assert req.template_name is None
        assert req.system_prompt is None
        assert req.user_prompt is None
        assert req.metadata == {}

    def test_full_construction(self):
        req = RewriteRequest(
            text="compress this",
            target_ratio=0.3,
            content_type="rag_context",
            constraints=["keep URLs"],
            template_name="rag",
            system_prompt="You are a compressor.",
            user_prompt="Compress: ...",
            metadata={"temperature": 0.2},
        )
        assert req.target_ratio == 0.3
        assert req.content_type == "rag_context"
        assert req.constraints == ["keep URLs"]
        assert req.template_name == "rag"
        assert req.metadata["temperature"] == 0.2

    def test_frozen(self):
        req = RewriteRequest(text="x")
        with pytest.raises(AttributeError):
            req.text = "y"  # type: ignore[misc]

    def test_default_lists_are_independent(self):
        """Each instance gets its own default list/dict (no shared mutable defaults)."""
        r1 = RewriteRequest(text="a")
        r2 = RewriteRequest(text="b")
        assert r1.constraints is not r2.constraints
        assert r1.metadata is not r2.metadata


# ─────────────────────────────────────────────────────────────────────
# BaseRewriteProvider
# ─────────────────────────────────────────────────────────────────────


class TestBaseRewriteProvider:
    """BaseRewriteProvider is abstract and cannot be instantiated directly."""

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseRewriteProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_rewrite(self):
        class IncompleteProvider(BaseRewriteProvider):
            name = "incomplete"

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_subclass_with_rewrite(self):
        class EchoProvider(BaseRewriteProvider):
            name = "echo"

            def rewrite(self, request: RewriteRequest) -> str:
                return request.text

        provider = EchoProvider()
        assert provider.name == "echo"
        result = provider.rewrite(RewriteRequest(text="hello"))
        assert result == "hello"

    def test_is_available_default(self):
        class MinimalProvider(BaseRewriteProvider):
            name = "minimal"

            def rewrite(self, request: RewriteRequest) -> str:
                return request.text

        provider = MinimalProvider()
        assert provider.is_available() is True

    def test_is_available_override(self):
        class UnavailableProvider(BaseRewriteProvider):
            name = "unavailable"

            def rewrite(self, request: RewriteRequest) -> str:
                return request.text

            def is_available(self) -> bool:
                return False

        provider = UnavailableProvider()
        assert provider.is_available() is False

    def test_provider_receives_full_request(self):
        """Provider gets the complete RewriteRequest with all fields."""
        captured = {}

        class CapturingProvider(BaseRewriteProvider):
            name = "capturing"

            def rewrite(self, request: RewriteRequest) -> str:
                captured["text"] = request.text
                captured["ratio"] = request.target_ratio
                captured["content_type"] = request.content_type
                captured["constraints"] = request.constraints
                captured["system_prompt"] = request.system_prompt
                captured["metadata"] = request.metadata
                return request.text

        provider = CapturingProvider()
        req = RewriteRequest(
            text="test",
            target_ratio=0.4,
            content_type="chat_conversation",
            constraints=["keep names"],
            system_prompt="sys",
            metadata={"max_tokens": 100},
        )
        provider.rewrite(req)

        assert captured["text"] == "test"
        assert captured["ratio"] == 0.4
        assert captured["content_type"] == "chat_conversation"
        assert captured["constraints"] == ["keep names"]
        assert captured["system_prompt"] == "sys"
        assert captured["metadata"] == {"max_tokens": 100}


# ─────────────────────────────────────────────────────────────────────
# CallableProvider
# ─────────────────────────────────────────────────────────────────────


class TestCallableProvider:
    """CallableProvider wraps any callable as a provider."""

    def test_basic_callable(self):
        def fn(req: RewriteRequest) -> str:
            return req.text.upper()

        provider = CallableProvider(fn, name="upper")
        assert provider.name == "upper"
        result = provider.rewrite(RewriteRequest(text="hello"))
        assert result == "HELLO"

    def test_default_name(self):
        provider = CallableProvider(lambda req: req.text)
        assert provider.name == "custom"

    def test_is_available_always_true(self):
        provider = CallableProvider(lambda req: req.text)
        assert provider.is_available() is True

    def test_isinstance_base_provider(self):
        provider = CallableProvider(lambda req: req.text)
        assert isinstance(provider, BaseRewriteProvider)

    def test_rejects_non_callable(self):
        with pytest.raises(TypeError, match="Expected a callable"):
            CallableProvider("not a function")  # type: ignore[arg-type]

    def test_rejects_none(self):
        with pytest.raises(TypeError, match="Expected a callable"):
            CallableProvider(None)  # type: ignore[arg-type]

    def test_callable_receives_request_object(self):
        """Verify the callable gets a RewriteRequest, not raw args."""
        received = {}

        def capture(request: RewriteRequest) -> str:
            received["type"] = type(request).__name__
            received["text"] = request.text
            received["ratio"] = request.target_ratio
            return request.text

        provider = CallableProvider(capture)
        provider.rewrite(RewriteRequest(text="data", target_ratio=0.3))

        assert received["type"] == "RewriteRequest"
        assert received["text"] == "data"
        assert received["ratio"] == 0.3

    def test_callable_exception_propagates(self):
        """Provider exceptions should propagate — engine handles fallback."""

        def failing(req: RewriteRequest) -> str:
            raise RuntimeError("LLM API error")

        provider = CallableProvider(failing)
        with pytest.raises(RuntimeError, match="LLM API error"):
            provider.rewrite(RewriteRequest(text="x"))


# ─────────────────────────────────────────────────────────────────────
# Package import smoke test
# ─────────────────────────────────────────────────────────────────────


class TestPackageImports:
    """Verify rewrite package exports the correct public API."""

    def test_package_imports(self):
        from llmslim.rewrite import (
            BaseRewriteProvider,
            CallableProvider,
            RewriteRequest,
        )

        assert BaseRewriteProvider is not None
        assert CallableProvider is not None
        assert RewriteRequest is not None

    def test_package_all(self):
        import llmslim.rewrite as rewrite_pkg

        assert "BaseRewriteProvider" in rewrite_pkg.__all__
        assert "CallableProvider" in rewrite_pkg.__all__
        assert "RewriteRequest" in rewrite_pkg.__all__
