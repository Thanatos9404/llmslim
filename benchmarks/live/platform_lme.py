"""Build the `platform` arm of LongMemEval-S with LLMSlim Platform (in-process, no services, no LLM in prepare).

Integration as the Platform documents it: every turn of every session is ingested into one Scope as a user or
assistant event (session date written into the text, since the Platform does not render timestamps), the task
instruction is a trusted system instruction, and prepare() compiles the Anthropic request at the same 8,000-token
context budget as the other arms. The compiled request is sent unchanged by bench2.py run.

  <platform venv python> platform_lme.py --n 90 [--mode balanced] [--arm platform]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import bench2  # noqa: E402
from llmslim_platform import (
    Actor,
    CompilerOptions,
    ContextControlPlane,
    EventInput,
    EventType,
    Scope,
    TrustClass,
)  # noqa: E402
from llmslim_platform.context import ContextMode, ContextRequest  # noqa: E402
from llmslim_platform.shared import canonical  # noqa: E402

INSTRUCTION = (
    "I will give you several history chats between you and a user. Please answer the question based on the "
    "relevant chat history."
)
BUDGET = 8000
QUALITY_FLOOR = 0.5


def parse_date(text: str) -> datetime:
    # LongMemEval dates look like "2023/05/20 (Sat) 02:21"
    match = re.match(r"(\d{4})/(\d{2})/(\d{2}).*?(\d{2}):(\d{2})", text)
    y, mo, d, h, mi = map(int, match.groups())
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


async def build_one(item: dict, mode: str, quality_floor: float = QUALITY_FLOOR) -> dict:
    plane = ContextControlPlane()
    host = Actor(
        principal_id="host",
        tenant_id="bench",
        can_administer=True,
        grants=frozenset({TrustClass.SYSTEM_TRUSTED}),
    )
    session = re.sub(r"[^A-Za-z0-9_.:-]", "-", item["id"])[:100]
    scope = Scope(tenant_id="bench", session_id=session)
    started = time.perf_counter()
    await plane.ingest(
        scope,
        EventInput(
            event_type=EventType.SYSTEM_INSTRUCTION,
            source="host",
            trust=TrustClass.SYSTEM_TRUSTED,
            payload_json=canonical({"text": INSTRUCTION}),
        ),
        host,
    )
    for index, (date, turns) in enumerate(zip(item["meta"]["dates"], item["meta"]["sessions"])):
        when = parse_date(date)
        for turn in turns:
            user = turn["role"] == "user"
            await plane.ingest(
                scope,
                EventInput(
                    event_type=EventType.USER_MESSAGE if user else EventType.ASSISTANT_MESSAGE,
                    source="chat",
                    trust=TrustClass.USER_INPUT if user else TrustClass.MODEL_GENERATED,
                    happened_at=when,
                    observed_at=when,
                    payload_json=canonical(
                        {"text": f"[Session {index + 1}, {date}] {turn['content']}"[:131000]}
                    ),
                ),
                host,
            )
    ingest_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    turn = await plane.prepare(
        tenant_id="bench",
        session_id=session,
        actor=host,
        user_input=f"Current Date: {item['date']}\nQuestion: {item['question']}\nAnswer:",
        # The default quality floor (0.8) raises CompilationError on every LongMemEval history at this budget;
        # 0.5 is the lowest documented setting that lets v0.9 compile, so the arm uses it.
        options=CompilerOptions(
            provider="anthropic",
            model="claude-haiku-5-5",
            max_input_tokens=BUDGET + 600,
            max_output_tokens=bench2.SUITES["lme"]["max_tokens"],
            cache_mode="disabled",
            quality_floor=quality_floor,
        ),
        context=ContextRequest(mode=ContextMode(mode)),
    )
    prepare_ms = (time.perf_counter() - started) * 1000
    request = {k: v for k, v in turn.request.items() if k in ("system", "messages")}
    assert turn.trace.token_counter_version.startswith("tiktoken"), turn.trace.token_counter_version
    return {
        "id": item["id"],
        "context_tokens": turn.trace.planned_tokens,
        "ms": round(prepare_ms, 1),
        "ingest_ms": round(ingest_ms, 1),
        "request": request,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=90)
    parser.add_argument("--mode", default="balanced")
    parser.add_argument("--arm", default="platform")
    parser.add_argument("--quality-floor", type=float, default=QUALITY_FLOOR)
    args = parser.parse_args()
    items = bench2.lme_load(args.n)
    out_dir = bench2.BUILT / "lme"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args.arm}.jsonl"
    done = (
        {
            json.loads(ln)["id"]
            for ln in path.read_bytes().decode("utf-8").split(chr(10))
            if ln.strip()
        }
        if path.exists()
        else set()
    )
    with path.open("a", encoding="utf-8") as sink:
        for item in items:
            if item["id"] in done:
                continue
            row = asyncio.run(build_one(item, args.mode, args.quality_floor))
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
            sink.flush()
            print(
                f"{item['id']}: {row['context_tokens']} tokens, prepare {row['ms']:.0f} ms",
                flush=True,
            )


if __name__ == "__main__":
    main()
