"""Sarvam document digitisation source (fakes only, no network, no real sleeping)."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import io
import zipfile
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional, Sequence

import pytest

from llmslim.core import ContextRole
from llmslim.integrations.sarvam import (
    DEFAULT_DOCUMENT_LIMITS,
    DOCUMENT_GUARD_PREFIX,
    AsyncSarvamDocumentSource,
    SarvamAuthenticationError,
    SarvamDocumentSource,
    SarvamJobError,
    SarvamJobTimeoutError,
    SarvamMalformedResponseError,
    SarvamPaymentRequiredError,
    SarvamRateLimitError,
    SarvamServerError,
    UsageCapExceeded,
    UsageGuard,
    UsageLimits,
)
from llmslim.integrations.sarvam_documents import pdf_page_count
from llmslim.planning.models import ContextKind

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
SECRET = "sk-doc-secret"


def make_pdf(pages: int) -> bytes:
    kids = " ".join(f"{3 + index} 0 R" for index in range(pages))
    body = [
        b"%PDF-1.4\n",
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        f"2 0 obj << /Type /Pages /Resources << /Font << >> >> /Kids [{kids}] /Count {pages} >> endobj\n".encode(),
    ]
    for index in range(pages):
        body.append(f"{3 + index} 0 obj << /Type /Page /Parent 2 0 R >> endobj\n".encode())
    body.append(b"trailer << /Root 1 0 R >>\n%%EOF\n")
    return b"".join(body)


def make_compressed_pdf(pages: int) -> bytes:
    inner = f"<< /Type /Pages /Kids [] /Count {pages} >> ".encode() + (
        b"<< /Type /Page /Parent 2 0 R >> " * pages
    )
    stream = zlib.compress(inner)
    return (
        b"%PDF-1.7\n5 0 obj\n<< /Type /ObjStm /N 3 /First 10 /Filter /FlateDecode /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\r\n"
        + stream
        + b"\nendstream\nendobj\n%%EOF\n"
    )


def make_zip(names: Sequence[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, PNG)
    return buffer.getvalue()


def usage(total: int, processed: Optional[int] = None, succeeded: int = 0, failed: int = 0) -> Any:
    return SimpleNamespace(
        pages_total=total,
        pages_processed=processed,
        pages_succeeded=succeeded,
        pages_failed=failed,
    )


def status(state: str, use: Any = None) -> Any:
    return SimpleNamespace(job_id="job-1", status=state, usage=use)


def results(pages: Sequence[Any], use: Any = None) -> Any:
    return SimpleNamespace(
        documents=[
            SimpleNamespace(
                file_name="doc.pdf",
                pages=[SimpleNamespace(page_number=n, content=c) for n, c in pages],
            )
        ],
        usage=use,
    )


class _Failure(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"Authorization: {SECRET}")
        self.status_code = status_code


class FakeDocAi:
    def __init__(
        self,
        statuses: Sequence[Any] = (),
        result: Any = None,
        *,
        start_error: Optional[BaseException] = None,
        status_error: Optional[BaseException] = None,
        results_error: Optional[BaseException] = None,
        started: Any = None,
    ) -> None:
        self.statuses = list(statuses)
        self.result = result
        self.start_error = start_error
        self.status_error = status_error
        self.results_error = results_error
        self.started = started if started is not None else SimpleNamespace(job_id="job-1")
        self.calls: List[Any] = []

    def digitise(self, **kwargs: Any) -> Any:
        self.calls.append(("digitise", kwargs))
        if self.start_error is not None:
            raise self.start_error
        return self.started

    def get_status(self, job_id: str) -> Any:
        self.calls.append(("get_status", job_id))
        if self.status_error is not None:
            raise self.status_error
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def get_results(self, job_id: str, *, format: str) -> Any:
        self.calls.append(("get_results", job_id, format))
        if self.results_error is not None:
            raise self.results_error
        return self.result

    def names(self) -> List[str]:
        return [call[0] for call in self.calls]


class AsyncFakeDocAi(FakeDocAi):
    async def digitise(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return FakeDocAi.digitise(self, **kwargs)

    async def get_status(self, job_id: str) -> Any:  # type: ignore[override]
        return FakeDocAi.get_status(self, job_id)

    async def get_results(self, job_id: str, *, format: str) -> Any:  # type: ignore[override]
        return FakeDocAi.get_results(self, job_id, format=format)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: List[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)


def guard(**limits: Any) -> UsageGuard:
    base = {"requests_per_minute": None, "max_requests": None, "max_units": None, "unit": "inr"}
    base.update(limits)
    return UsageGuard(UsageLimits(**base), name="doc-test")


def source(fake: FakeDocAi, **kwargs: Any) -> SarvamDocumentSource:
    clock = kwargs.pop("clock", Clock())
    return SarvamDocumentSource(
        client=SimpleNamespace(doc_ai=fake), clock=clock, sleep=clock.sleep, **kwargs
    )


TWO_PAGES = [(1, "# पहला पृष्ठ\nनमस्ते"), (2, "Second page text")]


# --------------------------------------------------------------------------- page counting


def test_pdf_page_counting() -> None:
    assert pdf_page_count(make_pdf(3)) == 3
    assert pdf_page_count(make_compressed_pdf(4)) == 4
    leaves_only = b"%PDF-1.4\n" + b"1 0 obj << /Type /Page >> endobj\n" * 2
    assert pdf_page_count(leaves_only) == 2
    assert pdf_page_count(b"%PDF-1.4\nnothing to see\n%%EOF") is None
    broken = (
        b"%PDF-1.5\n1 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream\nnot zlib\nendstream\n"
    )
    assert pdf_page_count(broken) is None
    unterminated = b"%PDF-1.5\n1 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream\nabc"
    assert pdf_page_count(unterminated) is None
    unclosed = b"%PDF-1.4\n<< /Type /Pages /Count 3 "
    assert pdf_page_count(unclosed) is None
    no_dict = b"%PDF-1.4\n/Type /Pages /Count 3"
    assert pdf_page_count(no_dict) is None
    nested_first = b"%PDF-1.4\n<< /Resources << /Font << >> >> /Type /Pages /Count 6 >>"
    assert pdf_page_count(nested_first) == 6
    no_count = b"%PDF-1.4\n<< /Type /Pages /Kids [] >> << /Type /Page >>"
    assert pdf_page_count(no_count) == 1
    streamless = b"%PDF-1.5\n1 0 obj << /Type /ObjStm >> endobj"
    assert pdf_page_count(streamless) is None
    unfiltered = b"%PDF-1.5\n1 0 obj << /Type /ObjStm >>\nstream\n<< /Type /Page >>\nendstream"
    assert pdf_page_count(unfiltered) == 1  # raw text is still scanned
    inner = zlib.compress(b"<< /Type /Pages /Count 2 >>")
    cr_only = b"%PDF-1.5\n1 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream\r" + inner
    assert pdf_page_count(cr_only + b"\nendstream") == 2
    bare = b"%PDF-1.5\n1 0 obj << /Type /ObjStm /Filter /FlateDecode >>\nstream" + inner
    assert pdf_page_count(bare + b"\nendstream") == 2


# --------------------------------------------------------------------------- happy path


def test_completed_job_becomes_one_item_per_page() -> None:
    data = make_pdf(2)
    fake = FakeDocAi(
        [status("pending"), status("running"), status("completed", usage(2, 2, 2, 0))],
        results(TWO_PAGES),
    )
    clock = Clock()
    doc_guard = guard(max_units=10.0)
    src = source(fake, guard=doc_guard, clock=clock, poll_interval_seconds=3.0)
    result = src.digitize_bytes(data, file_name="report.pdf", language="hi-IN")

    sha = hashlib.sha256(data).hexdigest()
    assert [item.item_id for item in result.items] == [
        f"sarvam-document:{sha[:16]}:0:1",
        f"sarvam-document:{sha[:16]}:0:2",
    ]
    first = result.items[0]
    assert first.kind is ContextKind.RAG_DOCUMENT and first.role is ContextRole.RAG
    assert first.source == "sarvam:document"
    assert first.content.startswith("# पहला पृष्ठ")
    assert dict(first.metadata) == {
        "page_number": 1,
        "document_index": 0,
        "file_name": "report.pdf",
        "file_sha256": sha,
        "language_code": "hi-IN",
        "job_id": "job-1",
        "job_status": "completed",
        "output_format": "md",
        "pages_total": 2,
    }
    assert [item.original_order for item in result.items] == [0, 1]
    assert result.status == "completed" and result.missing_pages == ()
    assert result.usage.classification == "PROVIDER_REPORTED"
    assert result.usage.quantity == 2 and result.usage.cost_inr == pytest.approx(1.0)
    assert doc_guard.snapshot()["units"] == pytest.approx(1.0)
    assert clock.sleeps == [3.0, 3.0]
    kind, request = fake.calls[0]
    assert kind == "digitise"
    assert request == {
        "file": [("report.pdf", data, "application/pdf")],
        "language": "hi-IN",
        # Creating the job is billable: the SDK must not retry it.
        "request_options": {"max_retries": 0},
    }
    assert fake.calls[-1] == ("get_results", "job-1", "md")
    assert fake.names().count("digitise") == 1

    with pytest.raises(dataclasses.FrozenInstanceError):
        first.content = "x"  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.metadata["page_number"] = 9  # type: ignore[index]

    again = source(
        FakeDocAi([status("completed", usage(2, 2, 2, 0))], results(TWO_PAGES))
    ).digitize_bytes(data, file_name="report.pdf", language="hi-IN")
    assert [item.item_id for item in again.items] == [item.item_id for item in result.items]


def test_path_input_images_and_zip_reservations(tmp_path: Path) -> None:
    image = tmp_path / "scan.PNG"
    image.write_bytes(PNG)
    doc_guard = guard(max_units=10.0)
    fake = FakeDocAi([status("completed", None)], results([(1, "page")]))
    result = source(fake, guard=doc_guard).digitize(
        image, language="en-IN", content_type="handwritten"
    )
    assert result.file_name == "scan.PNG"
    assert fake.calls[0][1]["content_type"] == "handwritten"
    assert fake.calls[0][1]["file"][0][2] == "image/png"
    # No usage reported: the one-page estimate stays charged and is labelled ESTIMATED.
    assert result.usage.classification == "ESTIMATED"
    assert doc_guard.snapshot()["units"] == pytest.approx(0.5)

    archive = make_zip(["pages/1.png", "pages/2.jpg", "3.jpeg", "pages/"])
    zip_guard = guard(max_units=10.0)
    zip_fake = FakeDocAi([status("completed", None)], results([(1, "a"), (2, "b"), (3, "c")]))
    source(zip_fake, guard=zip_guard).digitize_bytes(archive, file_name="p.zip", language="ta-IN")
    assert zip_guard.snapshot()["units"] == pytest.approx(1.5)
    jpeg = source(FakeDocAi([status("completed", None)], results([(1, "j")]))).digitize_bytes(
        JPEG, file_name="photo.jpeg", language="mr-IN"
    )
    assert len(jpeg.items) == 1


def test_uncountable_pdf_reserves_the_full_job_then_settles() -> None:
    data = b"%PDF-1.7\n% scanned, encrypted or unusually encoded\n%%EOF"
    doc_guard = guard(max_units=10.0)
    fake = FakeDocAi([status("completed", usage(3, 3, 3, 0))], results([(1, "a")]))
    acquired: List[float] = []
    original = doc_guard.acquire

    def spy(units: float = 0.0) -> Any:
        acquired.append(units)
        return original(units)

    doc_guard.acquire = spy  # type: ignore[method-assign]
    result = source(fake, guard=doc_guard).digitize_bytes(data, file_name="x.pdf", language="en-IN")
    assert acquired == [5.0]  # ten pages at ₹0.5 until Sarvam reports usage
    assert doc_guard.snapshot()["units"] == pytest.approx(1.5)
    assert result.missing_pages == (2, 3)


# --------------------------------------------------------------------------- local refusals


def test_wrong_type_oversize_and_too_many_pages_never_reach_sarvam(tmp_path: Path) -> None:
    fake = FakeDocAi([status("completed")], results([]))
    src = source(fake, max_file_bytes=4096)
    cases = [
        (b"PK\x03\x04", "notes.docx", "unsupported document type"),
        (PNG, "scan.pdf", "does not match"),
        (make_pdf(1), "scan.png", "does not match"),
        (b"", "empty.pdf", "empty"),
        (PNG, "../scan.png", "plain file name"),
        (PNG, "", "plain file name"),
        (b"%PDF-" + b"0" * 5000, "big.pdf", "limit is 4096"),
        (make_pdf(11), "long.pdf", "11 pages"),
        (make_zip(["a/b/c.png"]), "deep.zip", "flat"),
        (make_zip(["notes.txt"]), "text.zip", "only PNG or JPEG"),
        (make_zip(["pages/"]), "folders.zip", "no page images"),
        (make_zip([]), "empty.zip", "does not match"),
        (b"PK\x03\x04garbage", "bad.zip", "not a readable ZIP"),
    ]
    for data, name, message in cases:
        with pytest.raises(ValueError, match=message):
            src.digitize_bytes(data, file_name=name, language="hi-IN")
    with pytest.raises(ValueError, match="at most 2"):
        source(fake, max_pages_per_job=2).digitize_bytes(
            make_pdf(3), file_name="three.pdf", language="hi-IN"
        )
    with pytest.raises(ValueError, match="document language"):
        src.digitize_bytes(PNG, file_name="a.png", language="xx-IN")
    with pytest.raises(ValueError, match="language is required"):
        src.digitize_bytes(PNG, file_name="a.png", language=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="content type"):
        src.digitize_bytes(PNG, file_name="a.png", language="hi-IN", content_type="typed")
    with pytest.raises(TypeError):
        src.digitize_bytes("text", file_name="a.png", language="hi-IN")  # type: ignore[arg-type]

    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-" + b"0" * 5000)
    with pytest.raises(ValueError, match="limit is 4096"):
        src.digitize(big, language="hi-IN")
    with pytest.raises(ValueError, match="unsupported document type"):
        src.digitize(tmp_path / "missing.txt", language="hi-IN")
    assert fake.calls == []


def test_guard_refusal_happens_before_the_job_is_created() -> None:
    fake = FakeDocAi([status("completed")], results([]))
    with pytest.raises(UsageCapExceeded):
        source(fake, guard=guard(max_units=0.4)).digitize_bytes(
            PNG, file_name="a.png", language="hi-IN"
        )
    assert fake.calls == []


# --------------------------------------------------------------------------- failures


@pytest.mark.parametrize(
    "status_code,error_type,released",
    [
        (401, SarvamAuthenticationError, True),
        (402, SarvamPaymentRequiredError, True),
        (429, SarvamRateLimitError, True),
        (500, SarvamServerError, False),
    ],
)
def test_job_creation_errors_are_mapped_and_never_retried(
    status_code: int, error_type: type, released: bool
) -> None:
    doc_guard = guard(max_units=10.0)
    fake = FakeDocAi(start_error=_Failure(status_code))
    with pytest.raises(error_type) as captured:
        source(fake, guard=doc_guard).digitize_bytes(PNG, file_name="a.png", language="hi-IN")
    assert SECRET not in str(captured.value)
    assert fake.names() == ["digitise"]
    assert (doc_guard.snapshot()["units"] == 0) is released


def test_failed_and_rejected_jobs() -> None:
    reported = guard(max_units=10.0)
    fake = FakeDocAi([status("Failed", usage(2, 2, 0, 2))], results([]))
    with pytest.raises(SarvamJobError) as failed:
        source(fake, guard=reported).digitize_bytes(
            make_pdf(2), file_name="a.pdf", language="hi-IN"
        )
    assert failed.value.status == "failed" and failed.value.job_id == "job-1"
    assert reported.snapshot()["units"] == pytest.approx(1.0)
    assert "get_results" not in fake.names()

    unknown = guard(max_units=10.0)
    with pytest.raises(SarvamJobError):
        source(FakeDocAi([status("failed")]), guard=unknown).digitize_bytes(
            make_pdf(2), file_name="a.pdf", language="hi-IN"
        )
    assert unknown.snapshot()["units"] == pytest.approx(1.0)  # reservation kept

    rejected = guard(max_units=10.0)
    with pytest.raises(SarvamJobError) as info:
        source(FakeDocAi([status("rejected")]), guard=rejected).digitize_bytes(
            make_pdf(2), file_name="a.pdf", language="hi-IN"
        )
    assert info.value.status == "rejected"
    assert rejected.snapshot()["units"] == 0


def test_poll_timeout_keeps_the_reservation_and_reports_the_job() -> None:
    doc_guard = guard(max_units=10.0)
    clock = Clock()
    fake = FakeDocAi([status("running")])
    src = source(
        fake,
        guard=doc_guard,
        clock=clock,
        poll_interval_seconds=4.0,
        poll_timeout_seconds=10.0,
    )
    with pytest.raises(SarvamJobTimeoutError) as info:
        src.digitize_bytes(make_pdf(1), file_name="a.pdf", language="hi-IN")
    assert info.value.job_id == "job-1"
    assert clock.sleeps == [4.0, 4.0, 2.0]
    assert fake.names().count("digitise") == 1 and "get_results" not in fake.names()
    assert doc_guard.snapshot()["units"] == pytest.approx(0.5)


def test_partial_results_and_strict_mode() -> None:
    partial = [status("partially_completed", usage(3, 3, 2, 1))]
    pages = [(1, "one"), (2, None), (3, "three")]
    result = source(FakeDocAi(partial, results(pages))).digitize_bytes(
        make_pdf(3), file_name="a.pdf", language="bn-IN"
    )
    assert [item.metadata["page_number"] for item in result.items] == [1, 3]
    assert result.missing_pages == (2,)
    assert (result.pages_total, result.pages_succeeded, result.pages_failed) == (3, 2, 1)
    assert all(item.metadata["job_status"] == "partially_completed" for item in result.items)

    strict_guard = guard(max_units=10.0)
    with pytest.raises(SarvamJobError) as info:
        source(
            FakeDocAi(partial, results(pages)), guard=strict_guard, allow_partial=False
        ).digitize_bytes(make_pdf(3), file_name="a.pdf", language="bn-IN")
    assert info.value.status == "partially_completed"
    assert strict_guard.snapshot()["units"] == pytest.approx(1.5)

    blank = source(FakeDocAi([status("completed")], results([(2, "  "), (1, "x")]))).digitize_bytes(
        make_pdf(2), file_name="a.pdf", language="bn-IN"
    )
    assert blank.missing_pages == (2,) and blank.pages_total is None


def test_billed_pages_fall_back_to_succeeded_plus_failed() -> None:
    doc_guard = guard(max_units=10.0)
    fake = FakeDocAi(
        [status("completed", usage(3, None, 2, 1))], results([(1, "a"), (2, "b"), (3, "c")])
    )
    result = source(fake, guard=doc_guard).digitize_bytes(
        make_pdf(3), file_name="a.pdf", language="hi-IN"
    )
    assert result.usage.quantity == 3 and result.usage.classification == "PROVIDER_REPORTED"
    assert doc_guard.snapshot()["units"] == pytest.approx(1.5)
    unknown = SimpleNamespace(pages_total=3, pages_processed=None, pages_succeeded=None)
    kept = guard(max_units=10.0)
    estimated = source(
        FakeDocAi([status("completed", unknown)], results([(1, "a")])), guard=kept
    ).digitize_bytes(make_pdf(3), file_name="a.pdf", language="hi-IN")
    assert estimated.usage.classification == "ESTIMATED" and estimated.usage.quantity == 3
    assert kept.snapshot()["units"] == pytest.approx(1.5)


def test_status_and_results_errors_carry_the_job_id() -> None:
    with pytest.raises(SarvamRateLimitError) as polled:
        source(FakeDocAi(status_error=_Failure(429))).digitize_bytes(
            PNG, file_name="a.png", language="hi-IN"
        )
    assert polled.value.job_id == "job-1"
    doc_guard = guard(max_units=10.0)
    fake = FakeDocAi([status("completed", usage(1, 1, 1, 0))], results_error=_Failure(503))
    with pytest.raises(SarvamServerError) as fetched:
        source(fake, guard=doc_guard).digitize_bytes(PNG, file_name="a.png", language="hi-IN")
    assert fetched.value.job_id == "job-1"
    assert doc_guard.snapshot()["units"] == pytest.approx(0.5)


@pytest.mark.parametrize(
    "fake",
    [
        FakeDocAi(started=SimpleNamespace(job_id="")),
        FakeDocAi([status("")]),
        FakeDocAi([SimpleNamespace(usage=None)]),
        FakeDocAi([status("completed")], SimpleNamespace(documents=None)),
        FakeDocAi([status("completed")], SimpleNamespace(documents=[SimpleNamespace(pages="x")])),
        FakeDocAi([status("completed")], results([(0, "bad number")])),
        FakeDocAi([status("completed")], results([(True, "bool number")])),
        FakeDocAi([status("completed")], results([(1, "a"), (1, "again")])),
        FakeDocAi([status("completed")], results([(1, b"bytes")])),
    ],
)
def test_malformed_responses_are_typed(fake: FakeDocAi) -> None:
    with pytest.raises(SarvamMalformedResponseError):
        source(fake).digitize_bytes(PNG, file_name="a.png", language="hi-IN")


def test_unknown_states_keep_polling_and_dict_results_parse() -> None:
    fake = FakeDocAi(
        [status("uploading"), {"status": "COMPLETED", "usage": {"pages_processed": 1}}],
        {
            "documents": [
                {"pages": None},
                {"pages": [{"page_number": 1, "content": "dict page"}]},
            ],
            "usage": {"pages_total": 1},
        },
    )
    result = source(fake).digitize_bytes(PNG, file_name="a.png", language="hi-IN")
    assert [item.item_id.split(":")[-2:] for item in result.items] == [["1", "1"]]
    assert result.usage.quantity == 1


# --------------------------------------------------------------------------- construction


def test_construction_defaults_env_and_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    src = SarvamDocumentSource(client=object())
    assert src.guard.limits == DEFAULT_DOCUMENT_LIMITS
    assert src.guard.name == DOCUMENT_GUARD_PREFIX
    assert src.max_pages_per_job == 10
    for kwargs, message in [
        ({"max_pages_per_job": 11}, "max_pages_per_job"),
        ({"max_pages_per_job": 0}, "max_pages_per_job"),
        ({"max_file_bytes": 201 * 1024 * 1024}, "max_file_bytes"),
        ({"max_file_bytes": True}, "max_file_bytes"),
        ({"poll_interval_seconds": 0}, "poll_interval_seconds"),
        ({"poll_timeout_seconds": -1}, "poll_timeout_seconds"),
        ({"timeout_seconds": True}, "timeout_seconds"),
    ]:
        with pytest.raises(ValueError, match=message):
            SarvamDocumentSource(client=object(), **kwargs)
    with pytest.raises(TypeError, match="prices"):
        SarvamDocumentSource(client=object(), prices=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires api_key"):
        SarvamDocumentSource()
    with pytest.raises(ValueError, match="requires api_key"):
        AsyncSarvamDocumentSource()

    for suffix in ("REQUESTS_PER_MINUTE", "MAX_REQUESTS"):
        monkeypatch.delenv(f"LLMSLIM_SARVAM_DOCUMENT_{suffix}", raising=False)
    monkeypatch.setenv("LLMSLIM_SARVAM_DOCUMENT_MAX_UNITS", "none")
    monkeypatch.setenv("TEST_SARVAM_KEY", SECRET)
    from_env = AsyncSarvamDocumentSource.from_env("TEST_SARVAM_KEY", client=object())
    assert from_env.guard.limits.max_units is None
    assert from_env.guard.limits.requests_per_minute == 10
    assert SECRET not in repr(from_env) and "<redacted>" in repr(from_env)
    own = guard()
    assert SarvamDocumentSource.from_env("TEST_SARVAM_KEY", client=object(), guard=own).guard is own


# --------------------------------------------------------------------------- async parity


def _async_source(fake: AsyncFakeDocAi, **kwargs: Any) -> AsyncSarvamDocumentSource:
    clock = kwargs.pop("clock", Clock())
    return AsyncSarvamDocumentSource(
        client=SimpleNamespace(doc_ai=fake), clock=clock, sleep=clock.asleep, **kwargs
    )


def test_async_source_parity(tmp_path: Path) -> None:
    data = make_pdf(2)
    path = tmp_path / "report.pdf"
    path.write_bytes(data)
    statuses = [status("running"), status("completed", usage(2, 2, 2, 0))]
    sync_result = source(FakeDocAi(statuses, results(TWO_PAGES))).digitize(path, language="hi-IN")
    clock = Clock()
    async_result = asyncio.run(
        _async_source(AsyncFakeDocAi(statuses, results(TWO_PAGES)), clock=clock).digitize(
            path, language="hi-IN"
        )
    )
    assert async_result == sync_result
    assert clock.sleeps == [5.0]

    with pytest.raises(SarvamJobTimeoutError):
        asyncio.run(
            _async_source(
                AsyncFakeDocAi([status("running")]), poll_timeout_seconds=1.0
            ).digitize_bytes(data, file_name="a.pdf", language="hi-IN")
        )
    doc_guard = guard(max_units=10.0)
    with pytest.raises(SarvamAuthenticationError):
        asyncio.run(
            _async_source(
                AsyncFakeDocAi(start_error=_Failure(403)), guard=doc_guard
            ).digitize_bytes(data, file_name="a.pdf", language="hi-IN")
        )
    assert doc_guard.snapshot()["units"] == 0
    with pytest.raises(SarvamServerError):
        asyncio.run(
            _async_source(
                AsyncFakeDocAi([status("completed")], results_error=_Failure(500))
            ).digitize_bytes(data, file_name="a.pdf", language="hi-IN")
        )
    with pytest.raises(SarvamRateLimitError):
        asyncio.run(
            _async_source(AsyncFakeDocAi(status_error=_Failure(429))).digitize_bytes(
                data, file_name="a.pdf", language="hi-IN"
            )
        )
    with pytest.raises(SarvamJobError):
        asyncio.run(
            _async_source(AsyncFakeDocAi([status("failed")])).digitize_bytes(
                data, file_name="a.pdf", language="hi-IN"
            )
        )


# --------------------------------------------------------------------------- pages without numbers


def test_pages_without_a_page_number_keep_their_text_by_position() -> None:
    # The SDK marks page_number optional. The job is billed by then, so the text is kept.
    doc_guard = guard(max_units=10.0)
    fake = FakeDocAi(
        [status("completed", usage(3, 3, 3, 0))],
        results([(None, "first"), (None, "second"), (3, "third")]),
    )
    result = source(fake, guard=doc_guard).digitize_bytes(PNG, file_name="a.png", language="hi-IN")
    assert [item.content for item in result.items] == ["first", "second", "third"]
    assert [item.metadata["page_number"] for item in result.items] == [1, 2, 3]
    assert [item.metadata.get("page_number_inferred", False) for item in result.items] == [
        True,
        True,
        False,
    ]
    assert result.missing_pages == ()
    assert doc_guard.snapshot()["units"] == pytest.approx(1.5)  # settled from reported pages


def test_an_inferred_page_number_never_collides_with_a_reported_one() -> None:
    fake = FakeDocAi(
        [status("completed", usage(2, 2, 2, 0))], results([(None, "unnumbered"), (1, "one")])
    )
    result = source(fake).digitize_bytes(PNG, file_name="a.png", language="hi-IN")
    numbers = {item.content: item.metadata["page_number"] for item in result.items}
    assert numbers == {"one": 1, "unnumbered": 2}
    assert len({item.item_id for item in result.items}) == 2
    inferred = [item for item in result.items if item.metadata.get("page_number_inferred")]
    assert [item.content for item in inferred] == ["unnumbered"]
