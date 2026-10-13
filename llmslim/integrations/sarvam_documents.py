"""Sarvam Document Intelligence as a bounded LLMSlim context source.

:class:`SarvamDocumentSource` (sync) and :class:`AsyncSarvamDocumentSource`
digitise one PDF, PNG, JPEG or ZIP of page images through the ``sarvamai``
Doc AI job API (``doc_ai.digitise`` creates and starts the job,
``doc_ai.get_status`` is polled until a terminal state, ``doc_ai.get_results``
returns Markdown per page) and return one untrusted RAG
:class:`~llmslim.planning.models.ContextItem` per page.

Limits are checked locally before anything is sent: file type (extension and
magic bytes), file size, and page count against Sarvam's 10-page job limit.
Job creation (``doc_ai.digitise``, a POST) is billable, so it is sent once with
``request_options={"max_retries": 0}``, also on injected clients. The read-only
GETs (``get_status``, ``get_results``) keep the SDK's own retries, which cannot
bill anything. A job that outlives the poll deadline raises
:class:`SarvamJobTimeoutError` carrying its ``job_id``. Clients built from a key
never follow redirects; close them with ``close()`` / ``aclose()`` or ``with``.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import time
import zipfile
import zlib
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from ..core import ContextRole
from ..planning.models import ContextItem, ContextKind
from ._guard import UsageGuard, UsageLimits, UsageReservation
from ._sarvam_common import (
    DOCUMENT_LANGUAGES,
    SARVAM_PRICES,
    AsyncClientOwner,
    SarvamJobError,
    SarvamJobTimeoutError,
    SarvamMalformedResponseError,
    SarvamPriceTable,
    SarvamServiceUsage,
    SyncClientOwner,
    async_client,
    check_choice,
    env_key,
    fail_call,
    map_sarvam_error,
    no_retries,
    read_field,
    sync_client,
)

DOCUMENT_GUARD_PREFIX = "sarvam_document"
DEFAULT_DOCUMENT_LIMITS = UsageLimits(
    requests_per_minute=10, max_requests=200, max_units=200.0, unit="inr"
)
SARVAM_MAX_PAGES_PER_JOB = 10
SARVAM_MAX_FILE_BYTES = 200 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
OUTPUT_FORMAT = "md"
CONTENT_TYPES = frozenset({"printed", "handwritten", "mixed"})

# extension -> (type, MIME type)
FILE_TYPES: Dict[str, Tuple[str, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("png", "image/png"),
    ".jpg": ("jpeg", "image/jpeg"),
    ".jpeg": ("jpeg", "image/jpeg"),
    ".zip": ("zip", "application/zip"),
}
_TERMINAL = frozenset({"completed", "partially_completed", "failed", "rejected"})
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
_FILE_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f/\\]{1,255}$")

_SourceT = TypeVar("_SourceT", bound="_DocumentSourceBase")
PathLike = Union[str, "os.PathLike[str]"]


# --------------------------------------------------------------------------- inspection


def _magic_matches(file_type: str, data: bytes) -> bool:
    if file_type == "pdf":
        return b"%PDF-" in data[:1024]
    if file_type == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if file_type == "jpeg":
        return data.startswith(b"\xff\xd8\xff")
    return data.startswith(b"PK\x03\x04")


_PDF_PAGE = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_PDF_PAGES = re.compile(rb"/Type\s*/Pages(?![A-Za-z])")
_PDF_COUNT = re.compile(rb"/Count\s+(\d+)")
_PDF_OBJSTM = re.compile(rb"/Type\s*/ObjStm(?![A-Za-z])")
_MAX_INFLATED_BYTES = 32 * 1024 * 1024
_MAX_DICT_SCAN = 1024 * 1024


def _pdf_segments(data: bytes) -> List[bytes]:
    """The raw file plus the inflated contents of its object streams (bounded)."""

    segments = [data]
    budget = _MAX_INFLATED_BYTES
    for match in _PDF_OBJSTM.finditer(data):
        stream = data.find(b"stream", match.end())
        if stream < 0 or budget <= 0:
            continue
        header = data[data.rfind(b"obj", 0, match.start()) + 1 : stream]
        if b"/FlateDecode" not in header:
            continue
        body = stream + len(b"stream")
        if data[body : body + 2] == b"\r\n":
            body += 2
        elif data[body : body + 1] in (b"\n", b"\r"):
            body += 1
        end = data.find(b"endstream", body)
        if end < 0:
            continue
        try:
            inflated = zlib.decompressobj().decompress(data[body:end], budget)
        except zlib.error:
            continue
        budget -= len(inflated)
        segments.append(inflated)
    return segments


def _dict_span(data: bytes, position: int) -> Optional[Tuple[int, int]]:
    """Bounds of the ``<< >>`` dictionary that contains ``position``."""

    depth = 0
    index = position
    opening = -1
    while index >= 2 and position - index < _MAX_DICT_SCAN:
        pair = data[index - 2 : index]
        if pair == b">>":
            depth += 1
            index -= 2
        elif pair == b"<<":
            if depth == 0:
                opening = index - 2
                break
            depth -= 1
            index -= 2
        else:
            index -= 1
    if opening < 0:
        return None
    depth = 1
    index = opening + 2
    limit = min(len(data), opening + _MAX_DICT_SCAN)
    while index < limit:
        pair = data[index : index + 2]
        if pair == b"<<":
            depth += 1
            index += 2
        elif pair == b">>":
            depth -= 1
            index += 2
            if depth == 0:
                return opening, index
        else:
            index += 1
    return None


def pdf_page_count(data: bytes) -> Optional[int]:
    """Best-effort page count of a PDF without a PDF library.

    Uses the largest ``/Count`` of a ``/Type /Pages`` node (the page-tree root),
    falling back to the number of ``/Type /Page`` objects; object streams are
    inflated (bounded). Returns ``None`` when neither is found, for example for
    encrypted or unusually encoded files.
    """

    tree_counts: List[int] = []
    leaves = 0
    for segment in _pdf_segments(data):
        leaves += len(_PDF_PAGE.findall(segment))
        for match in _PDF_PAGES.finditer(segment):
            span = _dict_span(segment, match.start())
            if span is None:
                continue
            count = _PDF_COUNT.search(segment, span[0], span[1])
            if count:
                tree_counts.append(int(count.group(1)))
    if tree_counts:
        return max(tree_counts)
    return leaves or None


def _zip_page_count(data: bytes) -> int:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("file is not a readable ZIP archive") from None
    images = 0
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts = [part for part in info.filename.replace("\\", "/").split("/") if part]
            if len(parts) > 2 or ".." in parts or info.filename.startswith(("/", "\\")):
                raise ValueError("ZIP archives must be flat (at most one folder level)")
            if os.path.splitext(parts[-1])[1].lower() not in _IMAGE_EXTENSIONS:
                raise ValueError("ZIP archives may contain only PNG or JPEG page images")
            images += 1
    if images == 0:
        raise ValueError("ZIP archive contains no page images")
    return images


@dataclass(frozen=True)
class _Document:
    file_name: str
    file_type: str
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: Optional[int]
    language_code: str
    request: Dict[str, Any]
    reserved_pages: int


# --------------------------------------------------------------------------- results


@dataclass(frozen=True)
class SarvamDocumentResult:
    """Pages of one digitised document; ``missing_pages`` lists pages without text."""

    items: Tuple[ContextItem, ...]
    job_id: str
    status: str
    file_name: str
    file_sha256: str
    language_code: str
    pages_total: Optional[int]
    pages_succeeded: Optional[int]
    pages_failed: Optional[int]
    missing_pages: Tuple[int, ...]
    usage: SarvamServiceUsage


def _optional_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _first_count(usages: Sequence[Any], name: str) -> Optional[int]:
    for usage in usages:
        if usage is not None:
            value = _optional_count(read_field(usage, name))
            if value is not None:
                return value
    return None


def _billed_pages(usage: Any) -> Optional[int]:
    """Pages Sarvam reports as processed (succeeded + failed): the conservative billing read."""

    if usage is None:
        return None
    processed = _optional_count(read_field(usage, "pages_processed"))
    if processed is not None:
        return processed
    succeeded = _optional_count(read_field(usage, "pages_succeeded"))
    failed = _optional_count(read_field(usage, "pages_failed"))
    if succeeded is not None and failed is not None:
        return succeeded + failed
    return None


def _numbered_pages(
    document_index: int, entry_pages: Sequence[Any], job_id: str
) -> List[Tuple[int, int, Optional[str], bool]]:
    """Validate one document's pages and give every page a number.

    A page without ``page_number`` takes its 1-based position in the list, or, if
    another page already carries that number, the next number after the highest
    one in use. Such pages are flagged as inferred.
    """

    explicit = set()
    parsed: List[Tuple[Optional[int], Optional[str]]] = []
    for page in entry_pages:
        number = read_field(page, "page_number")
        content = read_field(page, "content")
        if number is not None and (
            isinstance(number, bool) or not isinstance(number, int) or number < 1
        ):
            raise SarvamMalformedResponseError(
                "Sarvam returned a page with an invalid page_number", job_id=job_id
            )
        if content is not None and not isinstance(content, str):
            raise SarvamMalformedResponseError(
                "Sarvam returned non-text page content", job_id=job_id
            )
        if number is not None:
            if number in explicit:
                raise SarvamMalformedResponseError(
                    "Sarvam returned the same page twice", job_id=job_id
                )
            explicit.add(number)
        parsed.append((number, content))
    used = set(explicit)
    numbered = []
    for position, (number, content) in enumerate(parsed, start=1):
        if number is not None:
            numbered.append((document_index, number, content, False))
            continue
        inferred = position if position not in used else max(used) + 1
        used.add(inferred)
        numbered.append((document_index, inferred, content, True))
    return numbered


# --------------------------------------------------------------------------- sources


class _DocumentSourceBase:
    source_id = "sarvam:document"

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        client: Optional[Any] = None,
        guard: Optional[UsageGuard] = None,
        prices: SarvamPriceTable = SARVAM_PRICES,
        timeout_seconds: float = 60.0,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        max_pages_per_job: int = SARVAM_MAX_PAGES_PER_JOB,
        poll_interval_seconds: float = 5.0,
        poll_timeout_seconds: float = 300.0,
        allow_partial: bool = True,
        clock: Optional[Callable[[], float]] = None,
        sleep: Optional[Callable[[float], Any]] = None,
    ) -> None:
        for name, value in (
            ("timeout_seconds", timeout_seconds),
            ("poll_interval_seconds", poll_interval_seconds),
            ("poll_timeout_seconds", poll_timeout_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if (
            isinstance(max_file_bytes, bool)
            or not isinstance(max_file_bytes, int)
            or not 0 < max_file_bytes <= SARVAM_MAX_FILE_BYTES
        ):
            raise ValueError(f"max_file_bytes must be between 1 and {SARVAM_MAX_FILE_BYTES}")
        if (
            isinstance(max_pages_per_job, bool)
            or not isinstance(max_pages_per_job, int)
            or not 0 < max_pages_per_job <= SARVAM_MAX_PAGES_PER_JOB
        ):
            raise ValueError(f"max_pages_per_job must be between 1 and {SARVAM_MAX_PAGES_PER_JOB}")
        if not isinstance(prices, SarvamPriceTable):
            raise TypeError("prices must be a SarvamPriceTable")
        self._owned_http: Any = None
        if client is None:
            client, self._owned_http = self._make_client(api_key, timeout_seconds)
        self._client = client
        self.guard = (
            guard
            if guard is not None
            else UsageGuard(DEFAULT_DOCUMENT_LIMITS, name=DOCUMENT_GUARD_PREFIX)
        )
        self.prices = prices
        self.timeout_seconds = timeout_seconds
        self.max_file_bytes = max_file_bytes
        self.max_pages_per_job = max_pages_per_job
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.poll_timeout_seconds = float(poll_timeout_seconds)
        self.allow_partial = allow_partial
        self._clock: Callable[[], float] = clock or time.monotonic
        self._sleep: Callable[[float], Any] = sleep or self._default_sleep()

    def _make_client(self, api_key: Optional[str], timeout_seconds: float) -> Any:
        return sync_client(api_key, timeout_seconds, type(self).__name__)

    def _default_sleep(self) -> Callable[[float], Any]:
        return time.sleep

    @classmethod
    def from_env(
        cls: Type[_SourceT],
        env_var: str = "SARVAM_API_KEY",
        *,
        guard: Optional[UsageGuard] = None,
        **kwargs: Any,
    ) -> _SourceT:
        """Read one named key variable and the ``LLMSLIM_SARVAM_DOCUMENT_*`` guard limits."""

        api_key = env_key(env_var)
        if guard is None:
            guard = UsageGuard.from_env(DOCUMENT_GUARD_PREFIX, DEFAULT_DOCUMENT_LIMITS)
        return cls(api_key=api_key, guard=guard, **kwargs)

    # -- validation ---------------------------------------------------------------------

    def _read(self, path: PathLike) -> Tuple[str, bytes]:
        resolved = os.fspath(path)
        file_name = os.path.basename(resolved)
        self._file_type(file_name)
        size = os.path.getsize(resolved)
        if size > self.max_file_bytes:
            raise ValueError(f"document is {size} bytes; the limit is {self.max_file_bytes} bytes")
        with open(resolved, "rb") as handle:
            return file_name, handle.read(self.max_file_bytes + 1)

    @staticmethod
    def _file_type(file_name: str) -> Tuple[str, str]:
        if not isinstance(file_name, str) or not _FILE_NAME_RE.fullmatch(file_name):
            raise ValueError("file_name must be a plain file name without path separators")
        extension = os.path.splitext(file_name)[1].lower()
        if extension not in FILE_TYPES:
            raise ValueError("unsupported document type; allowed: " + ", ".join(sorted(FILE_TYPES)))
        return FILE_TYPES[extension]

    def _prepare(
        self,
        data: bytes,
        file_name: str,
        language: str,
        content_type: Optional[str],
    ) -> _Document:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes")
        data = bytes(data)
        file_type, mime_type = self._file_type(file_name)
        if language is None:
            raise ValueError("language is required, for example 'hi-IN' or 'en-IN'")
        check_choice(language, DOCUMENT_LANGUAGES, "document language")
        check_choice(content_type, CONTENT_TYPES, "document content type")
        if not data:
            raise ValueError("document is empty")
        if len(data) > self.max_file_bytes:
            raise ValueError(
                f"document is {len(data)} bytes; the limit is {self.max_file_bytes} bytes"
            )
        if not _magic_matches(file_type, data):
            raise ValueError(f"file content does not match its {file_type.upper()} extension")
        if file_type == "pdf":
            page_count = pdf_page_count(data)
        elif file_type == "zip":
            page_count = _zip_page_count(data)
        else:
            page_count = 1
        if page_count is not None and page_count > self.max_pages_per_job:
            raise ValueError(
                f"document has {page_count} pages; a job accepts at most "
                f"{self.max_pages_per_job}. Split it and digitise each part."
            )
        request: Dict[str, Any] = {
            "file": [(file_name, data, mime_type)],
            "language": language,
        }
        if content_type is not None:
            request["content_type"] = content_type
        return _Document(
            file_name=file_name,
            file_type=file_type,
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=page_count,
            language_code=language,
            request=request,
            # An uncountable PDF reserves the full job allowance until Sarvam reports usage.
            reserved_pages=page_count if page_count is not None else self.max_pages_per_job,
        )

    def _page_price(self, pages: float) -> float:
        return pages * float(self.prices.document_digitization_per_page)

    # -- job handling -------------------------------------------------------------------

    @staticmethod
    def _job_id(started: Any) -> str:
        job_id = read_field(started, "job_id")
        if not isinstance(job_id, str) or not job_id.strip():
            raise SarvamMalformedResponseError("Sarvam did not return a document job id")
        return job_id

    @staticmethod
    def _state(status: Any, job_id: str) -> str:
        state = read_field(status, "status")
        if not isinstance(state, str) or not state.strip():
            raise SarvamMalformedResponseError(
                "Sarvam returned a job status without a state", job_id=job_id
            )
        return state.strip().lower()

    def _settle(
        self,
        reservation: UsageReservation,
        usages: Sequence[Any],
        *,
        release_if_unknown: bool = False,
    ) -> Optional[int]:
        for usage in usages:
            pages = _billed_pages(usage)
            if pages is not None:
                self.guard.settle(reservation, self._page_price(pages))
                return pages
        if release_if_unknown:
            self.guard.release(reservation)
        # Otherwise the reservation stays charged: Sarvam may still bill the job.
        return None

    def _check_terminal(
        self, document: _Document, job_id: str, state: str, status: Any, reservation: Any
    ) -> None:
        if state in ("failed", "rejected"):
            self._settle(
                reservation,
                [read_field(status, "usage")],
                release_if_unknown=state == "rejected",
            )
            raise SarvamJobError(
                f"Sarvam document job {state} for {document.file_name}",
                job_id=job_id,
                status=state,
            )

    def _next_wait(self, job_id: str, deadline: float) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise SarvamJobTimeoutError(
                f"Sarvam document job did not finish within {self.poll_timeout_seconds:g}s",
                job_id=job_id,
            )
        return min(self.poll_interval_seconds, remaining)

    def _result(
        self,
        document: _Document,
        job_id: str,
        state: str,
        status: Any,
        results: Any,
        reservation: UsageReservation,
    ) -> SarvamDocumentResult:
        status_usage = read_field(status, "usage")
        results_usage = read_field(results, "usage") if results is not None else None
        billed = self._settle(reservation, [status_usage, results_usage])
        if state == "partially_completed" and not self.allow_partial:
            raise SarvamJobError(
                f"Sarvam document job partially completed for {document.file_name}",
                job_id=job_id,
                status=state,
            )
        usages = (status_usage, results_usage)
        pages_total = _first_count(usages, "pages_total")
        items, missing = self._items(document, job_id, state, results, pages_total)
        quantity = billed if billed is not None else document.reserved_pages
        return SarvamDocumentResult(
            items=items,
            job_id=job_id,
            status=state,
            file_name=document.file_name,
            file_sha256=document.sha256,
            language_code=document.language_code,
            pages_total=pages_total,
            pages_succeeded=_first_count(usages, "pages_succeeded"),
            pages_failed=_first_count(usages, "pages_failed"),
            missing_pages=missing,
            usage=SarvamServiceUsage(
                service="document_digitization",
                requests=1,
                quantity=quantity,
                unit="pages",
                cost_inr=self._page_price(quantity),
                price_as_of=self.prices.as_of,
                classification="PROVIDER_REPORTED" if billed is not None else "ESTIMATED",
            ),
        )

    def _items(
        self,
        document: _Document,
        job_id: str,
        state: str,
        results: Any,
        pages_total: Optional[int],
    ) -> Tuple[Tuple[ContextItem, ...], Tuple[int, ...]]:
        documents = read_field(results, "documents")
        if not isinstance(documents, (list, tuple)):
            raise SarvamMalformedResponseError(
                "Sarvam document results have no documents", job_id=job_id
            )
        # (document index, page number, content, whether the number was inferred)
        pages: List[Tuple[int, int, Optional[str], bool]] = []
        for document_index, entry in enumerate(documents):
            entry_pages = read_field(entry, "pages")
            if entry_pages is None:
                continue
            if not isinstance(entry_pages, (list, tuple)):
                raise SarvamMalformedResponseError(
                    "Sarvam document pages are malformed", job_id=job_id
                )
            pages.extend(_numbered_pages(document_index, entry_pages, job_id))
        pages.sort(key=lambda page: (page[0], page[1]))
        items = []
        with_text = set()
        for order, (document_index, number, content, inferred) in enumerate(
            page for page in pages if page[2] and page[2].strip()
        ):
            assert content is not None
            with_text.add(number)
            metadata: Dict[str, Any] = {
                "page_number": number,
                "document_index": document_index,
                "file_name": document.file_name,
                "file_sha256": document.sha256,
                "language_code": document.language_code,
                "job_id": job_id,
                "job_status": state,
                "output_format": OUTPUT_FORMAT,
                "pages_total": pages_total,
            }
            if inferred:
                # Sarvam sent the page without a page_number (the SDK marks it optional); the job
                # was billed, so keep the text and say the number came from the page's position.
                metadata["page_number_inferred"] = True
            items.append(
                ContextItem(
                    item_id=f"sarvam-document:{document.sha256[:16]}:{document_index}:{number}",
                    content=content,
                    kind=ContextKind.RAG_DOCUMENT,
                    role=ContextRole.RAG,
                    original_order=order,
                    source=self.source_id,
                    metadata=metadata,
                )
            )
        if pages_total is not None:
            missing = tuple(n for n in range(1, pages_total + 1) if n not in with_text)
        else:
            missing = tuple(sorted({page[1] for page in pages} - with_text))
        return tuple(items), missing

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(max_pages_per_job={self.max_pages_per_job}, "
            f"guard={self.guard.name!r}, credentials=<redacted>)"
        )


class SarvamDocumentSource(_DocumentSourceBase, SyncClientOwner):
    """Synchronous Sarvam document digitisation into per-page context items."""

    def digitize(
        self, path: PathLike, *, language: str, content_type: Optional[str] = None
    ) -> SarvamDocumentResult:
        """Digitise a local PDF, PNG, JPEG or ZIP file. ``language`` is a BCP-47 code."""

        file_name, data = self._read(path)
        return self.digitize_bytes(
            data, file_name=file_name, language=language, content_type=content_type
        )

    def digitize_bytes(
        self,
        data: bytes,
        *,
        file_name: str,
        language: str,
        content_type: Optional[str] = None,
    ) -> SarvamDocumentResult:
        document = self._prepare(data, file_name, language, content_type)
        reservation = self.guard.acquire(self._page_price(document.reserved_pages))
        try:
            # Creating the job is billable: one attempt only.
            started = self._client.doc_ai.digitise(**document.request, request_options=no_retries())
        except Exception as exc:
            fail_call(self.guard, reservation, exc)
        job_id = self._job_id(started)
        status = self._poll(job_id)
        state = self._state(status, job_id)
        self._check_terminal(document, job_id, state, status, reservation)
        try:
            # A read-only GET of a finished job: the SDK's own retries cannot bill anything.
            results = self._client.doc_ai.get_results(job_id, format=OUTPUT_FORMAT)
        except Exception as exc:
            self._settle(reservation, [read_field(status, "usage")])
            raise map_sarvam_error(exc, job_id=job_id) from None
        return self._result(document, job_id, state, status, results, reservation)

    def _poll(self, job_id: str) -> Any:
        deadline = self._clock() + self.poll_timeout_seconds
        while True:
            try:
                # Read-only status poll (GET): SDK retries are harmless here and stay on.
                status = self._client.doc_ai.get_status(job_id)
            except Exception as exc:
                raise map_sarvam_error(exc, job_id=job_id) from None
            if self._state(status, job_id) in _TERMINAL:
                return status
            self._sleep(self._next_wait(job_id, deadline))


class AsyncSarvamDocumentSource(_DocumentSourceBase, AsyncClientOwner):
    """Asyncio twin of :class:`SarvamDocumentSource` backed by ``AsyncSarvamAI``."""

    def _make_client(self, api_key: Optional[str], timeout_seconds: float) -> Any:
        return async_client(api_key, timeout_seconds, type(self).__name__)

    def _default_sleep(self) -> Callable[[float], Any]:
        return asyncio.sleep

    async def digitize(
        self, path: PathLike, *, language: str, content_type: Optional[str] = None
    ) -> SarvamDocumentResult:
        file_name, data = await asyncio.to_thread(self._read, path)
        return await self.digitize_bytes(
            data, file_name=file_name, language=language, content_type=content_type
        )

    async def digitize_bytes(
        self,
        data: bytes,
        *,
        file_name: str,
        language: str,
        content_type: Optional[str] = None,
    ) -> SarvamDocumentResult:
        document = await asyncio.to_thread(self._prepare, data, file_name, language, content_type)
        reservation = self.guard.acquire(self._page_price(document.reserved_pages))
        try:
            # Creating the job is billable: one attempt only.
            started = await self._client.doc_ai.digitise(
                **document.request, request_options=no_retries()
            )
        except Exception as exc:
            fail_call(self.guard, reservation, exc)
        job_id = self._job_id(started)
        status = await self._poll(job_id)
        state = self._state(status, job_id)
        self._check_terminal(document, job_id, state, status, reservation)
        try:
            # A read-only GET of a finished job: the SDK's own retries cannot bill anything.
            results = await self._client.doc_ai.get_results(job_id, format=OUTPUT_FORMAT)
        except Exception as exc:
            self._settle(reservation, [read_field(status, "usage")])
            raise map_sarvam_error(exc, job_id=job_id) from None
        return self._result(document, job_id, state, status, results, reservation)

    async def _poll(self, job_id: str) -> Any:
        deadline = self._clock() + self.poll_timeout_seconds
        while True:
            try:
                # Read-only status poll (GET): SDK retries are harmless here and stay on.
                status = await self._client.doc_ai.get_status(job_id)
            except Exception as exc:
                raise map_sarvam_error(exc, job_id=job_id) from None
            if self._state(status, job_id) in _TERMINAL:
                return status
            await self._sleep(self._next_wait(job_id, deadline))


__all__ = [
    "CONTENT_TYPES",
    "DEFAULT_DOCUMENT_LIMITS",
    "DEFAULT_MAX_FILE_BYTES",
    "DOCUMENT_GUARD_PREFIX",
    "FILE_TYPES",
    "SARVAM_MAX_FILE_BYTES",
    "SARVAM_MAX_PAGES_PER_JOB",
    "AsyncSarvamDocumentSource",
    "SarvamDocumentResult",
    "SarvamDocumentSource",
    "pdf_page_count",
]
