"""Writes splits_r3.json: the round-3 dev/test splits, fixed before any round-3 result was seen.

Rules carried over from earlier rounds: changes to LLMSlim are made and checked only on `dev`; everything reported
comes from the test sets, which no change was tuned on. Earlier rounds' dev questions stay dev.

- locomo: conversations 0-1 are dev (all their questions); 2-9 are test. `longlingua_sample` is a fixed random
  300 of the test questions for LongLLMLingua, whose 7B scorer is too slow for all of them.
- lme: test is test_a + test_b from splits.json (180 questions, never tuned on). `memory_sample` is 60 of them,
  10 per question type, for Mem0 and Zep, which must build a memory per question.
- nq: every question that is not in the earlier dev split, each with one gold position drawn at random from the
  three published files (1st, 10th, 20th).
- hotpot: 2,000 validation questions drawn at random from those not in the earlier dev split.
- nq and hotpot `longlingua_sample`: a fixed random 1,000 of each test set for LongLLMLingua (about 8 s a question
  on a T4, so all 4,255 would not fit a Kaggle session). Added before any round-3 result existed.

  python splits_r3.py --data DATA_DIR
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SEED = 2026


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    old = json.loads((HERE.parent / "splits.json").read_text())
    rng = random.Random(SEED)
    out: dict = {"seed": SEED}

    locomo = json.loads((args.data / "locomo" / "locomo10.json").read_text(encoding="utf-8"))
    test_ids = [
        f"c{c}q{i}"
        for c in range(2, 10)
        for i, qa in enumerate(locomo[c]["qa"])
        if int(qa.get("category", 0)) in (1, 2, 3, 4)
    ]
    out["locomo"] = {
        "dev_convs": [0, 1],
        "test_convs": list(range(2, 10)),
        "longlingua_sample": sorted(rng.sample(test_ids, 300)),
    }

    lme = json.loads(
        (args.data / "longmemeval" / "longmemeval_s_cleaned.json").read_text(encoding="utf-8")
    )
    types = {row["question_id"]: row["question_type"] for row in lme}
    test = old["lme"]["test_a"] + old["lme"]["test_b"]
    by_type = defaultdict(list)
    for qid in test:
        by_type[types[qid]].append(qid)
    sample = [qid for kind in sorted(by_type) for qid in rng.sample(sorted(by_type[kind]), 10)]
    out["lme"] = {"test": test, "dev": old["lme"]["dev"], "memory_sample": sample}

    with gzip.open(args.data / "nq20" / "gold_at_0.jsonl.gz", "rt", encoding="utf-8") as handle:
        total = sum(1 for _ in handle)
    dev = set(old["nq"]["dev"])
    out["nq"] = {
        "dev": sorted(dev),
        "test": [[i, rng.choice([0, 9, 19])] for i in range(total) if i not in dev],
    }

    hotpot = json.loads((args.data / "hotpot_full" / "validation.json").read_text(encoding="utf-8"))
    hot_dev = set(old["hotpot"]["dev"])
    pool = [row["id"] for row in hotpot if row["id"] not in hot_dev]
    out["hotpot"] = {"dev": sorted(hot_dev), "test": sorted(rng.sample(pool, 2000))}

    # Drawn after every split above so those stay exactly as first written.
    sample_rng = random.Random(SEED + 1)
    out["nq"]["longlingua_sample"] = sorted(
        f"nq{i}-g{g}" for i, g in sample_rng.sample(out["nq"]["test"], 1000)
    )
    out["hotpot"]["longlingua_sample"] = sorted(sample_rng.sample(out["hotpot"]["test"], 1000))
    (HERE / "splits_r3.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(
        {
            k: {kk: len(vv) for kk, vv in v.items() if isinstance(vv, list)}
            for k, v in out.items()
            if isinstance(v, dict)
        }
    )


if __name__ == "__main__":
    main()
