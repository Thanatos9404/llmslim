"""Run the SWE-bench agent over Verified Mini for the given arms. Resumable: finished (instance, arm) pairs are skipped.

usage: run.py --arms baseline llmslim --limit 4 --workers 4 --tag pilot
"""

from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import haiku_client as hc
from agent import solve

import llmslim

HERE = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arms", nargs="+", default=["baseline", "llmslim"]
    )  # baseline2: a second baseline sample for run-to-run noise
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tag", default="main")
    args = parser.parse_args()

    instances = [json.loads(line) for line in (HERE / "mini.jsonl").read_text().splitlines()][
        args.offset : args.offset + args.limit
    ]
    out = HERE / "runs" / args.tag
    logs = out / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (out / "meta.json").write_text(
        json.dumps({"llmslim": llmslim.__version__, "arms": args.arms, "n": len(instances)})
    )
    lock = threading.Lock()
    done = (
        {
            (json.loads(ln)["instance_id"], json.loads(ln)["arm"])
            for ln in (out / "stats.jsonl").read_text().splitlines()
        }
        if (out / "stats.jsonl").exists()
        else set()
    )
    jobs = [
        (inst, arm)
        for inst in instances
        for arm in args.arms
        if (inst["instance_id"], arm) not in done
    ]
    print(
        f"llmslim {llmslim.__version__}; {len(jobs)} jobs; spent so far ${hc.spent():.2f}",
        flush=True,
    )
    api = hc.client()

    def job(inst, arm):
        pred = solve(inst, arm, api, logs)
        with lock:
            with (out / f"preds_{arm}.jsonl").open("a") as f:
                f.write(
                    json.dumps(
                        {k: pred[k] for k in ("instance_id", "model_name_or_path", "model_patch")}
                    )
                    + "\n"
                )
            with (out / "stats.jsonl").open("a") as f:
                f.write(json.dumps(pred["stats"]) + "\n")
        s = pred["stats"]
        return f"{inst['instance_id']:32} {arm:9} steps={s['steps']:2} ${s['usd']:.3f} exit={s['exit']} patch={s['patch_lines']} lines {s['error'] or ''}"

    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(job, inst, arm) for inst, arm in jobs]
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except hc.BudgetExceeded as error:
                print("STOP:", error, flush=True)
                pool.shutdown(cancel_futures=True)
                break
    print(f"done; total spent ${hc.spent():.2f}", flush=True)


if __name__ == "__main__":
    main()
