"""Tests for the website's /api/studio function."""

from __future__ import annotations

import importlib.util
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

API_PATH = Path(__file__).resolve().parents[1] / "web" / "api" / "studio.py"
SPEC = importlib.util.spec_from_file_location("studio_lab_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
studio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(studio)

FILLER = [
    "User: How do I download last month's statement? Agent: Open Statements and choose Download PDF.",
    "User: The app logs me out when I switch apps. Agent: Version 4.2.3 keeps your session for 30 days.",
    "User: Can I set a monthly spending limit? Agent: Yes, from Card settings, then Limits.",
    "User: Why was I charged a foreign fee? Agent: The merchant billed in US dollars.",
]
HISTORY = "\n".join(
    [f"Session {i + 1}\n{FILLER[i % len(FILLER)]}" for i in range(12)]
    + ["Session 13\nUser: I moved to Pune. Ship any new card to Koregaon Park, Pune. Agent: Updated."]
    + [f"Session {i + 14}\n{FILLER[(i + 1) % len(FILLER)]}" for i in range(12)]
)


def test_segments_rebuild_the_original_exactly() -> None:
    pieces = studio.segments(HISTORY, "Ship any new card to Koregaon Park, Pune.")
    assert "".join(piece for piece, _ in pieces) == HISTORY
    kept = [piece for piece, keep in pieces if keep and piece.strip()]
    assert any("Koregaon Park" in piece for piece in kept)


def test_cut_to_keeps_the_head_or_the_tail_within_budget() -> None:
    head = studio.cut_to(HISTORY, 40, "head")
    tail = studio.cut_to(HISTORY, 40, "tail")
    assert HISTORY.startswith(head) and HISTORY.endswith(tail)
    assert studio.count_tokens(head) <= 40 and studio.count_tokens(tail) <= 40
    assert studio.cut_to("short text", 40, "head") == "short text"


def test_run_compresses_around_the_question() -> None:
    data = studio.run({"text": HISTORY, "question": "Where should the new card be shipped?", "keep": 0.25, "baseline": "tail"})
    assert data["kept_tokens"] < data["original_tokens"]
    assert "Koregaon Park" in data["compressed_text"]
    assert "".join(piece for piece, _ in data["segments"]) == HISTORY
    assert data["baseline"]["keep"] == "tail"
    assert data["baseline"]["tokens"] <= data["kept_tokens"]
    assert isinstance(data["elapsed_ms"], float)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"text": ""}, "missing_text"),
        ({"text": "x", "keep": 0.9}, "invalid_keep"),
        ({"text": "x", "keep": True}, "invalid_keep"),
        ({"text": "x", "baseline": "middle"}, "invalid_baseline"),
        ({"text": "x", "question": "q" * 501}, "invalid_question"),
        ({"text": "x", "model": "anything"}, "unknown_fields"),
        ({"text": "x" * (studio.MAX_INPUT_CHARS + 1)}, "text_too_long"),
    ],
)
def test_run_rejects_bad_input(payload: dict[str, object], code: str) -> None:
    with pytest.raises(studio.RequestProblem) as problem:
        studio.run(payload)
    assert problem.value.code == code


def test_rate_limit_resets_after_the_window() -> None:
    key = "test-client"
    studio._request_windows.pop(key, None)
    assert all(studio.allow_request(key, now=1.0) for _ in range(studio.RATE_LIMIT_MAX_REQUESTS))
    assert not studio.allow_request(key, now=1.0)
    assert studio.allow_request(key, now=1.0 + studio.RATE_LIMIT_WINDOW_SECONDS + 0.1)


def test_handler_round_trip() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), studio.handler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
        body = json.dumps({"text": HISTORY, "question": "Where should the new card be shipped?", "keep": 0.3})
        connection.request("POST", "/api/studio", body=body, headers={"content-type": "application/json"})
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Cache-Control") == "no-store"
        assert "data" in json.loads(response.read())
        connection.request("POST", "/api/studio", body="{}", headers={"content-type": "text/plain"})
        response = connection.getresponse()
        assert response.status == 415
        response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
