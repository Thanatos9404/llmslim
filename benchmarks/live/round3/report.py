"""Round-3 tables from the results JSONL files, cost first: accuracy with a 95% bootstrap interval over questions, the
paired difference from a reference arm on the questions both answered, and what 1,000 questions cost end to end.

Cost per 1,000 questions (USD, list prices; judge calls are not counted for any arm):

- Reader: the answer call on Claude Haiku 5.5 ($0.10 / $0.50 per million input / output tokens; $0.50 / $2.50 above
  100k prompt tokens). "As run" keeps prompt caching where the arm used it: a context that does not depend on the
  question (full history, recent turns, LLMLingua-2 on LoCoMo) is the same prefix for every question about a
  conversation, so it was read from cache. "No cache" prices every prompt token in full, as when questions about a
  history arrive too far apart for the cache. Answers read through the Message Batches API were billed at half price;
  both columns count them at the list price like the rest.
- Memory: Mem0's and Zep's ingestion calls (Haiku 5.5, through the metering proxy), spread over the questions asked of
  the memory they built (LoCoMo: a conversation's questions share one memory; LongMemEval: one memory per question).
  Their embedding and database compute is not counted, which favours them.
- Compute: the time each system took to build its context, priced as cloud machine time: a T4 GPU (AWS g4dn.xlarge,
  $0.526/h on demand, us-east-1, mid-2026) for systems that ran on one, a 2-vCPU machine (c7i.large, $0.0892/h)
  otherwise. A question-independent LoCoMo context is built once per conversation and its time is shared.

  python report.py --results results/locomo_test*.jsonl --reference llmslim-v3_2500 \
      --ingest mem0=2.70:1540 zep=6.28:1307 --gpu rag rerank lingua2 longlingua llmslim_rr_
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROUNDS = 2000
LONG_PROMPT = 100_000
RATES = {False: (0.10, 0.50), True: (0.50, 2.50)}  # USD per million tokens: input, output
GPU_HOUR = 0.526  # AWS g4dn.xlarge (1x T4), on demand, us-east-1
CPU_HOUR = 0.0892  # AWS c7i.large (2 vCPU), on demand, us-east-1
QUESTION_INDEPENDENT = ("full", "recent", "lingua2")


def list_usd(row: dict) -> float:
    """The answer call's cost at list price, as run. Batch answers took minutes (every synchronous call took under
    30 s)."""
    batch = row.get("batch", row.get("seconds", 0) > 60)
    return row["usd"] * (2 if batch else 1)


def uncached_usd(row: dict) -> float:
    """The answer call's cost at list price with every prompt token billed in full."""
    price_in, price_out = RATES[row["prompt_tokens"] > LONG_PROMPT]
    return (row["prompt_tokens"] * price_in + row["output_tokens"] * price_out) / 1_000_000


def conversation(question_id: str) -> str:
    """LoCoMo ids are c<conversation>q<question>; other suites have one context per question."""
    return question_id[: question_id.index("q")] if question_id.startswith("c") else question_id


def read_lines(path: Path):
    """Lines of a .jsonl or .jsonl.gz file."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        yield from handle


def bootstrap(values: list[float], rng: random.Random) -> tuple[float, float]:
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(ROUNDS))
    return means[int(0.025 * ROUNDS)], means[int(0.975 * ROUNDS) - 1]


def compute_usd(
    arm: str, answered: dict[str, dict], gpu: list[str], cpu: list[str] | None = None
) -> float:
    """Mean build cost per question, with a question-independent LoCoMo context counted once per conversation.
    An arm matching a --cpu prefix was built on a CPU machine even if it also matches a --gpu prefix."""
    on_gpu = any(arm.startswith(p) for p in gpu) and not any(arm.startswith(p) for p in cpu or [])
    hourly = GPU_HOUR if on_gpu else CPU_HOUR
    rows = [r for r in answered.values() if r.get("build_ms") is not None]
    if not rows:
        return 0.0
    if arm.startswith(QUESTION_INDEPENDENT) and rows[0].get("suite") == "locomo":
        per_conversation: dict[str, float] = {}
        for r in rows:
            per_conversation[conversation(r["id"])] = r["build_ms"]
        total_ms = sum(per_conversation.values())
    else:
        total_ms = sum(r["build_ms"] for r in rows)
    return total_ms / 3_600_000 * hourly / len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--metric", default="score")
    parser.add_argument("--ingest", nargs="*", default=[], help="ARM_PREFIX=USD:QUESTIONS")
    parser.add_argument(
        "--gpu", nargs="*", default=[], help="arm prefixes whose context was built on a GPU"
    )
    parser.add_argument(
        "--cpu", nargs="*", default=[], help="arm prefixes built on a CPU (overrides --gpu)"
    )
    parser.add_argument("--ids", type=Path, help="restrict to these question ids")
    parser.add_argument(
        "--arms", nargs="*", help="only these arms (default: every arm in the files)"
    )
    args = parser.parse_args()
    wanted = set(args.ids.read_text().split()) if args.ids else None
    rows = [json.loads(line) for path in args.results for line in read_lines(path)]
    by_arm: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if args.arms and row["arm"] not in args.arms:
            continue
        if (wanted is None or row["id"] in wanted) and row["id"] not in by_arm[row["arm"]]:
            by_arm[row["arm"]][row["id"]] = row
    ingest = {}
    for spec in args.ingest:
        prefix, _, rest = spec.partition("=")
        usd, _, questions = rest.partition(":")
        ingest[prefix] = float(usd) / int(questions)
    reference = by_arm.get(args.reference, {})
    rng = random.Random(2026)
    print(
        f"| Arm | n | {args.metric} (95% CI) | vs {args.reference} (paired, 95% CI) | Context tokens | "
        "Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | "
        "Total $/1k as run | $ per 1k correct | Cost frontier |"
    )
    print("|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    order = sorted(
        by_arm, key=lambda arm: -statistics.mean(r[args.metric] for r in by_arm[arm].values())
    )
    frontier = cost_frontier(by_arm, args.metric, ingest, args.gpu, args.cpu)
    for arm in order:
        answered = by_arm[arm]
        values = [r[args.metric] for r in answered.values()]
        mean = statistics.mean(values)
        low, high = bootstrap(values, rng)
        common = sorted(set(answered) & set(reference))
        if arm == args.reference or not common:
            paired = "" if arm == args.reference else "n/a"
        else:
            diffs = [answered[i][args.metric] - reference[i][args.metric] for i in common]
            d_low, d_high = bootstrap(diffs, rng)
            paired = f"{100 * statistics.mean(diffs):+.1f} ({100 * d_low:+.1f}, {100 * d_high:+.1f}), n={len(common)}"
        tokens = [r["context_tokens"] for r in answered.values() if r.get("context_tokens")]
        ms = [r["build_ms"] for r in answered.values() if r.get("build_ms") is not None]
        reader = statistics.mean(list_usd(r) for r in answered.values())
        no_cache = statistics.mean(uncached_usd(r) for r in answered.values())
        memory = next((v for prefix, v in ingest.items() if arm.startswith(prefix)), 0.0)
        extra = memory + compute_usd(arm, answered, args.gpu, args.cpu)
        total = reader + extra
        per_correct = total / mean if mean else float("inf")
        context = f"{statistics.mean(tokens):,.0f}" if tokens else ""
        latency = f"{statistics.median(ms):,.0f}" if ms else ""
        print(
            f"| {arm} | {len(values)} | {100 * mean:.1f} ({100 * low:.1f}-{100 * high:.1f}) | {paired} | "
            f"{context} | {latency} | {1000 * reader:.2f} | {1000 * no_cache:.2f} | {1000 * extra:.2f} | "
            f"{1000 * total:.2f} | {1000 * per_correct:.2f} | {frontier[arm]} |"
        )


def cost_frontier(
    by_arm: dict[str, dict[str, dict]],
    metric: str,
    ingest: dict[str, float],
    gpu: list[str],
    cpu: list[str],
) -> dict[str, str]:
    """Which arms no other arm beats on both accuracy and total cost ("as run" and with no prompt cache): an arm is
    on the frontier when nothing is at least as accurate for at most its cost, and better on one of the two."""
    stats = {}
    for arm, answered in by_arm.items():
        memory = next((v for prefix, v in ingest.items() if arm.startswith(prefix)), 0.0)
        extra = memory + compute_usd(arm, answered, gpu, cpu)
        stats[arm] = (
            statistics.mean(r[metric] for r in answered.values()),
            statistics.mean(list_usd(r) for r in answered.values()) + extra,
            statistics.mean(uncached_usd(r) for r in answered.values()) + extra,
        )
    out = {}
    for arm, (accuracy, *costs) in stats.items():
        marks = []
        for k, label in ((0, "as run"), (1, "no cache")):
            dominated = any(
                other != arm
                and o_acc >= accuracy
                and o_costs[k] <= costs[k]
                and (o_acc > accuracy or o_costs[k] < costs[k])
                for other, (o_acc, *o_costs) in stats.items()
            )
            if not dominated:
                marks.append(label)
        out[arm] = ", ".join(marks)
    return out


if __name__ == "__main__":
    main()
