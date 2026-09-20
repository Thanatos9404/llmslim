"""Built-in and caller-overridable model profiles."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from .models import ModelProfile

_SARVAM_PRICING_SOURCE = "https://docs.sarvam.ai/api/getting-started/pricing"
_SARVAM_MODEL_SOURCE = "https://docs.sarvam.ai/api/getting-started/models/sarvam-105b"

BUILTIN_MODEL_PROFILES: Dict[str, ModelProfile] = {
    "sarvam-105b": ModelProfile(
        model_id="sarvam-105b",
        provider="sarvam",
        context_window=131_072,
        input_cost_per_million=29.28,
        cached_input_cost_per_million=10.98,
        output_cost_per_million=73.20,
        currency="INR",
        capabilities=("chat", "reasoning", "tools", "indic", "structured_output"),
        pricing_as_of="2026-09-18",
        source=_SARVAM_PRICING_SOURCE,
        metadata={"model_source": _SARVAM_MODEL_SOURCE, "limits_are_provider_documented": True},
    ),
    "sarvam-105b-conversations": ModelProfile(
        model_id="sarvam-105b-conversations",
        provider="sarvam",
        context_window=32_768,
        input_cost_per_million=29.28,
        cached_input_cost_per_million=10.98,
        output_cost_per_million=73.20,
        currency="INR",
        capabilities=("chat", "voice_agents", "indic"),
        pricing_as_of="2026-09-18",
        source=_SARVAM_PRICING_SOURCE,
        metadata={"model_source": _SARVAM_MODEL_SOURCE, "limits_are_provider_documented": True},
    ),
    "generic-128k": ModelProfile(
        model_id="generic-128k",
        provider="generic",
        context_window=131_072,
        capabilities=("chat",),
        source="caller-neutral LLMSlim fallback profile",
    ),
}


class ModelProfileRegistry:
    """Mutable registry owned by a planner instance, never global hidden state."""

    def __init__(self, profiles: Iterable[ModelProfile] = ()) -> None:
        self._profiles = dict(BUILTIN_MODEL_PROFILES)
        for profile in profiles:
            self.register(profile)

    def register(self, profile: ModelProfile) -> None:
        self._profiles[profile.model_id] = profile

    def get(self, model_id: str) -> Optional[ModelProfile]:
        return self._profiles.get(model_id)

    def require(self, model_id: str) -> ModelProfile:
        profile = self.get(model_id)
        if profile is None:
            raise ValueError(
                f"unknown model profile '{model_id}'; supply max_input_tokens or a ModelProfile"
            )
        return profile

    def list(self) -> tuple[ModelProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))


__all__ = ["BUILTIN_MODEL_PROFILES", "ModelProfileRegistry"]
