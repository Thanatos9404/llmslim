"""A MongoDB store for :class:`llmslim.memory.Memory`, through PyMongo.

``pip install "llmslim[mongodb]"``. Works with MongoDB 6.0 or newer, standalone or as a replica set, self-hosted or on
MongoDB Atlas. ``Memory("mongodb://...")`` uses it, and so do ``llmslim serve --db mongodb://...`` and
``llmslim mcp --db mongodb://...`` (``mongodb+srv://`` too).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence
from urllib.parse import unquote

from ._types import MemoryItem, Scope

__all__ = ["MongoStore", "is_mongodb_url"]

SCHEMA_VERSION = 1
_COLLECTION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,50}$")
_DATABASE = re.compile(r"^[A-Za-z0-9_-]{1,63}$")
# MongoDB's own databases: admin holds users, local is not replicated, config belongs to sharding.
_RESERVED_DATABASES = frozenset({"admin", "config", "local"})
_DEFAULT_DATABASE = "llmslim"
_SCOPE_FIELDS = ("user_id", "agent_id", "run_id")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MAX_DOCUMENT = 16 * 1024 * 1024  # the most one BSON document may hold
_MAX_DEPTH = 32  # metadata nested deeper than this is kept as JSON text
_INT64 = (-(2**63), 2**63 - 1)
# URL options whose values are credentials (tlsCertificateKeyFilePassword, authMechanismProperties=AWS_SESSION_TOKEN:...).
_SECRET_OPTION = re.compile(r"password|secret|token|authmechanismproperties", re.IGNORECASE)
_DUPLICATE_KEY = 11000
_INDEX_OPTIONS_CONFLICT = 85  # the same keys are already indexed under another name


def is_mongodb_url(value: Any) -> bool:
    """Whether ``value`` is a MongoDB connection URL (``mongodb://`` or ``mongodb+srv://``)."""
    return isinstance(value, str) and value.startswith(("mongodb://", "mongodb+srv://"))


def _missing_driver() -> ImportError:
    return ImportError('The MongoDB memory store needs pymongo: pip install "llmslim[mongodb]"')


class MongoStore:
    """Turns in one MongoDB collection.

    Pass a connection URL (``mongodb://user:password@host:27017/db``, or ``mongodb+srv://...`` for Atlas), in which
    case the store opens its own ``MongoClient`` and closes it in :meth:`close`; a ``pymongo.MongoClient``; or a
    ``pymongo.database.Database``. The store is safe to use from several threads, and several processes can share one
    collection.

    The collection (``llmslim_memory`` by default), its indexes and a ``<collection>_meta`` collection, which holds
    the schema version and the counter that orders turns, are created when the store opens if they don't exist.
    Creating them again changes nothing, so several processes can start at once. A collection written by a newer
    llmslim is refused rather than misread. On a replica set or a sharded cluster each :meth:`add` is one transaction,
    so a batch is stored whole or not at all, even if the connection drops partway. A standalone server has no
    transactions; there a batch that fails partway is undone instead. Reads go to the primary, so a turn is readable as
    soon as it is added.

    Every caller value is stored and matched as data: ids and scope values must be strings and are compared with
    ``$eq``, and metadata whose keys MongoDB would read as operators or paths (a leading ``$``, a ``.``) is kept as JSON
    text. Error messages from opening the store have the URL's password and secret options removed.

    Args:
        client: A ``mongodb://`` or ``mongodb+srv://`` URL, a ``MongoClient`` or a ``Database``.
        database: Database name: letters, digits, ``_`` and ``-``, and not ``admin``, ``local`` or ``config``. By
            default the URL's (or the client's) default database, else ``llmslim``. Leave it unset with a
            ``Database``.
        collection: Collection name: letters, digits and underscores. Use one per application or tenant if you like.
    """

    def __init__(
        self,
        client: Any,
        *,
        database: Optional[str] = None,
        collection: str = "llmslim_memory",
    ) -> None:
        try:
            from bson.codec_options import CodecOptions
            from pymongo import MongoClient, ReadPreference
            from pymongo.database import Database
        except ImportError as error:
            raise _missing_driver() from error
        if not isinstance(collection, str) or not _COLLECTION.match(collection):
            raise ValueError(
                "collection must be letters, digits and underscores, starting with a letter or underscore"
            )
        if database is not None:
            _check_database(database)
        self.collection = collection
        self._owned: Any = None
        secrets: List[str] = []
        if isinstance(client, str):
            if not is_mongodb_url(client):
                raise ValueError("the URL must start with mongodb:// or mongodb+srv://")
            secrets = _url_secrets(client)
        elif isinstance(client, Database):
            if database is not None:
                raise ValueError(
                    "pass database only with a URL or a MongoClient, not with a Database"
                )
            _check_database(client.name)
        elif not isinstance(client, MongoClient):
            raise TypeError(
                "client must be a mongodb:// URL, a pymongo.MongoClient or a pymongo.database.Database"
            )
        failure: Optional[BaseException] = None
        try:
            if isinstance(client, str):
                self._owned = MongoClient(client)
                client = self._owned
            if isinstance(client, Database):
                db = client
            else:
                db = client.get_database(
                    database or client.get_default_database(_DEFAULT_DATABASE).name
                )
                _check_database(db.name)
            self.database: str = db.name
            self._client: Any = db.client
            options: Any = CodecOptions(tz_aware=True, tzinfo=timezone.utc)
            self._turns: Any = db.get_collection(
                collection, codec_options=options, read_preference=ReadPreference.PRIMARY
            )
            self._meta: Any = db.get_collection(
                f"{collection}_meta", codec_options=options, read_preference=ReadPreference.PRIMARY
            )
            self._create_schema()
            self._transactions = _supports_transactions(db)
        except Exception as error:
            failure = _scrubbed(error, secrets)
            if failure is error:
                self.close()
                raise
        if failure is not None:
            # Raised outside the except block, so the original message (which held a secret) is not chained to it.
            self.close()
            raise failure

    # ------------------------------------------------------------------ connections

    def close(self) -> None:
        """Close the client the store opened for a URL. A client or database you passed in stays open."""
        if self._owned is not None:
            self._owned.close()

    def __enter__(self) -> "MongoStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"MongoStore(database={self.database!r}, collection={self.collection!r})"

    def _create_schema(self) -> None:
        from pymongo import ASCENDING

        _upsert(self._meta, "schema_version", {"$setOnInsert": {"value": SCHEMA_VERSION}})
        row = self._meta.find_one({"_id": "schema_version"})
        version = int(row["value"]) if row else SCHEMA_VERSION
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"collection {self.collection} uses memory schema {version}; this llmslim reads up to "
                f"{SCHEMA_VERSION}. Upgrade llmslim."
            )
        for field in _SCOPE_FIELDS:
            self._index(
                [(field, ASCENDING), ("created_at_us", ASCENDING), ("seq", ASCENDING)],
                f"{self.collection}_{field}",
            )
        self._index([("seq", ASCENDING)], f"{self.collection}_seq", unique=True)
        self._sync_counter()

    def _index(self, keys: List[Any], name: str, unique: bool = False) -> None:
        from pymongo.errors import OperationFailure

        options: Dict[str, Any] = {"name": name}
        if unique:
            options["unique"] = True
        try:
            self._turns.create_index(keys, **options)
        except OperationFailure as error:
            if error.code != _INDEX_OPTIONS_CONFLICT:
                raise

    def _sync_counter(self) -> None:
        """Make the order counter at least the highest ``seq`` stored (creating it if it is missing)."""
        from bson.int64 import Int64
        from pymongo import DESCENDING

        top = self._turns.find_one({}, {"seq": 1}, sort=[("seq", DESCENDING)])
        highest = int(top["seq"]) if top else 0
        _upsert(self._meta, "seq", {"$max": {"value": Int64(highest)}})

    def _reserve(self, count: int) -> int:
        """Take ``count`` consecutive ``seq`` values; return the first. One atomic update, so processes never share one."""
        from bson.int64 import Int64
        from pymongo import ReturnDocument

        for _ in range(3):
            row = self._meta.find_one_and_update(
                {"_id": "seq"},
                {"$inc": {"value": Int64(count)}},
                return_document=ReturnDocument.AFTER,
            )
            if row is not None:
                return int(row["value"]) - count + 1
            self._sync_counter()  # the counter was removed; rebuild it from the stored turns
        raise RuntimeError(f"could not reserve memory order numbers in {self.collection}_meta")

    # ------------------------------------------------------------------ MemoryStore

    def add(self, items: Sequence[MemoryItem]) -> None:
        if not items:
            return
        from bson.int64 import Int64
        from pymongo.errors import BulkWriteError

        # Everything is checked before anything is written.
        rows = [_document(item) for item in items]
        ids = [row["_id"] for row in rows]
        if len(set(ids)) != len(ids):
            raise ValueError("memory id already exists")
        start = self._reserve(len(rows))
        for offset, row in enumerate(rows):
            row["seq"] = Int64(start + offset)  # in the order the turns were given in
        try:
            if self._transactions:
                with self._client.start_session() as session:
                    session.with_transaction(
                        lambda s: self._turns.insert_many(rows, ordered=True, session=s)
                    )
            else:
                self._turns.insert_many(rows, ordered=True)
        except BulkWriteError as error:
            if not self._transactions:
                # Ordered inserts stop at the first failure; undo the ones before it so the batch leaves nothing behind.
                inserted = int(error.details.get("nInserted", 0))
                if inserted:
                    self._turns.delete_many({"_id": {"$in": ids[:inserted]}})
            if any(_id_conflict(failure) for failure in error.details.get("writeErrors", [])):
                # Not chained: the driver's message repeats the whole turn.
                raise ValueError("memory id already exists") from None
            raise

    def list(
        self, scope: Scope, *, since: Optional[datetime] = None, until: Optional[datetime] = None
    ) -> List[MemoryItem]:
        query = _scope_filter(scope)
        window: Dict[str, int] = {}
        if since is not None:
            window["$gte"] = _micros(since, "since")
        if until is not None:
            window["$lt"] = _micros(until, "until")
        if window:
            query["created_at_us"] = window
        cursor = self._turns.find(query, sort=[("created_at_us", 1), ("seq", 1)])
        return [_item(row) for row in cursor]

    def get(self, item_id: str) -> Optional[MemoryItem]:
        row = self._turns.find_one({"_id": {"$eq": _text(item_id, "memory id")}})
        return _item(row) if row else None

    def update(
        self,
        item_id: str,
        *,
        content: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        from bson.int64 import Int64
        from pymongo import ReturnDocument

        item_id = _text(item_id, "memory id")
        now = datetime.now(timezone.utc)
        changes: Dict[str, Any] = {"updated_at": now, "updated_at_us": Int64(_micros(now, "now"))}
        removed: Dict[str, str] = {}
        if content is not None:
            changes["content"] = _text(content, "content")
        if metadata is not None:
            stored = _metadata_fields(metadata)
            changes.update(stored)
            removed["metadata_json" if "metadata" in stored else "metadata"] = ""
        _check_size(changes)
        update: Dict[str, Any] = {"$set": changes}
        if removed:
            update["$unset"] = removed
        row = self._turns.find_one_and_update(
            {"_id": {"$eq": item_id}}, update, return_document=ReturnDocument.AFTER
        )
        return _item(row) if row else None

    def delete(self, item_id: str) -> bool:
        result = self._turns.delete_one({"_id": {"$eq": _text(item_id, "memory id")}})
        return bool(result.deleted_count)

    def delete_scope(self, scope: Scope) -> int:
        return int(self._turns.delete_many(_scope_filter(scope)).deleted_count)


# ---------------------------------------------------------------------- documents


def _text(value: Any, name: str) -> str:
    """A caller's string, refused if it is not one or is not valid Unicode (BSON, like SQLite, holds only UTF-8)."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, not {type(value).__name__}")
    if not value.isascii():
        value.encode(
            "utf-8"
        )  # a lone surrogate raises UnicodeEncodeError (a ValueError), as in SQLiteStore
    return value


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime, not {type(value).__name__}")
    if value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    try:  # 0001-01-01T00:00+05:00 has no UTC time; stored, it would break every read of its scope
        return value.astimezone(timezone.utc)
    except OverflowError:
        raise ValueError("timestamp is out of range") from None


def _micros(value: Any, name: str) -> int:
    """Microseconds since 1970 in UTC: exact, where a BSON date keeps only milliseconds."""
    delta = _utc(value, name) - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def _from_micros(value: int) -> datetime:
    return _EPOCH + timedelta(microseconds=int(value))


def _id_conflict(failure: Mapping[str, Any]) -> bool:
    if failure.get("code") != _DUPLICATE_KEY:
        return False
    pattern = failure.get("keyPattern")
    return "_id" in pattern if pattern else "_id_" in str(failure.get("errmsg", ""))


def _scope_filter(scope: Scope) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    for name in _SCOPE_FIELDS:
        value = getattr(scope, name)
        if value is not None:
            query[name] = {"$eq": _text(value, name)}
    if not query:  # an empty filter would match, or delete, everyone's memory
        raise ValueError("set at least one of user_id, agent_id or run_id")
    return query


def _document(item: MemoryItem) -> Dict[str, Any]:
    from bson.int64 import Int64

    created = _utc(item.created_at, "created_at")
    updated = _utc(item.updated_at, "updated_at") if item.updated_at is not None else None
    row: Dict[str, Any] = {
        "_id": _text(item.id, "memory id"),
        "seq": None,
        "role": _text(item.role, "role"),
        "content": _text(item.content, "content"),
        # The date is for people and tools reading the collection; the exact time, which reads use, is the integer.
        "created_at": created,
        "created_at_us": Int64(_micros(created, "created_at")),
        "updated_at": updated,
        "updated_at_us": Int64(_micros(updated, "updated_at")) if updated is not None else None,
    }
    for name in _SCOPE_FIELDS:
        value = getattr(item, name)
        row[name] = _text(value, name) if value is not None else None
    row.update(_metadata_fields(item.metadata))
    _check_size(row)
    return row


def _metadata_fields(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Metadata as MongoDB stores it: a document when MongoDB can hold its keys as plain names, else JSON text.

    It goes through JSON first, so it holds what SQLiteStore and PostgresStore hold: the same values are accepted, and
    the same come back (tuples as lists, numeric keys as strings).
    """
    if not isinstance(metadata, Mapping):
        raise TypeError(f"metadata must be a mapping, not {type(metadata).__name__}")
    text = _text(
        json.dumps(dict(metadata), ensure_ascii=False), "metadata"
    )  # keys and values, at any depth
    value = json.loads(text)
    return {"metadata": value} if _plain(value) else {"metadata_json": text}


def _plain(value: Any) -> bool:
    """Whether MongoDB can hold ``value`` as a document whose keys are only data.

    A key that starts with ``$`` reads as an operator and one with a ``.`` as a path, a NUL can't be stored in a key,
    an integer past 64 bits has no BSON type, and very deep nesting reaches MongoDB's limit.
    """
    stack = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if isinstance(current, dict):
            if depth >= _MAX_DEPTH:
                return False
            for key, child in current.items():
                if not key or key.startswith("$") or "." in key or "\x00" in key:
                    return False
                stack.append((child, depth + 1))
        elif isinstance(current, list):
            if depth >= _MAX_DEPTH:
                return False
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, int) and not isinstance(current, bool):
            if not _INT64[0] <= current <= _INT64[1]:
                return False
    return True


def _check_size(row: Mapping[str, Any]) -> None:
    """Refuse a turn MongoDB can't hold before anything is written. Only a large turn is encoded to measure it."""
    rough = 0
    for value in row.values():
        if isinstance(value, str):
            rough += 4 * len(value)  # a code point is at most 4 bytes of UTF-8
        elif isinstance(value, (dict, list)):
            rough += 4 * len(json.dumps(value))
        else:
            rough += 64
    if rough <= _MAX_DOCUMENT:
        return
    import bson

    if len(bson.encode(dict(row))) > _MAX_DOCUMENT:
        raise ValueError("a stored turn can be at most 16 MB in MongoDB (one BSON document)")


def _plain_value(value: Any) -> Any:
    """A decoded value as plain Python: BSON int64 comes back as ``bson.int64.Int64``."""
    if isinstance(value, dict):
        return {key: _plain_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_plain_value(child) for child in value]
    if isinstance(value, int) and not isinstance(value, bool) and type(value) is not int:
        return int(value)
    return value


def _metadata_of(row: Mapping[str, Any]) -> Dict[str, Any]:
    text = row.get("metadata_json")
    if text is not None:
        loaded: Dict[str, Any] = json.loads(text)
        return loaded
    return _plain_value(row.get("metadata") or {})


def _item(row: Mapping[str, Any]) -> MemoryItem:
    updated = row.get("updated_at_us")
    return MemoryItem(
        id=row["_id"],
        seq=int(row["seq"]),
        role=row["role"],
        content=row["content"],
        created_at=_from_micros(row["created_at_us"]),
        updated_at=_from_micros(updated) if updated is not None else None,
        user_id=row.get("user_id"),
        agent_id=row.get("agent_id"),
        run_id=row.get("run_id"),
        metadata=_metadata_of(row),
    )


# ---------------------------------------------------------------------- setup helpers


def _check_database(name: Any) -> None:
    if not isinstance(name, str) or not _DATABASE.match(name):
        raise ValueError("database must be 1 to 63 letters, digits, underscores or hyphens")
    if name in _RESERVED_DATABASES:
        raise ValueError(
            f"use a database of your own, not {name!r} (to log in against admin, add authSource=admin to the URL)"
        )


def _supports_transactions(db: Any) -> bool:
    """Whether the server is a replica set member or a mongos, the deployments that have multi-document transactions."""
    reply = db.command("hello")
    return bool(reply.get("setName")) or reply.get("msg") == "isdbgrid"


def _upsert(collection: Any, key: str, update: Mapping[str, Any]) -> None:
    from pymongo.errors import DuplicateKeyError

    try:
        collection.update_one({"_id": key}, update, upsert=True)
    except (
        DuplicateKeyError
    ):  # another process created it at the same moment; now it exists, so update it
        collection.update_one({"_id": key}, update, upsert=True)


def _url_secrets(url: str) -> List[str]:
    """What must not appear in an error message about ``url``: its password and its secret options, as written and
    decoded. Longest first, so a secret that contains another is removed whole."""
    rest = url.split("://", 1)[1]
    found: List[str] = []
    at = rest.rfind("@")
    if at >= 0:
        password = rest[:at].partition(":")[2]
        found += [password, unquote(password)]
    query = rest.partition("?")[2]
    for option in re.split(r"[&;]", query):
        name, _, value = option.partition("=")
        if _SECRET_OPTION.search(name):
            found += [value, unquote(value)]
    return sorted({secret for secret in found if secret}, key=len, reverse=True)


def _scrub(message: str, secrets: Sequence[str]) -> str:
    for secret in secrets:
        message = message.replace(secret, "<redacted>")
    return message


def _scrubbed(error: BaseException, secrets: Sequence[str]) -> BaseException:
    """``error`` itself when its message holds no secret; otherwise an error of the same type without them."""
    message = str(error)
    clean = _scrub(message, secrets)
    if clean == message and not any(secret in repr(error.args) for secret in secrets):
        return error
    try:
        return type(error)(clean)
    except Exception:  # an exception type whose constructor wants more than a message
        return RuntimeError(clean)
