"""Offline evidence recall on the round-3 DEV splits (never test): no model calls, no spend.

For each dev question, run the round-3 llmslim arm (lexical) and measure what survives:
  lme     share of each answer-bearing turn's sentences (has_answer) present in the context, at 2,500 and 10,000
  locomo  share of evidence turns (dia_id) present in the context, at 1,000 and 2,500
  nq      gold answer string present (ratio 0.25, gold at position 9 as in round 3)
  hotpot  gold answer string present (ratio 0.40; yes/no answers skipped)
Usage: dev_recall.py REPO DATA_DIR OUT_JSON [suite ...]
Compare two runs with dev_recall_compare.py BEFORE_JSON AFTER_JSON.
"""

import json
import re
import sys
import time
from pathlib import Path

repo, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
suites = sys.argv[4:] or ["lme", "locomo", "nq", "hotpot"]
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "benchmarks" / "live" / "round3"))
import build_lme  # noqa: E402
import build_locomo  # noqa: E402
import build_rag  # noqa: E402
import locomo_data as ld  # noqa: E402

from llmslim.tokenization import split_sentences  # noqa: E402

SPLITS = json.loads((repo / "benchmarks/live/round3/splits_r3.json").read_text())


def squash(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def sentence_share(turn_text, context):
    parts = [squash(s) for s in split_sentences(turn_text) if len(s.strip()) >= 20] or [
        squash(turn_text)
    ]
    return sum(p in context for p in parts) / len(parts)


results = {}
t0 = time.time()
if "lme" in suites:
    rows = {
        r["question_id"]: r
        for r in json.loads(
            (data / "longmemeval" / "longmemeval_s_cleaned.json").read_text(encoding="utf-8")
        )
    }
    arms = build_lme.Arms("cpu")
    for qid in SPLITS["lme"]["dev"]:
        row = rows[qid]
        evidence = [
            t["content"]
            for _, turns in build_lme.sessions(row)
            for t in turns
            if t.get("has_answer")
        ]
        if not evidence:
            continue
        for budget in (2500, 10000):
            context = squash(arms.llmslim(row, row["question"], budget))
            shares = [sentence_share(e, context) for e in evidence]
            results[f"lme/{budget}/{qid}"] = sum(shares) / len(shares)
    print("lme done", round(time.time() - t0), "s", flush=True)

if "locomo" in suites:
    conversations = ld.load(data / "locomo" / "locomo10.json")
    arms = build_locomo.Arms("cpu")
    dev = SPLITS["locomo"]["dev_convs"]
    for q in ld.questions(conversations):
        if q.conv not in dev or not q.evidence:
            continue
        conversation = conversations[q.conv]
        by_id = {t.dia_id: t.text for s in ld.sessions(conversation) for t in s.turns}
        evidence = [by_id[e] for e in q.evidence if e in by_id]
        if not evidence:
            continue
        for budget in (1000, 2500):
            context = squash(arms.llmslim(conversation, q.question, budget))
            results[f"locomo/{budget}/{q.id}"] = sum(squash(e) in context for e in evidence) / len(
                evidence
            )
    print("locomo done", round(time.time() - t0), "s", flush=True)

for suite in ("nq", "hotpot"):
    if suite not in suites:
        continue
    arms = build_rag.Arms(suite, "cpu")
    for item in build_rag.load(suite, data, "dev"):
        answers = [a for a in item["answers"] if a.lower() not in ("yes", "no")]
        if not answers:
            continue
        context = squash(arms.llmslim(item, 0))
        results[f"{suite}/{item['id']}"] = float(any(squash(a) in context for a in answers))
    print(suite, "done", round(time.time() - t0), "s", flush=True)

out.write_text(json.dumps(results, indent=0, sort_keys=True))
groups = {}
for key, value in results.items():
    group = key.rsplit("/", 1)[0]
    groups.setdefault(group, []).append(value)
for group, values in sorted(groups.items()):
    print(f"{group:16s} n={len(values):4d}  mean={sum(values) / len(values):.4f}")
