"""Sarvam language tools: language identification, transliteration and translation.

The tools are explicit, guarded wrappers around the official ``sarvamai`` text
endpoints. Texts longer than Sarvam's per-request character limit are split on
sentence or word boundaries (never inside a grapheme cluster), sent in order,
and reassembled with the original whitespace between parts.

Every request is billable, so each is sent once (``request_options`` with
``max_retries=0``, also on injected clients) and clients built from a key never
follow redirects.

The context helpers operate on :class:`~llmslim.planning.models.ContextItem`
and always return new items. Nothing here rewrites content silently:
:func:`annotate_languages` only adds metadata, :func:`normalize_scripts` is an
explicit opt-in that records a hash of the text it replaced and touches only
user, retrieved, memory and tool-result text (never system, developer or tool
schema items), and translation happens only when the caller invokes
:meth:`SarvamLanguageTools.translate`.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, replace
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

from ..core import ContextRole
from ..planning.models import ContextItem, ContextKind
from ._guard import UsageGuard, UsageLimits
from ._sarvam_common import (
    MAYURA_LANGUAGES,
    NATIVE_SCRIPTS,
    NUMERALS_FORMATS,
    OUTPUT_SCRIPTS,
    SARVAM_PRICES,
    SPEAKER_GENDERS,
    SPOKEN_FORM_NUMERALS,
    TRANSLATE_MODELS,
    TRANSLATE_MODES,
    TRANSLATE_SOURCE_LANGUAGES,
    TRANSLATE_TARGET_LANGUAGES,
    TRANSLITERATE_SOURCE_LANGUAGES,
    TRANSLITERATE_TARGET_LANGUAGES,
    AsyncClientOwner,
    SarvamMalformedResponseError,
    SarvamPriceTable,
    SarvamServiceUsage,
    SyncClientOwner,
    async_client,
    check_choice,
    env_key,
    fail_call,
    no_retries,
    per_10k_chars,
    preflight,
    read_field,
    sync_client,
)

TEXT_GUARD_PREFIX = "sarvam_text"
DEFAULT_TEXT_LIMITS = UsageLimits(
    requests_per_minute=60, max_requests=2000, max_units=500.0, unit="inr"
)

# Per-request character limits documented by Sarvam (checked 2026-10-12).
IDENTIFY_LANGUAGE_MAX_CHARS = 1000
TRANSLITERATE_MAX_CHARS = 1000
TRANSLATE_MAX_CHARS: Dict[str, int] = {"mayura:v1": 1000, "sarvam-translate:v1": 2000}
DEFAULT_TRANSLATE_MODEL = "sarvam-translate:v1"

#: Item kinds and roles :func:`normalize_scripts` may rewrite by default: the user's own text,
#: retrieved documents, memories and tool results. System, developer and assistant text and tool
#: schemas are never replaced with vendor output unless the caller lists them explicitly.
NORMALIZABLE_KINDS: FrozenSet[ContextKind] = frozenset(
    {ContextKind.USER, ContextKind.RAG_DOCUMENT, ContextKind.MEMORY, ContextKind.TOOL_RESULT}
)
NORMALIZABLE_ROLES: FrozenSet[ContextRole] = frozenset(
    {ContextRole.USER, ContextRole.RAG, ContextRole.TOOL, ContextRole.GENERAL}
)

_ToolsT = TypeVar("_ToolsT", bound="_LanguageToolsBase")

_OPERATIONS = ("identify_language", "transliterate", "translate")
_SERVICES = {
    "identify_language": "language_identification",
    "transliterate": "transliteration",
    "translate": "translation",
}

# --------------------------------------------------------------------------- splitting

_SENTENCE_END = frozenset(".!?;\u0964\u0965\u061f\u06d4\u3002\u2026")
_CLOSERS = frozenset("\"')]}\u00bb\u201d\u2019")
_ZWJ = "\u200d"
_ZWNJ = "\u200c"


def _is_regional_indicator(char: str) -> bool:
    return "\U0001f1e6" <= char <= "\U0001f1ff"


def _grapheme_boundary(text: str, index: int) -> bool:
    """Whether ``text`` may be cut before ``text[index]`` without splitting a grapheme.

    Covers the parts of Unicode UAX #29 that matter for Indic and mixed text:
    CR LF, combining marks (matras, nukta, anusvara, variation selectors), ZWJ
    and ZWNJ, virama conjuncts, emoji modifiers and regional-indicator pairs.
    """

    if index <= 0 or index >= len(text):
        return True
    prev, cur = text[index - 1], text[index]
    if prev == "\r" and cur == "\n":
        return False
    if cur in (_ZWJ, _ZWNJ) or unicodedata.category(cur) in ("Mn", "Mc", "Me"):
        return False
    if "\U0001f3fb" <= cur <= "\U0001f3ff":  # emoji skin-tone modifiers
        return False
    if prev == _ZWJ:
        return False
    if unicodedata.combining(prev) == 9 and unicodedata.category(cur).startswith("L"):
        return False  # virama + consonant forms one conjunct cluster
    if _is_regional_indicator(prev) and _is_regional_indicator(cur):
        run = 0
        position = index - 1
        while position >= 0 and _is_regional_indicator(text[position]):
            run += 1
            position -= 1
        return run % 2 == 0
    return True


def _ends_sentence(text: str, start: int, index: int) -> bool:
    position = index - 1
    while position >= start and text[position].isspace():
        if text[position] == "\n":
            return True
        position -= 1
    while position >= start and text[position] in _CLOSERS:
        position -= 1
    return position >= start and text[position] in _SENTENCE_END


def _choose_cut(text: str, start: int, end: int) -> int:
    """Best cut in ``(start, end]``: a late sentence end, else the last word start."""

    halfway = start + (end - start) // 2
    word_cut: Optional[int] = None
    for index in range(end, start, -1):
        if not (text[index - 1].isspace() and not text[index].isspace()):
            continue
        if not _grapheme_boundary(text, index):
            continue
        if index >= halfway and _ends_sentence(text, start, index):
            return index
        if word_cut is None:
            word_cut = index
    if word_cut is not None:
        return word_cut
    for index in range(end, start, -1):
        if _grapheme_boundary(text, index):
            return index
    raise ValueError("text contains a grapheme cluster longer than the per-request limit")


def split_for_sarvam(text: str, max_chars: int) -> List[str]:
    """Split ``text`` into parts of at most ``max_chars`` characters.

    Parts end on a sentence boundary when one falls in the second half of the
    window, otherwise on a word boundary, and only as a last resort inside a
    long unbroken run, and never inside a grapheme cluster. Whitespace stays
    with the preceding part, so ``"".join(parts) == text``.
    """

    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    parts: List[str] = []
    start = 0
    while len(text) - start > max_chars:
        cut = _choose_cut(text, start, start + max_chars)
        parts.append(text[start:cut])
        start = cut
    parts.append(text[start:])
    return parts


# --------------------------------------------------------------------------- results


@dataclass(frozen=True)
class SarvamLanguageIdentification:
    """Detected language and script; ``segments`` holds one entry per request."""

    language_code: Optional[str]
    script_code: Optional[str]
    characters_sent: int
    total_characters: int
    segments: Tuple[Tuple[Optional[str], Optional[str], int], ...]
    usage: SarvamServiceUsage

    @property
    def mixed(self) -> bool:
        """True when the identified segments disagree on language or script."""

        return len({(language, script) for language, script, _ in self.segments}) > 1


@dataclass(frozen=True)
class SarvamTextResult:
    """Transliterated or translated text, reassembled in the original order."""

    text: str
    source_language_code: str
    target_language_code: str
    model: Optional[str]
    usage: SarvamServiceUsage


@dataclass(frozen=True)
class _Piece:
    lead: str
    core: str
    trail: str


@dataclass(frozen=True)
class _Plan:
    operation: str
    pieces: Tuple[_Piece, ...]
    sent: Tuple[int, ...]
    rate: float

    @property
    def characters(self) -> int:
        return sum(len(self.pieces[index].core) for index in self.sent)

    @property
    def cost_inr(self) -> float:
        return per_10k_chars(self.characters, self.rate)

    def piece_cost(self, index: int) -> float:
        return per_10k_chars(len(self.pieces[index].core), self.rate)


def _require_text(text: Any) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must contain non-whitespace characters")
    return text


def _pieces(text: str, limit: int) -> Tuple[_Piece, ...]:
    pieces = []
    for part in split_for_sarvam(text, limit):
        core = part.strip()
        if not core:
            pieces.append(_Piece(part, "", ""))
            continue
        lead = part[: len(part) - len(part.lstrip())]
        trail = part[len(part.rstrip()) :]
        pieces.append(_Piece(lead, core, trail))
    return tuple(pieces)


def _text_of(response: Any, name: str) -> str:
    value = read_field(response, name)
    if not isinstance(value, str):
        raise SarvamMalformedResponseError(f"Sarvam response is missing {name}")
    return value


def _optional_code(response: Any, name: str) -> Optional[str]:
    if response is None:
        raise SarvamMalformedResponseError("Sarvam returned an empty response")
    value = read_field(response, name)
    if value is not None and not isinstance(value, str):
        raise SarvamMalformedResponseError(f"Sarvam response has a malformed {name}")
    return value or None


# --------------------------------------------------------------------------- tools


class _LanguageToolsBase:
    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        client: Optional[Any] = None,
        guard: Optional[UsageGuard] = None,
        prices: SarvamPriceTable = SARVAM_PRICES,
        timeout_seconds: float = 30.0,
    ) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(prices, SarvamPriceTable):
            raise TypeError("prices must be a SarvamPriceTable")
        self._owned_http: Any = None
        if client is None:
            client, self._owned_http = self._make_client(api_key, timeout_seconds)
        self._client = client
        self.guard = (
            guard if guard is not None else UsageGuard(DEFAULT_TEXT_LIMITS, name=TEXT_GUARD_PREFIX)
        )
        self.prices = prices
        self.timeout_seconds = timeout_seconds

    def _make_client(self, api_key: Optional[str], timeout_seconds: float) -> Any:
        return sync_client(api_key, timeout_seconds, type(self).__name__)

    @classmethod
    def from_env(
        cls: Type[_ToolsT],
        env_var: str = "SARVAM_API_KEY",
        *,
        guard: Optional[UsageGuard] = None,
        **kwargs: Any,
    ) -> _ToolsT:
        """Read one named key variable and the ``LLMSLIM_SARVAM_TEXT_*`` guard limits."""

        api_key = env_key(env_var)
        if guard is None:
            guard = UsageGuard.from_env(TEXT_GUARD_PREFIX, DEFAULT_TEXT_LIMITS)
        return cls(api_key=api_key, guard=guard, **kwargs)

    # -- planning (shared by sync and async) -----------------------------------------

    def estimate(
        self,
        operation: str,
        text: str,
        *,
        model: str = DEFAULT_TRANSLATE_MODEL,
        max_chunks: int = 1,
    ) -> SarvamServiceUsage:
        """Requests, characters and INR an operation on ``text`` would use. No network."""

        if operation not in _OPERATIONS:
            raise ValueError("operation must be one of: " + ", ".join(_OPERATIONS))
        if operation == "identify_language":
            plan = self._plan_identify(text, max_chunks)
        elif operation == "transliterate":
            plan = self._plan("transliterate", text, TRANSLITERATE_MAX_CHARS)
        else:
            if model not in TRANSLATE_MAX_CHARS:
                raise ValueError(f"unsupported Sarvam translation model: {model!r}")
            plan = self._plan("translate", text, TRANSLATE_MAX_CHARS[model])
        return self._usage(plan)

    def _rate(self, operation: str) -> float:
        if operation == "identify_language":
            return float(self.prices.language_identification_per_10k_chars)
        if operation == "transliterate":
            return float(self.prices.transliteration_per_10k_chars)
        return float(self.prices.translation_per_10k_chars)

    def _plan(self, operation: str, text: str, limit: int) -> _Plan:
        pieces = _pieces(_require_text(text), limit)
        sent = tuple(index for index, piece in enumerate(pieces) if piece.core)
        return _Plan(operation, pieces, sent, self._rate(operation))

    def _plan_identify(self, text: str, max_chunks: int) -> _Plan:
        if isinstance(max_chunks, bool) or not isinstance(max_chunks, int) or max_chunks < 1:
            raise ValueError("max_chunks must be a positive integer")
        plan = self._plan("identify_language", text, IDENTIFY_LANGUAGE_MAX_CHARS)
        return replace(plan, sent=plan.sent[:max_chunks])

    def _usage(self, plan: _Plan) -> SarvamServiceUsage:
        return SarvamServiceUsage(
            service=_SERVICES[plan.operation],
            requests=len(plan.sent),
            quantity=plan.characters,
            unit="characters",
            cost_inr=plan.cost_inr,
            price_as_of=self.prices.as_of,
        )

    def _identification(
        self, text: str, plan: _Plan, responses: Sequence[Any]
    ) -> SarvamLanguageIdentification:
        segments = []
        weights: Dict[Tuple[Optional[str], Optional[str]], int] = {}
        for index, response in zip(plan.sent, responses):
            language = _optional_code(response, "language_code")
            script = _optional_code(response, "script_code")
            size = len(plan.pieces[index].core)
            segments.append((language, script, size))
            weights[(language, script)] = weights.get((language, script), 0) + size
        # Most characters wins; ties keep the earliest segment (dicts keep insertion order).
        language, script = max(weights, key=lambda key: weights[key])
        return SarvamLanguageIdentification(
            language_code=language,
            script_code=script,
            characters_sent=plan.characters,
            total_characters=len(text),
            segments=tuple(segments),
            usage=self._usage(plan),
        )

    @staticmethod
    def _transliterate_kwargs(
        source_language_code: str,
        target_language_code: str,
        numerals_format: Optional[str],
        spoken_form: Optional[bool],
        spoken_form_numerals_language: Optional[str],
    ) -> Dict[str, Any]:
        check_choice(source_language_code, TRANSLITERATE_SOURCE_LANGUAGES, "source language")
        check_choice(target_language_code, TRANSLITERATE_TARGET_LANGUAGES, "target language")
        if source_language_code is None or target_language_code is None:
            raise ValueError("source_language_code and target_language_code are required")
        if source_language_code == target_language_code:
            raise ValueError("source and target language codes must differ")
        check_choice(numerals_format, NUMERALS_FORMATS, "numerals format")
        check_choice(spoken_form_numerals_language, SPOKEN_FORM_NUMERALS, "spoken-form numerals")
        if spoken_form is not None and not isinstance(spoken_form, bool):
            raise ValueError("spoken_form must be a boolean")
        kwargs: Dict[str, Any] = {
            "source_language_code": source_language_code,
            "target_language_code": target_language_code,
        }
        optional = {
            "numerals_format": numerals_format,
            "spoken_form": spoken_form,
            "spoken_form_numerals_language": spoken_form_numerals_language,
        }
        kwargs.update({key: value for key, value in optional.items() if value is not None})
        return kwargs

    @staticmethod
    def _translate_kwargs(
        source_language_code: str,
        target_language_code: str,
        model: str,
        mode: Optional[str],
        output_script: Optional[str],
        numerals_format: Optional[str],
        speaker_gender: Optional[str],
    ) -> Dict[str, Any]:
        check_choice(model, TRANSLATE_MODELS, "translation model")
        check_choice(source_language_code, TRANSLATE_SOURCE_LANGUAGES, "source language")
        check_choice(target_language_code, TRANSLATE_TARGET_LANGUAGES, "target language")
        if source_language_code is None or target_language_code is None or model is None:
            raise ValueError("source_language_code, target_language_code and model are required")
        if source_language_code == target_language_code:
            raise ValueError("source and target language codes must differ")
        check_choice(mode, TRANSLATE_MODES, "translation mode")
        check_choice(output_script, OUTPUT_SCRIPTS, "output script")
        check_choice(numerals_format, NUMERALS_FORMATS, "numerals format")
        check_choice(speaker_gender, SPEAKER_GENDERS, "speaker gender")
        if model == "mayura:v1":
            mayura: FrozenSet[str] = MAYURA_LANGUAGES | {"auto"}
            check_choice(source_language_code, mayura, "mayura:v1 source language")
            check_choice(target_language_code, MAYURA_LANGUAGES, "mayura:v1 target language")
        else:
            if source_language_code == "auto":
                raise ValueError("automatic source detection ('auto') requires model='mayura:v1'")
            if mode not in (None, "formal"):
                raise ValueError("sarvam-translate:v1 supports only mode='formal'")
            if output_script is not None:
                raise ValueError("sarvam-translate:v1 does not support output_script")
        kwargs: Dict[str, Any] = {
            "source_language_code": source_language_code,
            "target_language_code": target_language_code,
            "model": model,
        }
        optional = {
            "mode": mode,
            "output_script": output_script,
            "numerals_format": numerals_format,
            "speaker_gender": speaker_gender,
        }
        kwargs.update({key: value for key, value in optional.items() if value is not None})
        return kwargs

    def _text_result(
        self,
        plan: _Plan,
        outputs: Dict[int, str],
        reported_sources: Sequence[Any],
        kwargs: Dict[str, Any],
    ) -> SarvamTextResult:
        parts = []
        for index, piece in enumerate(plan.pieces):
            if index in outputs:
                parts.append(piece.lead + outputs[index] + piece.trail)
            else:
                parts.append(piece.lead)
        source = kwargs["source_language_code"]
        detected = [code for code in reported_sources if isinstance(code, str) and code]
        if source == "auto" and detected:
            source = detected[0]
        return SarvamTextResult(
            text="".join(parts),
            source_language_code=source,
            target_language_code=kwargs["target_language_code"],
            model=kwargs.get("model"),
            usage=self._usage(plan),
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(guard={self.guard.name!r}, credentials=<redacted>)"


class SarvamLanguageTools(_LanguageToolsBase, SyncClientOwner):
    """Synchronous Sarvam language identification, transliteration and translation."""

    def _call(self, units: float, call: Callable[[], Any]) -> Any:
        reservation = self.guard.acquire(units)
        try:
            response = call()
        except Exception as exc:
            fail_call(self.guard, reservation, exc)
        self.guard.settle(reservation, units)
        return response

    def identify_language(self, text: str, *, max_chunks: int = 1) -> SarvamLanguageIdentification:
        """Identify language and script from the first ``max_chunks`` parts of ``text``.

        Each part is at most 1,000 characters. With ``max_chunks > 1`` the result
        is the language with the most characters, and ``mixed`` reports disagreement.
        """

        plan = self._plan_identify(text, max_chunks)
        preflight(self.guard, len(plan.sent), plan.cost_inr)
        responses = [
            self._call(
                plan.piece_cost(index),
                partial(
                    self._client.text.identify_language,
                    input=plan.pieces[index].core,
                    request_options=no_retries(),
                ),
            )
            for index in plan.sent
        ]
        return self._identification(text, plan, responses)

    def transliterate(
        self,
        text: str,
        source_language_code: str,
        target_language_code: str,
        *,
        numerals_format: Optional[str] = None,
        spoken_form: Optional[bool] = None,
        spoken_form_numerals_language: Optional[str] = None,
    ) -> SarvamTextResult:
        """Convert script while keeping pronunciation (romanised Hindi uses ``en-IN`` as source)."""

        kwargs = self._transliterate_kwargs(
            source_language_code,
            target_language_code,
            numerals_format,
            spoken_form,
            spoken_form_numerals_language,
        )
        plan = self._plan("transliterate", text, TRANSLITERATE_MAX_CHARS)
        preflight(self.guard, len(plan.sent), plan.cost_inr)
        outputs: Dict[int, str] = {}
        sources = []
        for index in plan.sent:
            response = self._call(
                plan.piece_cost(index),
                partial(
                    self._client.text.transliterate,
                    input=plan.pieces[index].core,
                    request_options=no_retries(),
                    **kwargs,
                ),
            )
            outputs[index] = _text_of(response, "transliterated_text")
            sources.append(read_field(response, "source_language_code"))
        return self._text_result(plan, outputs, sources, kwargs)

    def translate(
        self,
        text: str,
        source_language_code: str,
        target_language_code: str,
        *,
        model: str = DEFAULT_TRANSLATE_MODEL,
        mode: Optional[str] = None,
        output_script: Optional[str] = None,
        numerals_format: Optional[str] = None,
        speaker_gender: Optional[str] = None,
    ) -> SarvamTextResult:
        """Translate ``text``. Only ever called explicitly; LLMSlim never translates on its own."""

        kwargs = self._translate_kwargs(
            source_language_code,
            target_language_code,
            model,
            mode,
            output_script,
            numerals_format,
            speaker_gender,
        )
        plan = self._plan("translate", text, TRANSLATE_MAX_CHARS[model])
        preflight(self.guard, len(plan.sent), plan.cost_inr)
        outputs: Dict[int, str] = {}
        sources = []
        for index in plan.sent:
            response = self._call(
                plan.piece_cost(index),
                partial(
                    self._client.text.translate,
                    input=plan.pieces[index].core,
                    request_options=no_retries(),
                    **kwargs,
                ),
            )
            outputs[index] = _text_of(response, "translated_text")
            sources.append(read_field(response, "source_language_code"))
        return self._text_result(plan, outputs, sources, kwargs)


class AsyncSarvamLanguageTools(_LanguageToolsBase, AsyncClientOwner):
    """Asyncio twin of :class:`SarvamLanguageTools` backed by ``AsyncSarvamAI``."""

    def _make_client(self, api_key: Optional[str], timeout_seconds: float) -> Any:
        return async_client(api_key, timeout_seconds, type(self).__name__)

    async def _call(self, units: float, call: Callable[[], Any]) -> Any:
        reservation = self.guard.acquire(units)
        try:
            response = await call()
        except Exception as exc:
            fail_call(self.guard, reservation, exc)
        self.guard.settle(reservation, units)
        return response

    async def identify_language(
        self, text: str, *, max_chunks: int = 1
    ) -> SarvamLanguageIdentification:
        plan = self._plan_identify(text, max_chunks)
        preflight(self.guard, len(plan.sent), plan.cost_inr)
        responses = []
        for index in plan.sent:
            responses.append(
                await self._call(
                    plan.piece_cost(index),
                    partial(
                        self._client.text.identify_language,
                        input=plan.pieces[index].core,
                        request_options=no_retries(),
                    ),
                )
            )
        return self._identification(text, plan, responses)

    async def transliterate(
        self,
        text: str,
        source_language_code: str,
        target_language_code: str,
        *,
        numerals_format: Optional[str] = None,
        spoken_form: Optional[bool] = None,
        spoken_form_numerals_language: Optional[str] = None,
    ) -> SarvamTextResult:
        kwargs = self._transliterate_kwargs(
            source_language_code,
            target_language_code,
            numerals_format,
            spoken_form,
            spoken_form_numerals_language,
        )
        plan = self._plan("transliterate", text, TRANSLITERATE_MAX_CHARS)
        preflight(self.guard, len(plan.sent), plan.cost_inr)
        outputs: Dict[int, str] = {}
        sources = []
        for index in plan.sent:
            response = await self._call(
                plan.piece_cost(index),
                partial(
                    self._client.text.transliterate,
                    input=plan.pieces[index].core,
                    request_options=no_retries(),
                    **kwargs,
                ),
            )
            outputs[index] = _text_of(response, "transliterated_text")
            sources.append(read_field(response, "source_language_code"))
        return self._text_result(plan, outputs, sources, kwargs)

    async def translate(
        self,
        text: str,
        source_language_code: str,
        target_language_code: str,
        *,
        model: str = DEFAULT_TRANSLATE_MODEL,
        mode: Optional[str] = None,
        output_script: Optional[str] = None,
        numerals_format: Optional[str] = None,
        speaker_gender: Optional[str] = None,
    ) -> SarvamTextResult:
        kwargs = self._translate_kwargs(
            source_language_code,
            target_language_code,
            model,
            mode,
            output_script,
            numerals_format,
            speaker_gender,
        )
        plan = self._plan("translate", text, TRANSLATE_MAX_CHARS[model])
        preflight(self.guard, len(plan.sent), plan.cost_inr)
        outputs: Dict[int, str] = {}
        sources = []
        for index in plan.sent:
            response = await self._call(
                plan.piece_cost(index),
                partial(
                    self._client.text.translate,
                    input=plan.pieces[index].core,
                    request_options=no_retries(),
                    **kwargs,
                ),
            )
            outputs[index] = _text_of(response, "translated_text")
            sources.append(read_field(response, "source_language_code"))
        return self._text_result(plan, outputs, sources, kwargs)


# --------------------------------------------------------------------------- context helpers


def _with_metadata(item: ContextItem, **updates: Any) -> ContextItem:
    metadata = dict(item.metadata)
    metadata.update(updates)
    return replace(item, metadata=metadata)


def _annotation_targets(items: Iterable[ContextItem], overwrite: bool) -> Tuple[Any, List[int]]:
    collected = tuple(items)
    for item in collected:
        if not isinstance(item, ContextItem):
            raise TypeError("items must be ContextItem instances")
    targets = [
        index
        for index, item in enumerate(collected)
        if item.content.strip() and (overwrite or "language_code" not in item.metadata)
    ]
    return collected, targets


def _preflight_all(tools: _LanguageToolsBase, estimates: Sequence[SarvamServiceUsage]) -> None:
    preflight(
        tools.guard,
        sum(estimate.requests for estimate in estimates),
        sum(estimate.cost_inr for estimate in estimates),
    )


def _annotated(item: ContextItem, result: SarvamLanguageIdentification) -> ContextItem:
    return _with_metadata(
        item,
        language_code=result.language_code,
        script_code=result.script_code,
        language_mixed=result.mixed,
    )


def _check_tools(tools: Any, expected: type, helper: str) -> None:
    if not isinstance(tools, expected):
        raise TypeError(f"{helper} needs a {expected.__name__}")


def annotate_languages(
    items: Iterable[ContextItem],
    tools: SarvamLanguageTools,
    *,
    max_chunks: int = 1,
    overwrite: bool = False,
) -> Tuple[ContextItem, ...]:
    """Return items with ``language_code``, ``script_code`` and ``language_mixed`` metadata.

    Content is never changed. Blank items, and items that already carry a
    ``language_code`` (unless ``overwrite``), are returned as they are without a call.
    """

    _check_tools(tools, SarvamLanguageTools, "annotate_languages")
    collected, targets = _annotation_targets(items, overwrite)
    _preflight_all(
        tools,
        [
            tools.estimate("identify_language", collected[index].content, max_chunks=max_chunks)
            for index in targets
        ],
    )
    result = list(collected)
    for index in targets:
        identified = tools.identify_language(collected[index].content, max_chunks=max_chunks)
        result[index] = _annotated(collected[index], identified)
    return tuple(result)


async def aannotate_languages(
    items: Iterable[ContextItem],
    tools: AsyncSarvamLanguageTools,
    *,
    max_chunks: int = 1,
    overwrite: bool = False,
) -> Tuple[ContextItem, ...]:
    """Async :func:`annotate_languages`; requests run one after another, in item order."""

    _check_tools(tools, AsyncSarvamLanguageTools, "aannotate_languages")
    collected, targets = _annotation_targets(items, overwrite)
    _preflight_all(
        tools,
        [
            tools.estimate("identify_language", collected[index].content, max_chunks=max_chunks)
            for index in targets
        ],
    )
    result = list(collected)
    for index in targets:
        identified = await tools.identify_language(collected[index].content, max_chunks=max_chunks)
        result[index] = _annotated(collected[index], identified)
    return tuple(result)


def _members(values: Iterable[Any], enum: Any, label: str) -> FrozenSet[Any]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{label} must be a collection, not a single string")
    members = set()
    for value in values:
        try:
            members.add(enum(value))
        except ValueError:
            raise ValueError(f"unknown {label[:-1]}: {value!r}") from None
    return frozenset(members)


def _normalization_targets(
    items: Iterable[ContextItem],
    languages: Optional[Iterable[str]],
    skip_required: bool,
    kinds: Iterable[Any],
    roles: Iterable[Any],
) -> Tuple[Any, List[int]]:
    allowed = set(NATIVE_SCRIPTS) if languages is None else set(languages)
    unsupported = sorted(allowed - set(NATIVE_SCRIPTS))
    if unsupported:
        raise ValueError("cannot transliterate into a native script for: " + ", ".join(unsupported))
    allowed_kinds = _members(kinds, ContextKind, "kinds")
    allowed_roles = _members(roles, ContextRole, "roles")
    collected = tuple(items)
    targets = []
    for index, item in enumerate(collected):
        if not isinstance(item, ContextItem):
            raise TypeError("items must be ContextItem instances")
        metadata = item.metadata
        if (
            item.kind in allowed_kinds
            and item.role in allowed_roles
            and item.content.strip()
            and not (skip_required and item.required)
            and "transliterated_from" not in metadata
            and metadata.get("script_code") == "Latn"
            and metadata.get("language_code") in allowed
            and not metadata.get("language_mixed", False)
        ):
            targets.append(index)
    return collected, targets


def _normalized(item: ContextItem, result: SarvamTextResult) -> ContextItem:
    language = item.metadata["language_code"]
    metadata = dict(item.metadata)
    metadata.update(
        script_code=NATIVE_SCRIPTS[language],
        transliterated_from="Latn",
        original_content_sha256=hashlib.sha256(item.content.encode("utf-8")).hexdigest(),
    )
    return replace(item, content=result.text, token_count=0, metadata=metadata)


def normalize_scripts(
    items: Iterable[ContextItem],
    tools: SarvamLanguageTools,
    *,
    languages: Optional[Iterable[str]] = None,
    skip_required: bool = True,
    kinds: Iterable[Any] = NORMALIZABLE_KINDS,
    roles: Iterable[Any] = NORMALIZABLE_ROLES,
) -> Tuple[ContextItem, ...]:
    """Opt-in: transliterate romanised Indic items into their native script.

    Works from metadata written by :func:`annotate_languages`: only items marked
    ``script_code == "Latn"`` with an Indic ``language_code`` (optionally limited
    to ``languages``) and not ``language_mixed`` are converted, so the planner's
    dedupe compares one script. Converted items keep their ID and record
    ``transliterated_from`` and ``original_content_sha256`` (a hash, never the
    original text). ``required`` items are skipped unless ``skip_required=False``.

    Only items whose ``kind`` is in ``kinds`` and whose ``role`` is in ``roles``
    are considered. The defaults (:data:`NORMALIZABLE_KINDS`,
    :data:`NORMALIZABLE_ROLES`) cover user, retrieved, memory and tool-result
    text; system, developer, assistant and tool-schema items are returned
    unchanged unless you list them explicitly.
    """

    _check_tools(tools, SarvamLanguageTools, "normalize_scripts")
    collected, targets = _normalization_targets(items, languages, skip_required, kinds, roles)
    _preflight_all(
        tools, [tools.estimate("transliterate", collected[index].content) for index in targets]
    )
    result = list(collected)
    for index in targets:
        item = collected[index]
        converted = tools.transliterate(item.content, "en-IN", item.metadata["language_code"])
        result[index] = _normalized(item, converted)
    return tuple(result)


async def anormalize_scripts(
    items: Iterable[ContextItem],
    tools: AsyncSarvamLanguageTools,
    *,
    languages: Optional[Iterable[str]] = None,
    skip_required: bool = True,
    kinds: Iterable[Any] = NORMALIZABLE_KINDS,
    roles: Iterable[Any] = NORMALIZABLE_ROLES,
) -> Tuple[ContextItem, ...]:
    """Async :func:`normalize_scripts`, with the same ``kinds`` and ``roles`` filter."""

    _check_tools(tools, AsyncSarvamLanguageTools, "anormalize_scripts")
    collected, targets = _normalization_targets(items, languages, skip_required, kinds, roles)
    _preflight_all(
        tools, [tools.estimate("transliterate", collected[index].content) for index in targets]
    )
    result = list(collected)
    for index in targets:
        item = collected[index]
        converted = await tools.transliterate(item.content, "en-IN", item.metadata["language_code"])
        result[index] = _normalized(item, converted)
    return tuple(result)


__all__ = [
    "DEFAULT_TEXT_LIMITS",
    "DEFAULT_TRANSLATE_MODEL",
    "IDENTIFY_LANGUAGE_MAX_CHARS",
    "NORMALIZABLE_KINDS",
    "NORMALIZABLE_ROLES",
    "TEXT_GUARD_PREFIX",
    "TRANSLATE_MAX_CHARS",
    "TRANSLITERATE_MAX_CHARS",
    "AsyncSarvamLanguageTools",
    "SarvamLanguageIdentification",
    "SarvamLanguageTools",
    "SarvamTextResult",
    "aannotate_languages",
    "annotate_languages",
    "anormalize_scripts",
    "normalize_scripts",
    "split_for_sarvam",
]
