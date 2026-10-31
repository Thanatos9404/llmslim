"""Bounded, streaming readers for history files from outside LLMSlim (see :func:`llmslim.memory.import_history`).

Every file is untrusted. Nothing here extracts, executes or evaluates anything, and every read is bounded:

* a file (or the zip member read) is at most ``max_file_bytes``, counted as it is read, not only from its size;
* JSONL is read line by line, each line at most ``max_record_bytes``: a longer one is skipped without holding it;
* a JSON document is read in chunks, one array element at a time, so a 500 MB ``conversations.json`` never sits in
  memory whole. Each element is at most ``max_record_bytes``;
* nesting is measured before a record is parsed, so a nesting bomb is skipped, not handed to the parser;
* a zip archive is read in place: its entry names are checked for path traversal, the entry read is checked against
  ``max_file_bytes`` and ``max_zip_ratio``, and nothing is written to disk.
"""

from __future__ import annotations

import codecs
import json
import re
import zipfile
import zlib
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

from ._import_types import HistoryImportError, ImportLimits

OK = "ok"
MALFORMED = "malformed"
TOO_LARGE = "too_large"
TOO_DEEP = "too_deep"

Record = Tuple[str, Any]  # (status, value): value is the parsed JSON when status is OK, else None

_CHUNK = 1 << 20
_KIB, _MIB, _GIB = 1 << 10, 1 << 20, 1 << 30
_UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
_ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06")
_INT_DIGITS = (
    64  # a longer JSON integer is malformed: int() of a huge one is slow on older 3.10 releases
)

# Outside a string, the characters that change nesting or open a string; inside one, the characters that end or escape.
_OUTSIDE = re.compile(r'["\[\]{}]')
_INSIDE = re.compile(r'["\\]')
_SCALAR_END = re.compile(r"[ \t\n\r,\]}]")
_WHITESPACE = re.compile(r"[ \t\n\r]*")
_DRIVE = re.compile(r"^[A-Za-z]:")


def size_text(count: int) -> str:
    """A byte count for people: 1 GiB, 32 MiB, 512 KiB or 100 bytes."""
    for unit, name in ((_GIB, "GiB"), (_MIB, "MiB"), (_KIB, "KiB")):
        if count >= unit:
            return f"{count / unit:.3g} {name}"
    return f"{count} bytes"


class _Truncated(Exception):
    """The input ended inside a value."""


class BoundedStream:
    """A binary stream that fails once more than ``limit`` bytes have been read from it."""

    def __init__(self, raw: Any, name: str, limit: int) -> None:
        self._raw = raw
        self.name = name
        self._limit = limit
        self.consumed = 0

    def _count(self, data: bytes) -> bytes:
        self.consumed += len(data)
        if self.consumed > self._limit:
            raise HistoryImportError(
                f"{self.name} is larger than the {size_text(self._limit)} file limit (max_file_bytes)"
            )
        return data

    def read(self, size: int) -> bytes:
        return self._count(self._raw.read(size))

    def readline(self, size: int) -> bytes:
        return self._count(self._raw.readline(size))


# --------------------------------------------------------------------------- opening files


def _stat_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError as error:
        raise HistoryImportError(f"can't read {path}: {error.strerror or error}") from error


@contextmanager
def open_file(path: Path, limits: ImportLimits) -> Iterator[BoundedStream]:
    """A regular file, opened for bounded binary reads."""
    if not path.exists():
        raise HistoryImportError(f"{path} does not exist")
    if not path.is_file():
        raise HistoryImportError(f"{path} is not a regular file")
    size = _stat_size(path)
    if size > limits.max_file_bytes:
        raise HistoryImportError(
            f"{path} is {size_text(size)}, over the {size_text(limits.max_file_bytes)} file limit (max_file_bytes)"
        )
    try:
        handle = open(path, "rb")  # closed by the with block below
    except OSError as error:
        raise HistoryImportError(f"can't read {path}: {error.strerror or error}") from error
    with handle:
        yield BoundedStream(handle, str(path), limits.max_file_bytes)


def is_zip(path: Path) -> bool:
    """Whether ``path`` starts like a zip archive (checked by its first bytes, not its name)."""
    try:
        with open(path, "rb") as handle:
            return handle.read(4) in _ZIP_MAGIC
    except OSError:
        return False


def _unsafe_member(name: str) -> bool:
    """An entry name that would escape a folder it was extracted to: absolute, with a drive, or with ``..``."""
    normal = name.replace("\\", "/")
    return (
        "\x00" in name
        or normal.startswith("/")
        or bool(_DRIVE.match(normal))
        or ".." in normal.split("/")
    )


@contextmanager
def open_zip_member(path: Path, wanted: str, limits: ImportLimits) -> Iterator[BoundedStream]:
    """The entry named ``wanted`` (at the top of the archive, or in its shallowest folder), read in place.

    The archive is refused as a whole when it lists more than ``max_zip_members`` entries or any entry name that would
    escape an extraction folder, and the entry when it is encrypted, larger than ``max_file_bytes`` or compressed more
    than ``max_zip_ratio`` times (a zip bomb). Its bytes are counted as they are read, so an entry that is larger
    than its header says still stops at the limit.
    """
    size = _stat_size(path)
    if size > limits.max_file_bytes:
        raise HistoryImportError(
            f"{path} is {size_text(size)}, over the {size_text(limits.max_file_bytes)} file limit (max_file_bytes)"
        )
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        raise HistoryImportError(f"{path} is not a readable zip archive: {error}") from error
    with archive:
        entries = archive.infolist()
        if len(entries) > limits.max_zip_members:
            raise HistoryImportError(
                f"{path} lists {len(entries)} entries, over the {limits.max_zip_members} limit (max_zip_members)"
            )
        for entry in entries:
            if _unsafe_member(entry.filename):
                raise HistoryImportError(
                    f"{path} has an unsafe entry name {entry.filename!r} (an absolute path or '..'); "
                    "the archive was not read"
                )
        found = [
            entry
            for entry in entries
            if not entry.is_dir()
            and PurePosixPath(entry.filename.replace("\\", "/")).name == wanted
        ]
        if not found:
            raise HistoryImportError(f"{path} has no {wanted}")
        entry = min(found, key=lambda e: (e.filename.replace("\\", "/").count("/"), e.filename))
        where = f"{path}!{entry.filename}"
        if entry.flag_bits & 0x1:
            raise HistoryImportError(f"{where} is encrypted; export it again without a password")
        if entry.file_size > limits.max_file_bytes:
            raise HistoryImportError(
                f"{where} is {size_text(entry.file_size)} uncompressed, over the "
                f"{size_text(limits.max_file_bytes)} file limit (max_file_bytes)"
            )
        ratio = entry.file_size / max(entry.compress_size, 1)
        if entry.file_size > _MIB and ratio > limits.max_zip_ratio:
            raise HistoryImportError(
                f"{where} expands {ratio:.0f} times ({size_text(entry.compress_size)} to "
                f"{size_text(entry.file_size)}), over the {limits.max_zip_ratio:g}x limit (max_zip_ratio): "
                "it looks like a zip bomb and was not read"
            )
        try:
            member = archive.open(entry)
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError) as error:
            raise HistoryImportError(f"can't read {where}: {error}") from error
        with member:
            stream = BoundedStream(member, where, limits.max_file_bytes)
            try:
                yield stream
            except (
                zipfile.BadZipFile,
                EOFError,
                zlib.error,
            ) as error:  # a damaged entry or a CRC mismatch
                raise HistoryImportError(f"can't read {where}: {error}") from error


@contextmanager
def open_export(path: Path, wanted: str, limits: ImportLimits) -> Iterator[BoundedStream]:
    """``wanted`` (such as ``conversations.json``) from an export: the zip archive as downloaded, the folder it was
    extracted to, or the file itself."""
    if path.is_dir():
        inside = path / wanted
        if not inside.is_file():
            raise HistoryImportError(f"{path} has no {wanted}")
        path = inside
    if path.is_file() and is_zip(path):
        with open_zip_member(path, wanted, limits) as stream:
            yield stream
    else:
        with open_file(path, limits) as stream:
            yield stream


# --------------------------------------------------------------------------- parsing


def _parse_int(text: str) -> int:
    if len(text.lstrip("-")) > _INT_DIGITS:
        raise ValueError("integer too long")
    return int(text)


def _loads(text: str) -> Record:
    try:
        return OK, json.loads(text, parse_int=_parse_int)
    except (ValueError, RecursionError):
        return MALFORMED, None


def too_deep(text: str, max_depth: int) -> bool:
    """Whether arrays and objects in the JSON ``text`` nest deeper than ``max_depth`` (strings are skipped)."""
    if text.count("[") + text.count("{") <= max_depth:
        return False
    depth = 0
    at = 0
    while True:
        found = _OUTSIDE.search(text, at)
        if found is None:
            return False
        char, at = found.group(), found.end()
        if char == '"':
            while True:
                end = _INSIDE.search(text, at)
                if end is None:
                    return False  # an unterminated string: the parser rejects it
                at = end.end()
                if end.group() == '"':
                    break
                at += 1  # the escaped character
        elif char in "[{":
            depth += 1
            if depth > max_depth:
                return True
        else:
            depth -= 1


def parse_record(text: str, limits: ImportLimits) -> Record:
    """One JSON record (a JSONL line), with its nesting checked before it is parsed."""
    if too_deep(text, limits.max_depth):
        return TOO_DEEP, None
    return _loads(text)


def iter_jsonl(stream: BoundedStream, limits: ImportLimits) -> Iterator[Tuple[int, Record]]:
    """(line number, record) for each non-blank line: UTF-8 with or without a BOM, LF or CRLF endings. A line over
    ``max_record_bytes`` is skipped as it is read, never held whole."""
    cap = limits.max_record_bytes
    number = 0
    while True:
        line = stream.readline(cap + 1)
        if not line:
            return
        number += 1
        if number == 1:
            if line.startswith(_UTF16_BOMS):
                raise HistoryImportError(
                    f"{stream.name} is UTF-16 text; save it as UTF-8 and import it again"
                )
            if line.startswith(codecs.BOM_UTF8):
                line = line[len(codecs.BOM_UTF8) :]
        if len(line) > cap and not line.endswith(b"\n"):
            while True:  # the rest of the long line, discarded as it is read
                rest = stream.readline(_CHUNK)
                if not rest or rest.endswith(b"\n"):
                    break
            yield number, (TOO_LARGE, None)
            continue
        body = line.rstrip(b"\r\n")
        if not body.strip():
            continue
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            yield number, (MALFORMED, None)
            continue
        yield number, parse_record(text, limits)


class _Document:
    """A JSON document read in chunks, value by value, without holding more than one top-level record."""

    def __init__(self, stream: BoundedStream, limits: ImportLimits) -> None:
        self.stream = stream
        self.limits = limits
        self.decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
        self.buf = ""
        self.pos = 0
        self.base = 0  # characters dropped from the front of buf
        self.eof = False
        self.started = False

    def error(self, problem: str) -> HistoryImportError:
        return HistoryImportError(
            f"{self.stream.name} is not valid JSON at character {self.base + self.pos}: {problem}"
        )

    def more(self) -> bool:
        """Read the next chunk into the buffer. False at the end of the input."""
        if self.eof:
            return False
        chunk = self.stream.read(_CHUNK)
        if not self.started:
            self.started = True
            if chunk.startswith(_UTF16_BOMS):
                raise HistoryImportError(
                    f"{self.stream.name} is UTF-16 text; save it as UTF-8 and import it again"
                )
        try:
            self.buf += self.decoder.decode(chunk, final=not chunk)
        except UnicodeDecodeError as error:
            raise HistoryImportError(
                f"{self.stream.name} is not UTF-8 text (near byte {self.stream.consumed})"
            ) from error
        if not chunk:
            self.eof = True
        return True

    def compact(self) -> None:
        if self.pos:
            self.base += self.pos
            self.buf = self.buf[self.pos :]
            self.pos = 0

    def skip_space(self) -> bool:
        """Move past whitespace. False at the end of the input."""
        while True:
            self.pos = _WHITESPACE.match(self.buf, self.pos).end()  # type: ignore[union-attr]
            if self.pos < len(self.buf):
                return True
            if not self.more():
                return False

    def next_char(self) -> str:
        if not self.skip_space():
            raise _Truncated
        return self.buf[self.pos]

    def value(self) -> Tuple[str, Optional[str]]:
        """The next value's text, or a status without it when it is over ``max_record_bytes`` or nests deeper than
        ``max_depth`` (it is then read past, never held)."""
        self.next_char()
        self.compact()
        cap = self.limits.max_record_bytes
        if self.buf[0] not in '[{"':
            while True:
                found = _SCALAR_END.search(self.buf, 0)
                if found is not None:
                    end = found.start()
                    break
                if len(self.buf) > cap:
                    raise self.error("a value over the record limit (max_record_bytes)")
                if not self.more():
                    end = len(self.buf)
                    break
            self.pos = end
            return OK, self.buf[:end]
        depth, inside, escaped = 0, False, False
        large = deep = False
        at = 0
        buf = self.buf
        while True:
            if inside:
                if escaped:
                    if at < len(buf):
                        at += 1
                        escaped = False
                        continue
                else:
                    found = _INSIDE.search(buf, at)
                    if found is not None:
                        at = found.end()
                        if found.group() == "\\":
                            escaped = True
                        else:
                            inside = False
                            if depth == 0:
                                break
                        continue
            else:
                found = _OUTSIDE.search(buf, at)
                if found is not None:
                    char, at = found.group(), found.end()
                    if char == '"':
                        inside = True
                    elif char in "[{":
                        depth += 1
                        if depth > self.limits.max_depth:
                            deep = True
                    else:
                        depth -= 1
                        if depth == 0:
                            break
                    continue
            # The buffer is used up inside the value: read on.
            if not (large or deep) and len(buf) > cap:
                large = True
            if large or deep:  # nothing of it is kept: drop what was read
                self.base += len(buf)
                self.buf = ""
                at = 0
            if not self.more():
                raise _Truncated
            buf = self.buf
        if at > cap:
            large = True
        self.pos = at
        if deep:
            return TOO_DEEP, None
        if large:
            return TOO_LARGE, None
        return OK, buf[:at]

    def array(self) -> Iterator[Record]:
        """The elements of the array whose ``[`` was just read."""
        first = True
        while True:
            char = self.next_char()
            if char == "]":
                self.pos += 1
                return
            if not first:
                if char != ",":
                    raise self.error("expected ',' or ']' between array elements")
                self.pos += 1
                if self.next_char() == "]":
                    raise self.error("a trailing comma")
            first = False
            status, text = self.value()
            yield _loads(text) if status == OK and text is not None else (status, None)

    def object(self, list_keys: Sequence[str]) -> Iterator[Record]:
        """The object whose ``{`` was just read: the elements of its first array under one of ``list_keys``, or else
        the whole object as one record."""
        kept: Dict[str, str] = {}
        size = 0
        problem: Optional[str] = None
        streamed = False
        first = True
        while True:
            char = self.next_char()
            if char == "}":
                self.pos += 1
                break
            if not first:
                if char != ",":
                    raise self.error("expected ',' or '}' between members")
                self.pos += 1
                self.next_char()
            first = False
            status, key_text = self.value()
            if status != OK or not key_text or not key_text.startswith('"'):
                raise self.error("expected a member name")
            parsed_status, key = _loads(key_text)
            if parsed_status != OK:
                raise self.error("an invalid member name")
            if self.next_char() != ":":
                raise self.error("expected ':' after a member name")
            self.pos += 1
            if key in list_keys and not streamed and self.next_char() == "[":
                self.pos += 1
                streamed = True
                yield from self.array()
                continue
            status, text = self.value()
            if streamed:
                continue  # beside the list (a count, a next-page link): not a record
            if status != OK or text is None:
                problem = problem or status
                continue
            size += len(text)
            if size > self.limits.max_record_bytes:
                problem = problem or TOO_LARGE
                kept.clear()
            elif problem is None:
                kept[key] = text
        if streamed:
            return
        if problem is not None:
            yield problem, None
            return
        record: Dict[str, Any] = {}
        for key, text in kept.items():
            status, value = _loads(text)
            if status != OK:
                yield MALFORMED, None
                return
            record[key] = value
        yield OK, record


def iter_document(
    stream: BoundedStream, limits: ImportLimits, list_keys: Sequence[str] = ()
) -> Iterator[Record]:
    """The records of a JSON document: the elements of a top-level array; or, for a top-level object, the elements of
    its array under one of ``list_keys`` (Mem0's ``{"results": [...]}``), or else the object itself. An empty file
    has no records. A document cut short yields one ``MALFORMED`` record after the complete ones."""
    document = _Document(stream, limits)
    try:
        if not document.skip_space():
            return
        char = document.buf[document.pos]
        document.pos += 1
        if char == "[":
            yield from document.array()
        elif char == "{":
            yield from document.object(list_keys)
        else:
            document.pos -= 1
            raise document.error("expected a JSON array or object")
        if document.skip_space():
            yield MALFORMED, None  # something after the document
    except _Truncated:
        yield MALFORMED, None
