"""Final paired results for every suite and split: score, paired bootstrap 95% CI vs full context and vs the
equal-budget baseline, tokens and cost. No API calls.

  python final_report.py [--json results/final.json]
"""

from __future__ import annotations

import argparse
import difflib
import gzip
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
R = HERE / "results"
rng = random.Random(7)


def rows(name: str) -> list[dict]:
    """Per-question results, from ``results/<name>`` or the committed ``results/<name>.gz``."""
    path = R / name
    packed = path.with_name(path.name + ".gz")
    if path.exists():
        data = path.read_bytes()
    elif packed.exists():
        data = gzip.decompress(packed.read_bytes())
    else:
        return []
    return [json.loads(line) for line in data.decode("utf-8").split("\n") if line.strip()]


def boot(diffs: list[float], n: int = 4000) -> tuple[float, float]:
    means = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def table(
    title: str,
    by_id: dict,
    arms: list[str],
    key=lambda r: r["score"],
    tokens=lambda r: r.get("context_tokens"),
    usd=lambda r: r.get("usd", 0.0),
    refs=("full", "truncate"),
) -> dict:
    arms = [a for a in arms if any(a in v for v in by_id.values())]
    ids = [i for i, v in by_id.items() if all(a in v for a in arms)]
    out = {"title": title, "n": len(ids), "arms": {}}
    print(f"\n## {title}  (n={len(ids)})")
    if not ids:
        return out
    print(f"{'arm':22} {'score':>6} {'vs full':>22} {'vs baseline':>22} {'tokens':>8} {'$/1k':>8}")
    for arm in arms:
        s = [100 * key(by_id[i][arm]) for i in ids]
        entry = {"score": round(sum(s) / len(s), 1)}
        line = f"{arm:22} {entry['score']:6.1f}"
        for ref in refs:
            ref_arm = next((a for a in arms if a == ref), None)
            if ref_arm and ref_arm != arm:
                d = [100 * (key(by_id[i][arm]) - key(by_id[i][ref_arm])) for i in ids]
                lo, hi = boot(d)
                entry[f"vs_{ref}"] = [round(sum(d) / len(d), 1), round(lo, 1), round(hi, 1)]
                line += f" {sum(d) / len(d):+5.1f} ({lo:+5.1f},{hi:+5.1f})".rjust(23)
            else:
                line += " " * 23
        tok = [tokens(by_id[i][arm]) for i in ids if tokens(by_id[i][arm]) is not None]
        entry["tokens"] = round(sum(tok) / len(tok)) if tok else None
        entry["usd_per_1k"] = round(1000 * sum(usd(by_id[i][arm]) for i in ids) / len(ids), 3)
        print(line + f" {entry['tokens'] or 0:8} {entry['usd_per_1k']:8.3f}")
        out["arms"][arm] = entry
    return out


def paired(name: str) -> dict:
    by_id: dict = defaultdict(dict)
    for r in rows(name):
        by_id[r["id"]][r["arm"]] = r
    return by_id


# ---- LongBench: official metrics with the fence-aware first code line for lcc / repobench-p (rescore_code.py)
def lb_answers() -> dict:
    out = {}
    for task in ("lcc", "repobench-p"):
        for line in (
            (HERE / "data" / "longbench" / f"{task}.jsonl").read_text(encoding="utf-8").splitlines()
        ):
            if line.strip():
                row = json.loads(line)
                out[(task, row["_id"])] = row["answers"]
    return out


def first_code_line(prediction: str) -> str:
    lines = prediction.lstrip("\n").split("\n")
    if any(line.strip().startswith("```") for line in lines):
        start = next(i for i, line in enumerate(lines) if line.strip().startswith("```")) + 1
        body = lines[start:]
    else:
        body = lines
    return next(
        (line for line in body if line.strip() and not line.strip().startswith(("#", "//", "`"))),
        "",
    )


def code_sim(prediction: str, truth: str) -> float:
    return difflib.SequenceMatcher(None, first_code_line(prediction), truth).ratio()


def longbench(name: str, arms: list[str], title: str) -> dict:
    answers = lb_answers()
    data = rows(name)
    for r in data:
        if r["task"] in ("lcc", "repobench-p") and (r["task"], r["id"]) in answers:
            r["score"] = max(
                code_sim(r.get("prediction", ""), a) for a in answers[(r["task"], r["id"])]
            )
    by_task: dict = defaultdict(lambda: defaultdict(dict))
    for r in data:
        by_task[r["task"]][r["id"]][r["arm"]] = r
    print(f"\n## {title}")
    present = [a for a in arms if any(a in v for t in by_task.values() for v in t.values())]
    per_task = {}
    for task, by_id in sorted(by_task.items()):
        ids = [i for i, v in by_id.items() if all(a in v for a in present)]
        per_task[task] = (
            {a: 100 * sum(by_id[i][a]["score"] for i in ids) / len(ids) for a in present}
            if ids
            else {}
        )
        print(
            f"{task:12} n={len(ids):3} "
            + "  ".join(f"{a}={per_task[task].get(a, 0):5.1f}" for a in present)
        )
    macro = {
        a: sum(t[a] for t in per_task.values() if a in t)
        / max(1, sum(1 for t in per_task.values() if a in t))
        for a in present
    }
    print("macro        " + "  ".join(f"{a}={v:5.1f}" for a, v in macro.items()))
    # Paired macro CI: resample within each task.
    flat: dict = defaultdict(dict)
    for task, by_id in by_task.items():
        for i, v in by_id.items():
            if all(a in v for a in present):
                for a in present:
                    flat[(task, i)][a] = v[a]
    out = {
        "title": title,
        "per_task": per_task,
        "macro": {a: round(v, 1) for a, v in macro.items()},
        "ci": {},
    }
    for arm in present:
        for ref in ("full", "truncate"):
            if ref in present and ref != arm:
                tasks = sorted(per_task)
                diffs_by_task = {
                    t: [
                        100 * (flat[k][arm]["score"] - flat[k][ref]["score"])
                        for k in flat
                        if k[0] == t
                    ]
                    for t in tasks
                }
                means = []
                for _ in range(2000):
                    means.append(
                        sum(
                            sum(rng.choice(d) for _ in d) / len(d)
                            for d in diffs_by_task.values()
                            if d
                        )
                        / len(tasks)
                    )
                means.sort()
                point = sum(sum(d) / len(d) for d in diffs_by_task.values() if d) / len(tasks)
                out["ci"][f"{arm}_vs_{ref}"] = [
                    round(point, 1),
                    round(means[50], 1),
                    round(means[1949], 1),
                ]
                print(f"  {arm} vs {ref}: {point:+.1f} ({means[50]:+.1f}, {means[1949]:+.1f})")
    tokens = {
        a: round(sum(v[a]["input_tokens"] for v in flat.values()) / len(flat))
        for a in present
        if flat and "input_tokens" in next(iter(flat.values()))[a]
    }
    print("input tokens", tokens)
    out["tokens"] = tokens
    return out


def hotpot(name: str, arms: list[str], title: str) -> dict:
    by_id = paired(name)
    f1 = table(
        title + " F1", by_id, arms, key=lambda r: r["f1"], tokens=lambda r: r.get("input_tokens")
    )
    em = table(
        title + " EM", by_id, arms, key=lambda r: r["em"], tokens=lambda r: r.get("input_tokens")
    )
    return {"f1": f1, "em": em}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(R / "final.json"))
    args = parser.parse_args()
    report = {}
    report["nq_a"] = table(
        "NQ 20 docs, test_a (reported questions)",
        paired("nq.jsonl"),
        [
            "full",
            "core08s_global",
            "core08f_global",
            "llmslim08_global",
            "llmslim_global",
            "truncate",
        ],
    )
    report["nq_a_lingua"] = table(
        "NQ, the 150 questions with LLMLingua-2 / LongLLMLingua",
        paired("nq.jsonl"),
        ["full", "core08s_global", "core08f_global", "lingua2_eq", "longllmlingua", "truncate"],
    )
    report["nq_b"] = table(
        "NQ 20 docs, test_b (fresh)",
        paired("nq_b.jsonl"),
        ["full", "core08s_global", "core08f_global", "truncate"],
    )
    report["nq_b_lingua"] = table(
        "NQ test_b, the 150 questions with LLMLingua-2 / LongLLMLingua",
        paired("nq_b.jsonl"),
        ["full", "core08s_global", "core08f_global", "lingua2_eq", "longllmlingua", "truncate"],
    )
    report["hotpot_a"] = hotpot(
        "suite_rag.jsonl",
        ["full", "core08s_doc", "core08f_doc", "llmslim_doc", "truncate", "no_context"],
        "HotpotQA test_a",
    )
    report["hotpot_b"] = hotpot(
        "suite_rag_b.jsonl", ["full", "core08s_doc", "core08f_doc", "truncate"], "HotpotQA test_b"
    )
    report["lb_a"] = longbench(
        "suite_longbench.jsonl",
        ["full", "core08s", "core08f", "llmslim", "truncate"],
        "LongBench v1 test_a",
    )
    report["lb_b"] = longbench(
        "suite_longbench_b.jsonl", ["full", "core08s", "core08f", "truncate"], "LongBench v1 test_b"
    )
    lme_arms = ["full", "core08s_docs", "core08f_docs", "core080_docs", "platform", "truncate"]
    report["lme_a"] = table(
        "LongMemEval test_a", paired("lme.jsonl"), lme_arms, usd=lambda r: r.get("usd", 0)
    )
    report["lme_b"] = table("LongMemEval test_b (fresh)", paired("lme_b.jsonl"), lme_arms)
    for key in ("lme_a", "lme_b"):
        by_id = paired("lme.jsonl" if key == "lme_a" else "lme_b.jsonl")
        types = defaultdict(list)
        for i, v in by_id.items():
            if all(a in v for a in report[key]["arms"]):
                types[next(iter(v.values()))["meta"]["type"]].append(i)
        report[key]["by_type"] = {
            t: {
                a: round(100 * sum(by_id[i][a]["score"] for i in ids) / len(ids), 1)
                for a in report[key]["arms"]
            }
            for t, ids in types.items()
        }
        for t, v in report[key]["by_type"].items():
            print(f"  {t:28} " + "  ".join(f"{a}={s:5.1f}" for a, s in v.items()))
    report["lbv2_a"] = table(
        "LongBench v2 test_a",
        paired("lbv2.jsonl"),
        ["full", "core08s_global", "core08f_global", "llmslim08_global", "truncate"],
    )
    Path(args.json).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
