"""Shared pieces of the Sarvam integrations: typed errors, prices, language codes, guards.

Nothing here imports the ``sarvamai`` SDK at module import time; the client
loaders import it lazily so the core library stays importable without the
``llmslim[sarvam]`` extra.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, FrozenSet, Mapping, NoReturn, Optional

from ._guard import RateLimitExceeded, UsageCapExceeded, UsageGuard, UsageReservation

PRICING_SOURCE = "https://docs.sarvam.ai/api/getting-started/pricing"
INSTALL_HINT = 'Sarvam integrations require the optional extra: pip install "llmslim[sarvam]"'


# --------------------------------------------------------------------------- errors


class SarvamProviderError(RuntimeError):
    """Sanitized base error for Sarvam failures. Never carries the key or response body."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.job_id = job_id


class SarvamAuthenticationError(SarvamProviderError):
    """HTTP 401/403: the key is missing, wrong or not entitled to the endpoint."""


class SarvamRateLimitError(SarvamProviderError):
    """HTTP 429 from Sarvam (distinct from a local :class:`RateLimitExceeded`)."""


class SarvamTimeoutError(SarvamProviderError):
    """The request or a document job did not finish in time."""


class SarvamMalformedResponseError(SarvamProviderError):
    """Sarvam answered, but not in the documented shape."""


class SarvamInvalidRequestError(SarvamProviderError):
    """HTTP 400/404/409/413/422: Sarvam rejected the request as sent."""


class SarvamPaymentRequiredError(SarvamProviderError):
    """HTTP 402: the Sarvam account has no credits left for this call."""


class SarvamServerError(SarvamProviderError):
    """HTTP 5xx from Sarvam."""


class SarvamJobError(SarvamProviderError):
    """A document job ended ``failed``/``rejected``, or partially when partial results are off."""

    def __init__(self, message: str, *, job_id: Optional[str], status: str) -> None:
        super().__init__(message, job_id=job_id)
        self.status = status


class SarvamJobTimeoutError(SarvamTimeoutError):
    """A document job was still running when the poll deadline passed.

    The job was created (and may still be billed); resume it with ``job_id``
    through the SDK instead of submitting the file again.
    """


# Errors raised before Sarvam processed anything. Their guard reservation is released;
# every other failure keeps its reservation, because the call may still be billed.
_UNBILLED = (
    SarvamAuthenticationError,
    SarvamRateLimitError,
    SarvamInvalidRequestError,
    SarvamPaymentRequiredError,
)


def _status_of(exc: BaseException) -> Optional[int]:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def map_sarvam_error(exc: BaseException, *, job_id: Optional[str] = None) -> SarvamProviderError:
    """Translate an SDK or transport exception into a sanitized typed error.

    Mapping uses the exception class name and the HTTP status only; the
    original message, headers and body (which may echo request data) are dropped.
    """

    if isinstance(exc, SarvamProviderError):
        return exc
    name = type(exc).__name__.lower()
    status = _status_of(exc)
    kwargs: Any = {"status_code": status, "job_id": job_id}
    if status in (401, 403) or any(
        key in name for key in ("unauthorized", "forbidden", "authentication", "permission")
    ):
        return SarvamAuthenticationError("Sarvam authentication failed", **kwargs)
    if status == 429 or "toomanyrequests" in name or "ratelimit" in name:
        return SarvamRateLimitError("Sarvam rate limit exceeded", **kwargs)
    if status == 402 or "paymentrequired" in name:
        return SarvamPaymentRequiredError("Sarvam account has insufficient credits", **kwargs)
    if status in (408, 504) or "timeout" in name:
        return SarvamTimeoutError("Sarvam request timed out", **kwargs)
    if status is not None and 500 <= status <= 599:
        return SarvamServerError(f"Sarvam server error (HTTP {status})", **kwargs)
    if (status is not None and 200 <= status <= 299) or any(
        key in name for key in ("validationerror", "decodeerror", "parseerror")
    ):
        return SarvamMalformedResponseError("Sarvam returned a malformed response", **kwargs)
    if status is not None and 400 <= status <= 499:
        return SarvamInvalidRequestError(f"Sarvam rejected the request (HTTP {status})", **kwargs)
    return SarvamProviderError(f"Sarvam request failed ({type(exc).__name__})", **kwargs)


def is_unbilled(error: SarvamProviderError) -> bool:
    return isinstance(error, _UNBILLED)


def fail_call(
    guard: Optional[UsageGuard],
    reservation: Optional[UsageReservation],
    exc: BaseException,
    *,
    job_id: Optional[str] = None,
) -> NoReturn:
    """Map ``exc``, release the reservation when Sarvam did not bill, and raise."""

    error = map_sarvam_error(exc, job_id=job_id)
    if guard is not None and reservation is not None and is_unbilled(error):
        guard.release(reservation)
    raise error from None


# --------------------------------------------------------------------------- prices


@dataclass(frozen=True)
class SarvamPriceTable:
    """Published Sarvam prices in INR, dated. Override by passing your own instance.

    Chat-model token prices live in :mod:`llmslim.planning.profiles`.
    """

    as_of: str = "2026-10-12"
    source: str = PRICING_SOURCE
    currency: str = "INR"
    language_identification_per_10k_chars: float = 3.5
    transliteration_per_10k_chars: float = 20.0
    translation_per_10k_chars: float = 20.0
    document_digitization_per_page: float = 0.5
    speech_to_text_per_hour: float = 30.0
    text_to_speech_per_10k_chars: float = 30.0

    def __post_init__(self) -> None:
        for name in (
            "language_identification_per_10k_chars",
            "transliteration_per_10k_chars",
            "translation_per_10k_chars",
            "document_digitization_per_page",
            "speech_to_text_per_hour",
            "text_to_speech_per_10k_chars",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"{name} must be a non-negative number")


SARVAM_PRICES = SarvamPriceTable()


def per_10k_chars(characters: int, rate: float) -> float:
    return characters / 10_000.0 * rate


@dataclass(frozen=True)
class SarvamServiceUsage:
    """Usage of one non-chat Sarvam operation.

    ``ESTIMATED`` means LLMSlim computed the amount from what it sent and the
    dated price table; ``PROVIDER_REPORTED`` means Sarvam reported the billed
    quantity (pages) and only the price is LLMSlim's.
    """

    service: str
    requests: int
    quantity: float
    unit: str
    cost_inr: float
    price_as_of: str
    classification: str = "ESTIMATED"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


# --------------------------------------------------------------------------- language codes
# Mirrors the Literal types of sarvamai 0.1.37; tests compare these with the installed SDK.

TRANSLATE_TARGET_LANGUAGES: FrozenSet[str] = frozenset(
    {
        "bn-IN",
        "en-IN",
        "gu-IN",
        "hi-IN",
        "kn-IN",
        "ml-IN",
        "mr-IN",
        "od-IN",
        "pa-IN",
        "ta-IN",
        "te-IN",
        "as-IN",
        "brx-IN",
        "doi-IN",
        "kok-IN",
        "ks-IN",
        "mai-IN",
        "mni-IN",
        "ne-IN",
        "sa-IN",
        "sat-IN",
        "sd-IN",
        "ur-IN",
    }
)
TRANSLATE_SOURCE_LANGUAGES: FrozenSet[str] = TRANSLATE_TARGET_LANGUAGES | {"auto"}
# Languages mayura:v1 supports; sarvam-translate:v1 covers every target above.
MAYURA_LANGUAGES: FrozenSet[str] = frozenset(
    {
        "bn-IN",
        "en-IN",
        "gu-IN",
        "hi-IN",
        "kn-IN",
        "ml-IN",
        "mr-IN",
        "od-IN",
        "pa-IN",
        "ta-IN",
        "te-IN",
    }
)
TRANSLITERATE_TARGET_LANGUAGES: FrozenSet[str] = MAYURA_LANGUAGES
TRANSLITERATE_SOURCE_LANGUAGES: FrozenSet[str] = MAYURA_LANGUAGES | {"auto"}
DOCUMENT_LANGUAGES: FrozenSet[str] = TRANSLATE_TARGET_LANGUAGES
TRANSLATE_MODELS: FrozenSet[str] = frozenset({"mayura:v1", "sarvam-translate:v1"})
TRANSLATE_MODES: FrozenSet[str] = frozenset(
    {"formal", "modern-colloquial", "classic-colloquial", "code-mixed"}
)
OUTPUT_SCRIPTS: FrozenSet[str] = frozenset({"roman", "fully-native", "spoken-form-in-native"})
NUMERALS_FORMATS: FrozenSet[str] = frozenset({"international", "native"})
SPEAKER_GENDERS: FrozenSet[str] = frozenset({"Male", "Female"})
SPOKEN_FORM_NUMERALS: FrozenSet[str] = frozenset({"english", "native"})

# ISO 15924 script that Sarvam language identification reports for native text.
NATIVE_SCRIPTS = {
    "hi-IN": "Deva",
    "mr-IN": "Deva",
    "bn-IN": "Beng",
    "gu-IN": "Gujr",
    "kn-IN": "Knda",
    "ml-IN": "Mlym",
    "od-IN": "Orya",
    "pa-IN": "Guru",
    "ta-IN": "Taml",
    "te-IN": "Telu",
}


def check_choice(value: Optional[str], allowed: FrozenSet[str], label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"unsupported Sarvam {label}: {value!r}")


# --------------------------------------------------------------------------- guard helpers


def preflight(guard: UsageGuard, requests: int, units: float) -> None:
    """Refuse a multi-request operation up front when the guard cannot admit all of it.

    Each request still goes through :meth:`UsageGuard.acquire`; this check only
    stops an operation that would be cut off half-way, after some parts were billed.
    """

    if requests <= 1:
        return
    snapshot = guard.snapshot()
    limits = guard.limits
    if limits.max_requests is not None and snapshot["requests"] + requests > limits.max_requests:
        raise UsageCapExceeded(
            f"{guard.name}: this operation needs {requests} requests; the request cap of "
            f"{limits.max_requests} allows {max(0, limits.max_requests - snapshot['requests'])} more"
        )
    if limits.max_units is not None and snapshot["units"] + units > limits.max_units + 1e-9:
        raise UsageCapExceeded(
            f"{guard.name}: this operation needs {units:g} {limits.unit}; the usage cap of "
            f"{limits.max_units:g} {limits.unit} has {max(0.0, limits.max_units - snapshot['units']):g} left"
        )
    rpm = limits.requests_per_minute
    if rpm is not None and snapshot["requests_last_minute"] + requests > rpm:
        raise RateLimitExceeded(
            f"{guard.name}: this operation needs {requests} requests but the rate limit of "
            f"{rpm} per minute has {max(0, rpm - snapshot['requests_last_minute'])} left",
            60.0,
        )


# --------------------------------------------------------------------------- clients


def sync_client(api_key: Optional[str], timeout_seconds: float, owner: str) -> Any:
    if not api_key:
        raise ValueError(
            f"{owner} requires api_key; use from_env() for explicit environment lookup"
        )
    try:
        from sarvamai import SarvamAI
    except ImportError as exc:  # pragma: no cover - clean-extra test exercises this.
        raise ImportError(INSTALL_HINT) from exc
    return SarvamAI(api_subscription_key=api_key, timeout=timeout_seconds)


def async_client(api_key: Optional[str], timeout_seconds: float, owner: str) -> Any:
    if not api_key:
        raise ValueError(
            f"{owner} requires api_key; use from_env() for explicit environment lookup"
        )
    try:
        from sarvamai import AsyncSarvamAI
    except ImportError as exc:  # pragma: no cover - clean-extra test exercises this.
        raise ImportError(INSTALL_HINT) from exc
    return AsyncSarvamAI(api_subscription_key=api_key, timeout=timeout_seconds)


def env_key(env_var: str) -> str:
    """Explicitly read one named environment variable (only ``from_env`` calls this)."""

    api_key = os.environ.get(env_var)
    if not api_key:
        raise ValueError(f"environment variable {env_var} is not set")
    return api_key


def read_field(obj: Any, name: str) -> Any:
    """Read ``name`` from an SDK model or a plain mapping."""

    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


__all__ = [
    "DOCUMENT_LANGUAGES",
    "MAYURA_LANGUAGES",
    "NATIVE_SCRIPTS",
    "SARVAM_PRICES",
    "TRANSLATE_MODELS",
    "TRANSLATE_SOURCE_LANGUAGES",
    "TRANSLATE_TARGET_LANGUAGES",
    "TRANSLITERATE_SOURCE_LANGUAGES",
    "TRANSLITERATE_TARGET_LANGUAGES",
    "SarvamAuthenticationError",
    "SarvamInvalidRequestError",
    "SarvamJobError",
    "SarvamJobTimeoutError",
    "SarvamMalformedResponseError",
    "SarvamPaymentRequiredError",
    "SarvamPriceTable",
    "SarvamProviderError",
    "SarvamRateLimitError",
    "SarvamServerError",
    "SarvamServiceUsage",
    "SarvamTimeoutError",
    "map_sarvam_error",
]
