"""Provider abstraction and request types for the rewrite engine.

This module defines the contract that all LLM rewrite providers must
implement.  The core library never imports any provider SDK —
implementations are user-supplied.

Public API
----------
.. autoclass:: RewriteRequest
.. autoclass:: BaseRewriteProvider
.. autoclass:: CallableProvider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class RewriteRequest:
    """Encapsulates everything a provider needs to perform a rewrite.

    Using a request object (instead of positional arguments) future-proofs
    the provider interface: new fields can be added without breaking
    existing provider implementations.

    Attributes:
        text: The text to rewrite (may be original or pre-compressed).
        target_ratio: Desired fraction of original tokens to retain.
        content_type: Detected or user-specified content type hint
            (e.g. ``"general_text"``, ``"rag_context"``).
        constraints: Free-form constraint strings the provider should
            honour (e.g. ``["preserve all URLs", "keep code blocks"]``).
        template_name: Name of the prompt template being used.
        system_prompt: The assembled system prompt for the LLM call.
        user_prompt: The assembled user prompt for the LLM call.
        metadata: Arbitrary key-value pairs for provider-specific config
            (e.g. ``{"temperature": 0.3, "max_tokens": 2048}``).
    """

    text: str
    target_ratio: float = 0.5
    content_type: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    template_name: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRewriteProvider(ABC):
    """Abstract base class for LLM rewrite providers.

    Subclass this to integrate any LLM backend (OpenAI, Anthropic,
    Gemini, Ollama, a local model, etc.) with the llmslim rewrite
    engine.  The core library depends only on this abstraction — it
    never imports any provider SDK.

    Example::

        class MyOpenAIProvider(BaseRewriteProvider):
            name = "openai"

            def __init__(self, client, model="gpt-4o"):
                self._client = client
                self._model = model

            def rewrite(self, request: RewriteRequest) -> str:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": request.system_prompt or ""},
                        {"role": "user", "content": request.user_prompt or request.text},
                    ],
                    **request.metadata,
                )
                return response.choices[0].message.content

            def is_available(self) -> bool:
                return self._client is not None
    """

    name: str = "base"

    @abstractmethod
    def rewrite(self, request: RewriteRequest) -> str:
        """Rewrite text according to the request.

        Args:
            request: A :class:`RewriteRequest` containing the text,
                target ratio, assembled prompts, and provider metadata.

        Returns:
            The rewritten text as a plain string.

        Raises:
            Any provider-specific exception on failure.  The rewrite
            engine catches these and falls back to extractive
            compression.
        """

    def is_available(self) -> bool:
        """Return ``True`` if this provider is ready to accept requests.

        Override this to check API keys, model availability, network
        connectivity, etc.  The default implementation returns ``True``.
        """
        return True


class CallableProvider(BaseRewriteProvider):
    """Wrap any callable as a rewrite provider.

    This is the simplest integration path — pass a function or lambda
    that accepts a :class:`RewriteRequest` and returns a string.

    Example::

        from llmslim.rewrite import CallableProvider, RewriteRequest

        def my_rewriter(request: RewriteRequest) -> str:
            # call your LLM here
            return request.text[:int(len(request.text) * request.target_ratio)]

        provider = CallableProvider(my_rewriter, name="truncator")

    Args:
        fn: A callable that takes a :class:`RewriteRequest` and returns
            the rewritten text.
        name: Human-readable name for this provider.
    """

    def __init__(
        self,
        fn: Callable[[RewriteRequest], str],
        name: str = "custom",
    ) -> None:
        if not callable(fn):
            raise TypeError(f"Expected a callable, got {type(fn).__name__}")
        self._fn = fn
        self.name = name

    def rewrite(self, request: RewriteRequest) -> str:
        """Delegate to the wrapped callable."""
        return self._fn(request)

    def is_available(self) -> bool:
        """Always ``True`` — the callable is available if it was provided."""
        return True
