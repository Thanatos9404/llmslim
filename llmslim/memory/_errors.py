"""Telling a memory database that is down or unreachable apart from a request that failed for another reason."""

from __future__ import annotations

import sys

#: What a client is told when the memory's database can't be reached. It names no host, URL or driver.
UNAVAILABLE_MESSAGE = "the memory store can't be reached right now; try again shortly"


def store_unavailable(error: BaseException) -> bool:
    """Whether ``error`` means the memory's database is down or unreachable for now, so the same request may work
    later: a MongoDB connection failure or server selection timeout, or an error MongoDB labels transient; a Postgres
    connection error or pool timeout. A driver that was never imported is not looked at."""
    mongo = sys.modules.get("pymongo.errors")
    if mongo is not None:
        if isinstance(error, mongo.ConnectionFailure):
            return True
        if isinstance(error, mongo.PyMongoError) and error.has_error_label(
            "TransientTransactionError"
        ):
            return True
    psycopg = sys.modules.get("psycopg")
    return psycopg is not None and isinstance(error, psycopg.OperationalError)
