"""Explicit in-process Transformers KV continuation with fail-closed validation.

This object is for a single trusted host process. It cannot be serialized into
LLMSlim stores, traces, or the browser. The host still owns inference.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional, Sequence


class TransformersKVSession:
    """Prepare and commit model forward calls using unchanged token prefixes.

    The caller must supply immutable model/tokenizer revision identifiers and
    must call ``clear`` after changing model weights, config, or chat template.
    """

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        model_revision: str,
        tokenizer_revision: str,
        renderer_version: str,
        tenant_id: str,
        cache_kind: str = "dynamic",
        max_cache_len: Optional[int] = None,
    ) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (model_revision, tokenizer_revision, renderer_version, tenant_id)
        ):
            raise ValueError("model, tokenizer, renderer, and tenant identities are required")
        if cache_kind not in {"dynamic", "static"}:
            raise ValueError("cache_kind must be dynamic or static")
        if cache_kind == "static" and (max_cache_len is None or max_cache_len < 1):
            raise ValueError("static cache needs a positive maximum length")
        self.model = model
        self.tokenizer = tokenizer
        self.model_revision = model_revision
        self.tokenizer_revision = tokenizer_revision
        self.renderer_version = renderer_version
        self.tenant_id = tenant_id
        self.cache_kind = cache_kind
        self.max_cache_len = max_cache_len
        self._model_identity = id(model)
        self._tokenizer_identity = id(tokenizer)
        self._config_digest = self._config_hash(model)
        self._token_ids: tuple[int, ...] = ()
        self._cache: Any = None
        self._pending: Optional[tuple[int, ...]] = None

    @staticmethod
    def _config_hash(model: Any) -> str:
        config = getattr(model, "config", None)
        if config is None or not hasattr(config, "to_dict"):
            raise ValueError("model config must expose to_dict for cache compatibility")
        return hashlib.sha256(
            json.dumps(config.to_dict(), sort_keys=True, default=str, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()

    @property
    def cached_tokens(self) -> int:
        return len(self._token_ids)

    def _validate_identity(
        self, *, model_revision: str, tokenizer_revision: str, renderer_version: str, tenant_id: str
    ) -> None:
        if (
            model_revision != self.model_revision
            or tokenizer_revision != self.tokenizer_revision
            or renderer_version != self.renderer_version
            or tenant_id != self.tenant_id
            or id(self.model) != self._model_identity
            or id(self.tokenizer) != self._tokenizer_identity
            or self._config_hash(self.model) != self._config_digest
        ):
            raise ValueError("model, tokenizer, renderer, tenant, or configuration changed")

    def prepare_forward(
        self,
        *,
        full_token_ids: Sequence[int],
        attention_mask: Sequence[int],
        position_ids: Sequence[int],
        device: str,
        model_revision: str,
        tokenizer_revision: str,
        renderer_version: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Return only new token IDs and offsets after validating the cached prefix."""
        self._validate_identity(
            model_revision=model_revision,
            tokenizer_revision=tokenizer_revision,
            renderer_version=renderer_version,
            tenant_id=tenant_id,
        )
        if self._pending is not None:
            raise RuntimeError("commit or abort the pending forward before continuing")
        ids = tuple(full_token_ids)
        if not ids or not all(isinstance(value, int) and value >= 0 for value in ids):
            raise ValueError("full_token_ids must be non-negative integers")
        if ids[: len(self._token_ids)] != self._token_ids:
            raise ValueError("prefix tokens changed; cached KV cannot be reused")
        if len(ids) <= len(self._token_ids):
            raise ValueError("continuation must append new tokens")
        if tuple(attention_mask) != (1,) * len(ids):
            raise ValueError("attention mask must cover the unchanged full sequence")
        if tuple(position_ids) != tuple(range(len(ids))):
            raise ValueError("position IDs must match absolute sequence offsets")
        parameter = next(self.model.parameters(), None)
        if parameter is None or str(parameter.device) != device:
            raise ValueError("model device does not match the requested device")
        if self.max_cache_len is not None and len(ids) > self.max_cache_len:
            raise ValueError("sequence exceeds the static cache capacity")
        if self._cache is not None:
            length = (
                self._cache.get_seq_length() if hasattr(self._cache, "get_seq_length") else None
            )
            if length != len(self._token_ids):
                raise ValueError("KV cache length does not match the token prefix")
        self._pending = ids
        offset = len(self._token_ids)
        return {
            "input_ids": ids[offset:],
            "attention_mask": tuple(attention_mask),
            "position_ids": tuple(position_ids[offset:]),
            "past_key_values": self._cache,
            "use_cache": True,
        }

    def commit_forward(self, *, past_key_values: Any) -> None:
        """Accept a host-produced cache only if its length matches the input."""
        if self._pending is None:
            raise RuntimeError("no forward is pending")
        length = (
            past_key_values.get_seq_length() if hasattr(past_key_values, "get_seq_length") else None
        )
        if length != len(self._pending):
            self._pending = None
            raise ValueError("returned KV cache length is incompatible")
        self._cache = past_key_values
        self._token_ids = self._pending
        self._pending = None

    def forward(
        self,
        *,
        full_token_ids: Sequence[int],
        attention_mask: Sequence[int],
        position_ids: Sequence[int],
        device: str,
        model_revision: str,
        tokenizer_revision: str,
        renderer_version: str,
        tenant_id: str,
    ) -> Any:
        """Run one local prefill/continuation and keep its KV cache in memory."""
        parts = self.prepare_forward(
            full_token_ids=full_token_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            device=device,
            model_revision=model_revision,
            tokenizer_revision=tokenizer_revision,
            renderer_version=renderer_version,
            tenant_id=tenant_id,
        )
        try:
            import torch
            from transformers import DynamicCache, StaticCache

            cache = parts["past_key_values"]
            if cache is None:
                if self.cache_kind == "static" and self.max_cache_len is not None:
                    cache = StaticCache(config=self.model.config, max_cache_len=self.max_cache_len)
                else:
                    cache = DynamicCache(config=self.model.config)
            with torch.no_grad():
                output = self.model(
                    input_ids=torch.tensor([parts["input_ids"]], dtype=torch.long, device=device),
                    attention_mask=torch.tensor(
                        [parts["attention_mask"]], dtype=torch.long, device=device
                    ),
                    position_ids=torch.tensor(
                        [parts["position_ids"]], dtype=torch.long, device=device
                    ),
                    past_key_values=cache,
                    use_cache=True,
                    return_dict=True,
                )
            self.commit_forward(past_key_values=output.past_key_values)
            return output
        except Exception:
            # A model can mutate a cache before raising. Never reuse that state.
            self.clear()
            raise

    def abort_forward(self) -> None:
        self._pending = None

    def clear(self) -> None:
        self._cache = None
        self._token_ids = ()
        self._pending = None

    def __getstate__(self) -> None:
        raise TypeError("KV sessions cannot be serialized")


__all__ = ["TransformersKVSession"]
