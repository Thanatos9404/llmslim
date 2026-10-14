"""Local metering proxy for the third-party systems in the round-3 benchmarks (Mem0, Graphiti/Zep).

Every Claude call those libraries make goes through here, so they are held to the same rules as our own runs:

- the model is pinned to claude-haiku-5-5, whatever the library asks for, and the sampling parameters Haiku 5.5
  rejects (temperature, top_p, top_k) are dropped;
- the real key is added here (the libraries only ever see a dummy key);
- a long system prompt is marked cacheable (cache_control), which lowers the bill without changing the output;
- each call is priced at Haiku 5.5 list rates and added to the shared spend ledger, and calls stop at the cap;
- each call is logged with its tag (header ``x-bench-tag``), tokens, cost and time, so ingestion cost can be
  reported per system.

It listens on 127.0.0.1 only. Rate-limit (429) and overload (529) responses are retried here with backoff, so a
library without retries is not penalised for the shared account's limits.

  LLMSLIM_KEY_FILE=... HAIKU_LEDGER_DIR=... HAIKU_CAP_USD=60 HAIKU_SUITE=mem0-locomo \
      python meter_proxy.py --port 8787
  clients: ANTHROPIC_BASE_URL=http://127.0.0.1:8787  ANTHROPIC_API_KEY=unused
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

MODEL = "claude-haiku-5-5"
UPSTREAM = "https://api.anthropic.com"
LONG_PROMPT = 100_000
RATES = {False: (0.10, 0.50), True: (0.50, 2.50)}  # USD per million tokens, by prompt length
FORWARD_HEADERS = ("anthropic-version", "anthropic-beta", "content-type")
SAMPLING = ("temperature", "top_p", "top_k")
CACHE_MIN_CHARS = 8_000  # about 2k tokens, Haiku's minimum cacheable prompt

LEDGER_DIR = Path(os.environ.get("HAIKU_LEDGER_DIR", Path(__file__).parent))
SUITE = re.sub(r"[^a-z0-9_-]", "", os.environ.get("HAIKU_SUITE", "proxy").lower()) or "proxy"
LEDGER = LEDGER_DIR / f"spend-{SUITE}.json"
CALLS = LEDGER_DIR / f"calls-{SUITE}.jsonl"
CAP_USD = float(os.environ.get("HAIKU_CAP_USD", "3.00"))
LOCK = threading.Lock()


def settings() -> dict[str, str]:
    values = {}
    for line in Path(os.environ["LLMSLIM_KEY_FILE"]).read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if value.strip() and not name.lstrip().startswith("#"):
            values[name.strip()] = value.strip()
    if "CLAUDE_API_KEY" not in values:
        raise SystemExit("no CLAUDE_API_KEY in the key file")
    return values


def read_ledger(path: Path) -> dict:
    for _ in range(5):
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            time.sleep(0.05)
    return {"usd": 0.0, "calls": 0}


def spent() -> float:
    return sum(read_ledger(path).get("usd", 0.0) for path in LEDGER_DIR.glob("spend*.json"))


def price(usage: dict) -> float:
    cache_write = usage.get("cache_creation_input_tokens") or 0
    cache_read = usage.get("cache_read_input_tokens") or 0
    prompt = (usage.get("input_tokens") or 0) + cache_write + cache_read
    price_in, price_out = RATES[prompt > LONG_PROMPT]
    return (
        (usage.get("input_tokens") or 0) * price_in
        + (usage.get("output_tokens") or 0) * price_out
        + cache_write * price_in * 1.25
        + cache_read * price_in * 0.10
    ) / 1_000_000


def cache_system(body: dict) -> None:
    """Mark a long system prompt cacheable. Both libraries resend the same long instructions on every call, and
    caching changes the bill, not the output. Short prompts are left alone: the API ignores them anyway."""
    system = body.get("system")
    if isinstance(system, str) and len(system) >= CACHE_MIN_CHARS:
        body["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    elif isinstance(system, list) and system and not any("cache_control" in block for block in system):
        if sum(len(block.get("text", "")) for block in system) >= CACHE_MIN_CHARS:
            system[-1]["cache_control"] = {"type": "ephemeral"}


def record(tag: str, requested: str, usage: dict, seconds: float, status: int, error: str = "") -> None:
    usd = price(usage) if status == 200 else 0.0
    with LOCK:
        mine = read_ledger(LEDGER) if LEDGER.exists() else {"usd": 0.0, "calls": 0}
        tmp = LEDGER.with_suffix(".tmp")
        tmp.write_text(json.dumps({"usd": round(mine["usd"] + usd, 6), "calls": mine["calls"] + 1}))
        for attempt in range(20):
            try:
                os.replace(tmp, LEDGER)
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        else:
            LEDGER.write_text(tmp.read_text())
        row = {"t": round(time.time(), 3), "tag": tag, "requested_model": requested, "status": status,
               "seconds": round(seconds, 3), "usd": round(usd, 8), **{k: usage.get(k) or 0 for k in (
                   "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}}
        if error:
            row["error"] = error[:300]
        with CALLS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    client: httpx.Client
    auth: dict[str, str]

    def log_message(self, *args) -> None:  # quiet
        pass

    def reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        raw = self.rfile.read(int(self.headers.get("content-length") or 0))
        path = self.path.split("?")[0]
        if path not in ("/v1/messages", "/v1/messages/count_tokens"):
            self.reply(404, b'{"type":"error","error":{"type":"not_found_error","message":"not proxied"}}')
            return
        body = json.loads(raw or b"{}")
        requested = str(body.get("model", ""))
        body["model"] = MODEL
        # Haiku 5.5 rejects sampling parameters ("`temperature` is deprecated for this model"); both libraries still
        # send them, so they are dropped here and the model samples with its defaults, as our own calls do.
        for name in SAMPLING:
            body.pop(name, None)
        cache_system(body)
        headers = {k: v for k in FORWARD_HEADERS if (v := self.headers.get(k))}
        headers.update(self.auth)
        if path.endswith("count_tokens"):
            response = self.client.post(UPSTREAM + path, json=body, headers=headers)
            self.reply(response.status_code, response.content)
            return
        with LOCK:
            if spent() >= CAP_USD:
                self.reply(402, json.dumps({"type": "error", "error": {
                    "type": "budget_exceeded", "message": f"spend cap ${CAP_USD:.2f} reached"}}).encode())
                return
        tag = self.headers.get("x-bench-tag", "untagged")
        if body.get("stream"):
            self.stream(path, body, headers, tag, requested)
            return
        started = time.perf_counter()
        for attempt in range(12):
            response = self.client.post(UPSTREAM + path, json=body, headers=headers)
            if response.status_code not in (429, 500, 502, 503, 529) or attempt == 11:
                break
            wait = response.headers.get("retry-after")
            time.sleep((float(wait) if wait else min(60.0, 5.0 * 2 ** min(attempt, 3))) + random.random() * 3)
        usage = response.json().get("usage", {}) if response.status_code == 200 else {}
        error = "" if response.status_code == 200 else response.text
        record(tag, requested, usage, time.perf_counter() - started, response.status_code, error)
        self.reply(response.status_code, response.content)

    def stream(self, path: str, body: dict, headers: dict, tag: str, requested: str) -> None:
        started = time.perf_counter()
        usage: dict = {}
        with self.client.stream("POST", UPSTREAM + path, json=body, headers=headers) as response:
            self.send_response(response.status_code)
            self.send_header("content-type", response.headers.get("content-type", "text/event-stream"))
            self.send_header("transfer-encoding", "chunked")
            self.end_headers()
            buffer = b""
            for chunk in response.iter_raw():
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.startswith(b"data:"):
                        try:
                            event = json.loads(line[5:])
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") == "message_start":
                            usage.update(event["message"].get("usage", {}))
                        elif event.get("type") == "message_delta":
                            usage.update({k: v for k, v in event.get("usage", {}).items() if v is not None})
            self.wfile.write(b"0\r\n\r\n")
            record(tag, requested, usage, time.perf_counter() - started, response.status_code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    values = settings()
    Handler.auth = {"x-api-key": values["CLAUDE_API_KEY"]}
    if "CLAUDE_WORKSPACE_ID" in values:
        Handler.auth["anthropic-workspace-id"] = values["CLAUDE_WORKSPACE_ID"]
    Handler.client = httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"metering proxy on 127.0.0.1:{args.port}, suite {SUITE}, cap ${CAP_USD:.2f}, spent ${spent():.2f}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
