"""Reader and judge for LoCoMo in round 3, the same for every system.

Each question is answered by Claude Haiku 5.5 (effort low) with Mem0's own LoCoMo answer prompt, and judged by
Haiku 5.5 with Mem0's own judge prompt, given the labelled evidence turns, exactly as Mem0's harness does
(mem0ai/memory-benchmarks @4b61c5d; prompts vendored verbatim in vendor/). The judge is generous by design (one
correct list item, the same topic, or dates within 14 days count), so token F1 against the gold answer, LoCoMo's
original metric, is reported beside it: it needs no model and gives no partial credit for a topic.

Sources:
  arm:FILE       contexts from build_locomo.py, shown as Mem0's prompt shows memories (chronological)
  mem0:DIR:K     Mem0's top-K memories per question from mem0_locomo.py, formatted by Mem0's own code
  zep:DIR        Zep's context block per question from zep_locomo.py

  HAIKU_SUITE=locomo-reader python reader_locomo.py --data locomo10.json --source arm:out/llmslim_2000.jsonl \
      --name llmslim_2000 --out results/locomo.jsonl [--convs 2 3 ...] [--ids sample.txt]
"""

from __future__ import annotations

import argparse
import json
import re
import string
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import haiku_client  # noqa: E402
import locomo_data as ld  # noqa: E402
from vendor import mem0_locomo_prompts as mem0p  # noqa: E402

CHRONO = "The following memories are presented in chronological order (oldest to newest)."
WRITE = threading.Lock()


def load_source(spec: str) -> dict[str, dict]:
    kind, _, rest = spec.partition(":")
    rows: dict[str, dict] = {}
    if kind == "arm":
        for line in Path(rest).open(encoding="utf-8"):
            row = json.loads(line)
            rows[row["id"]] = {"memories": f"{CHRONO}\n\n{row['context']}", "context_tokens": row["tokens"],
                               "build_ms": row.get("build_ms")}
    elif kind == "mem0":
        folder, _, k = rest.rpartition(":")
        for path in Path(folder).glob("search_c*.jsonl"):
            for line in path.open(encoding="utf-8"):
                row = json.loads(line)
                rows[row["id"]] = {"search": row["memories"][: int(k)], "build_ms": row.get("search_ms")}
    elif kind == "zep":
        for path in Path(rest).glob("search_c*.jsonl"):
            for line in path.open(encoding="utf-8"):
                row = json.loads(line)
                rows[row["id"]] = {"memories": row["context"], "build_ms": row.get("search_ms")}
    else:
        raise SystemExit(f"unknown source {spec}")
    return rows


def answer_prompt(question: ld.Question, source: dict, reference: str) -> str:
    if "search" in source:  # Mem0's own formatter: top memories, sorted by date, human dates, no scores
        return mem0p.get_answer_generation_prompt(question.question, source["search"], reference_date=reference)
    return mem0p.ANSWER_GENERATION_PROMPT.format(memories=source["memories"], question=question.question,
                                                 reference_date=reference)


def evidence_context(conversation: dict, question: ld.Question) -> str:
    """Mem0's harness: '[D1:3, said on <session date>] Speaker: "text"' per labelled evidence turn."""
    conv = conversation["conversation"]
    lines = []
    for ref in question.evidence:
        match = re.match(r"D(\d+):", ref)
        session = f"session_{match.group(1)}" if match else ""
        for turn in conv.get(session, []):
            if turn.get("dia_id") == ref:
                date = conv.get(f"{session}_date_time", "")
                suffix = f", said on {date}" if date else ""
                lines.append(f'[{ref}{suffix}] {turn.get("speaker", "")}: "{turn.get("text", "")}"')
    return "\n".join(lines)


def normalize(text: str) -> list[str]:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the|and)\b", " ", text)
    return text.split()


def token_f1(prediction: str, gold: str) -> float:
    pred, ref = normalize(prediction), normalize(gold)
    common = Counter(pred) & Counter(ref)
    same = sum(common.values())
    if not pred or not ref or same == 0:
        return 0.0
    precision, recall = same / len(pred), same / len(ref)
    return 2 * precision * recall / (precision + recall)


def parse_label(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            label = str(json.loads(match.group(0)).get("label", "")).upper()
            if label in ("CORRECT", "WRONG"):
                return label
        except json.JSONDecodeError:
            pass
    upper = text.upper()
    return "CORRECT" if "CORRECT" in upper and "WRONG" not in upper else "WRONG"


def run_one(api, name: str, question: ld.Question, conversation: dict, source: dict, reference: str) -> dict:
    prompt = answer_prompt(question, source, reference)
    response, seconds, usd = haiku_client.call(api, messages=[{"role": "user", "content": prompt}], max_tokens=4096)
    raw = haiku_client.text_of(response)
    answer = raw.rsplit("ANSWER:", 1)[-1].strip() if "ANSWER:" in raw else raw.strip()
    evidence = evidence_context(conversation, question)
    judge_prompt = (mem0p.get_judge_prompt_with_evidence(question.category, question.question, question.answer,
                                                         answer, evidence) if evidence else
                    mem0p.get_judge_prompt(question.category, question.question, question.answer, answer))
    verdict, _, judge_usd = haiku_client.call(api, system=mem0p.JUDGE_SYSTEM_PROMPT,
                                              messages=[{"role": "user", "content": judge_prompt}], max_tokens=600)
    label = parse_label(haiku_client.text_of(verdict))
    return {
        "suite": "locomo", "id": f"c{question.conv}{question.id[2:]}", "arm": name, "category": question.category,
        "score": 1.0 if label == "CORRECT" else 0.0, "f1": round(token_f1(answer, question.answer), 4),
        "context_tokens": source.get("context_tokens"), "prompt_tokens": haiku_client.prompt_tokens(response.usage),
        "output_tokens": response.usage.output_tokens, "build_ms": source.get("build_ms"),
        "usd": round(usd, 6), "judge_usd": round(judge_usd, 6), "seconds": round(seconds, 2),
        "stop": response.stop_reason, "prediction": answer, "gold": question.answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--convs", type=int, nargs="*")
    parser.add_argument("--ids", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    data = ld.load(args.data)
    source = load_source(args.source)
    wanted = set(args.ids.read_text().split()) if args.ids else None
    done = set()
    if args.out.exists():
        done = {(r["arm"], r["id"]) for r in map(json.loads, args.out.open(encoding="utf-8"))}
    jobs = []
    for conv, conversation in enumerate(data):
        if args.convs is not None and conv not in args.convs:
            continue
        reference = ld.reference_date(conversation)
        for question in ld.questions([conversation]):
            question = ld.Question(f"c{conv}{question.id[2:]}", conv, question.category, question.question,
                                   question.answer, question.evidence)
            if (args.name, question.id) in done or (wanted is not None and question.id not in wanted):
                continue
            if question.id not in source:
                print(f"{args.name}: no context for {question.id}", flush=True)
                continue
            jobs.append((question, conversation, source[question.id], reference))
    api = haiku_client.client()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def work(job):
        row = run_one(api, args.name, *job)
        with WRITE, args.out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return row

    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(work, jobs))
    if rows:
        print(f"{args.name}: {len(rows)} answered, judge {100 * sum(r['score'] for r in rows) / len(rows):.1f}, "
              f"F1 {100 * sum(r['f1'] for r in rows) / len(rows):.1f}, spent ${haiku_client.spent():.2f}", flush=True)


if __name__ == "__main__":
    main()
