"""Free offline development checks on the DEV split only (splits.json). No API calls.

What survives compression, at the reported budgets:
  nq       gold answer string present (25% of 20 documents)
  hotpot   both supporting paragraphs' supporting sentences kept, answer present (40%)
  lb       answer string present for LongBench QA tasks (3,000 tokens)
  lme      evidence turns kept (LongMemEval has_answer labels), answer present for short answers (8,000 tokens)

  python devcheck.py [--suites nq hotpot lb lme] [--n 400] [--which dev]
Run with the Core source you want first on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import statistics
import string
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
import splits as splits_mod  # noqa: E402

from llmslim import compress, compress_documents, count_tokens  # noqa: E402


def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def present(answers, text) -> bool:
    norm = normalize(text)
    return any(normalize(str(a)) and normalize(str(a)) in norm for a in answers)


def flat(text: str) -> str:
    """Comparable form of text whether or not it went through JSON escaping."""
    return re.sub(r"[^a-z0-9]+", "", text.lower().replace("\\n", " ").replace('\\"', '"'))


# ------------------------------------------------------------------ loaders (by split)


def nq_items(which: str, n: int):
    ids = splits_mod.load()["nq"][which][:n]
    files = {}
    for gold in (0, 9, 19):
        with gzip.open(DATA / "nq20" / f"gold_at_{gold}.jsonl.gz", "rt", encoding="utf-8") as f:
            files[gold] = [json.loads(line) for line in f]
    rng = random.Random(5)
    for i in ids:
        gold = rng.choice((0, 9, 19))
        row = files[gold][i]
        docs = [
            f"Document [{k + 1}](Title: {d['title']}) {d['text']}"
            for k, d in enumerate(row["ctxs"])
        ]
        yield {
            "id": f"nq{i}",
            "question": row["question"],
            "answers": row["answers"],
            "docs": docs,
            "context": "\n".join(docs),
            "gold": gold,
        }


def hotpot_items(which: str, n: int):
    want = splits_mod.load()["hotpot"][which][:n]
    rows = {}
    for offset in range(0, 800, 100):
        for item in json.loads((DATA / f"hotpot_{offset}.json").read_bytes())["rows"]:
            rows[item["row"]["id"]] = item["row"]
    for i in want:
        row = rows[i]
        ctx = row["context"]
        docs = [f"{t}: {''.join(s).strip()}" for t, s in zip(ctx["title"], ctx["sentences"])]
        support = defaultdict(list)
        for title, sid in zip(row["supporting_facts"]["title"], row["supporting_facts"]["sent_id"]):
            sents = ctx["sentences"][ctx["title"].index(title)]
            if sid < len(sents):
                support[title].append(sents[sid].strip())
        yield {
            "id": i,
            "question": row["question"],
            "answers": [row["answer"]],
            "docs": docs,
            "support": dict(support),
            "type": row["type"],
        }


def lb_items(task: str, which: str, n: int):
    want = splits_mod.load()["longbench"][task][which][:n]
    rows = {
        r["_id"]: r
        for r in (
            json.loads(line)
            for line in (DATA / "longbench" / f"{task}.jsonl")
            .read_bytes()
            .decode("utf-8")
            .split("\n")
            if line.strip()
        )
    }
    for i in want:
        r = rows[i]
        yield {"id": i, "question": r["input"], "answers": r["answers"], "context": r["context"]}


def lme_items(which: str, n: int):
    want = set(splits_mod.load()["lme"][which])
    rows = json.loads((DATA / "longmemeval" / "longmemeval_s_cleaned.json").read_bytes())
    out = []
    for r in rows:
        if r["question_id"] not in want:
            continue
        docs = []
        evidence = []
        for idx, (date, session) in enumerate(zip(r["haystack_dates"], r["haystack_sessions"])):
            turns = json.dumps(
                [{"role": t["role"], "content": t["content"]} for t in session], ensure_ascii=False
            )
            docs.append(
                f"### Session {idx + 1}:\nSession Date: {date}\nSession Content:\n{turns}\n"
            )
            for t in session:
                if t.get("has_answer"):
                    evidence.append(
                        {"session": idx, "role": t["role"], "content": t["content"], "date": date}
                    )
        out.append(
            {
                "id": r["question_id"],
                "question": r["question"],
                "answers": [str(r["answer"])],
                "docs": docs,
                "context": "\n".join(docs),
                "type": r["question_type"],
                "evidence": evidence,
                "abstention": r["question_id"].endswith("_abs"),
                "date": r["question_date"],
            }
        )
    return out[:n]


# ------------------------------------------------------------------ checks


def timed(fn):
    started = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - started) * 1000


def report(name, rows, keys):
    line = f"{name:30}"
    for key in keys:
        vals = [r[key] for r in rows if r.get(key) is not None]
        if vals:
            line += (
                f"  {key} {100 * statistics.mean(vals):5.1f}"
                if key not in ("tokens", "ms")
                else f"  {key} {statistics.mean(vals):6.0f}"
            )
    print(line + f"  n={len(rows)}", flush=True)


def check_nq(which, n, verbose=False):
    rows = []
    for it in nq_items(which, n):
        out, ms = timed(
            lambda: (
                compress(
                    it["context"], target_ratio=0.25, query=it["question"], **REL
                ).compressed_text
            )
        )
        rows.append(
            {
                "hit": present(it["answers"], out),
                "tokens": count_tokens(out),
                "ms": ms,
                "id": it["id"],
                "full": present(it["answers"], it["context"]),
            }
        )
    answerable = [r for r in rows if r["full"]]
    report("nq  compress 25%", answerable, ["hit", "tokens", "ms"])
    return rows


def check_hotpot(which, n):
    rows = []
    for it in hotpot_items(which, n):
        res, ms = timed(
            lambda: compress_documents(it["docs"], query=it["question"], target_ratio=0.4, **REL)
        )
        out = "\n".join(r.compressed_text for r in res)
        fo = flat(out)
        sp = [all(flat(s) in fo for s in sents) for sents in it["support"].values()]
        rows.append(
            {
                "both": all(sp) and len(sp) == 2,
                "sp": statistics.mean(sp) if sp else 0,
                "hit": present(it["answers"], out)
                if it["answers"][0].lower() not in ("yes", "no")
                else None,
                "tokens": count_tokens(out),
                "ms": ms,
                "type": it["type"],
            }
        )
    report("hot compress_documents 40%", rows, ["both", "sp", "hit", "tokens", "ms"])
    for t in ("bridge", "comparison"):
        report(f"    {t}", [r for r in rows if r["type"] == t], ["both", "sp"])
    return rows


def check_lb(which, n, tasks=("qasper", "2wikimqa", "musique", "triviaqa")):
    allrows = []
    for task in tasks:
        rows = []
        for it in lb_items(task, which, n):
            ratio = max(0.05, min(1.0, 3000 / count_tokens(it["context"])))
            out, ms = timed(
                lambda: (
                    compress(
                        it["context"], target_ratio=ratio, query=it["question"], **REL
                    ).compressed_text
                )
            )
            rows.append(
                {
                    "hit": present(it["answers"], out),
                    "tokens": count_tokens(out),
                    "ms": ms,
                    "full": present(it["answers"], it["context"]),
                }
            )
        report(f"lb  {task}", [r for r in rows if r["full"]], ["hit", "tokens", "ms"])
        allrows += rows
    return allrows


def check_lme(which, n, mode="docs"):
    rows = []
    for it in lme_items(which, n):
        budget = 8000
        if mode == "docs":
            res, ms = timed(
                lambda: compress_documents(
                    it["docs"],
                    query=it["question"],
                    target_ratio=budget / count_tokens(it["context"]),
                    **REL,
                )
            )
            out = "\n".join(r.compressed_text for r in res if r.compressed_text.strip())
        else:
            out, ms = timed(
                lambda: (
                    compress(
                        it["context"],
                        target_ratio=budget / count_tokens(it["context"]),
                        query=it["question"],
                        **REL,
                    ).compressed_text
                )
            )
        fo = flat(out)
        kept = []
        for ev in it["evidence"]:
            from llmslim.tokenization import split_sentences

            sents = [s for s in split_sentences(ev["content"]) if len(flat(s)) > 12] or [
                ev["content"]
            ]
            kept.append(sum(flat(s) in fo for s in sents) / len(sents))
        sessions = defaultdict(list)
        for ev, k in zip(it["evidence"], kept):
            sessions[ev["session"]].append(k)
        user_ev = [k for ev, k in zip(it["evidence"], kept) if ev["role"] == "user"]
        short = (
            len(it["answers"][0].split()) <= 4
            and it["type"] not in ("temporal-reasoning", "multi-session")
            and not it["abstention"]
        )
        rows.append(
            {
                "type": it["type"],
                "ev": statistics.mean(kept) if kept else None,
                "sess": statistics.mean(max(v) >= 0.5 for v in sessions.values())
                if sessions
                else None,
                "all": all(max(v) >= 0.5 for v in sessions.values()) if sessions else None,
                "user_ev": statistics.mean(user_ev) if user_ev else None,
                "hit": present(it["answers"], out) if short else None,
                "tokens": count_tokens(out),
                "ms": ms,
                "id": it["id"],
            }
        )
    report(f"lme {mode} 8k", rows, ["ev", "sess", "all", "user_ev", "hit", "tokens", "ms"])
    for t in LME_TYPES_ORDER:
        sub = [r for r in rows if r["type"] == t]
        if sub:
            report(f"    {t}", sub, ["ev", "sess", "all", "hit"])
    return rows


LME_TYPES_ORDER = splits_mod.LME_TYPES
REL: dict = {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suites", nargs="+", default=["nq", "hotpot", "lb", "lme"])
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument(
        "--which", default="dev", choices=["dev"]
    )  # test splits are evaluated with the API harness only
    parser.add_argument("--lme-mode", default="docs", choices=["docs", "global"])
    parser.add_argument("--relevance", default=None)
    parser.add_argument(
        "--set", nargs="*", default=[], help="focus module constants, NAME=VALUE (dev sweeps)"
    )
    args = parser.parse_args()
    import llmslim.focus as focus_module

    for assignment in args.set:
        name, value = assignment.split("=")
        setattr(focus_module, name, type(getattr(focus_module, name))(value))
        print("set", name, "=", getattr(focus_module, name))
    if args.relevance:
        REL["relevance"] = args.relevance
    import llmslim

    print("llmslim", llmslim.__version__, "from", llmslim.__file__, flush=True)
    if "nq" in args.suites:
        check_nq(args.which, args.n)
    if "hotpot" in args.suites:
        check_hotpot(args.which, args.n)
    if "lb" in args.suites:
        check_lb(args.which, min(args.n, 80))
    if "lme" in args.suites:
        check_lme(args.which, min(args.n, 320), args.lme_mode)


if __name__ == "__main__":
    main()
