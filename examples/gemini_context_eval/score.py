"""Score recorded Gemini replies and write the results table and summary.

Reads results/responses.jsonl (one JSON object per reply with case, condition,
model, surface and response) and writes:

* results/results.csv - Prompt | Ideal Response | Model Used | Response 1 |
  Response 1 PASS or FAIL - Comments (the Google AI Futures Fund feedback format)
* results/RESULTS.md - pass rates and token counts per condition

Checks are deliberately simple regular expressions from cases.py, so every
verdict can be audited by reading the reply.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from cases import CASES

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def verdict(case: dict, response: str) -> tuple[bool, list[str]]:
    notes = []
    for pattern in case["must_include"]:
        if not re.search(pattern, response, re.IGNORECASE | re.MULTILINE):
            notes.append(f"missing /{pattern}/")
    for pattern in case["must_not_include"]:
        if re.search(pattern, response, re.IGNORECASE | re.MULTILINE):
            notes.append(f"contains forbidden /{pattern}/")
    return not notes, notes


def main() -> None:
    by_id = {case["id"]: case for case in CASES}
    manifest = json.loads((HERE / "prompts" / "manifest.json").read_text(encoding="utf-8"))
    tokens = {row["id"]: row for row in manifest["cases"]}
    records = [
        json.loads(line)
        for line in (RESULTS / "responses.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    tally: dict[tuple[str, str], list[bool]] = defaultdict(list)
    with (RESULTS / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Prompt",
                "Ideal Response",
                "Model Used",
                "Response 1",
                "Response 1 PASS or FAIL - Comments",
            ]
        )
        for record in records:
            case = by_id[record["case"]]
            passed, notes = verdict(case, record["response"])
            if "manual_verdict" in record:  # a human read the reply and disagreed with the regex
                passed = record["manual_verdict"] == "PASS"
                notes = [f"manual review overrides regex: {record.get('note', '')}"]
            tally[(record["model"], record["condition"])].append(passed)
            prompt = (HERE / "prompts" / f"{case['id']}.{record['condition']}.txt").read_text(
                encoding="utf-8"
            )
            comment = "PASS" if passed else "FAIL - " + "; ".join(notes)
            comment += f" | condition={record['condition']}; failure mode: {case['failure_mode']}"
            if record.get("note"):
                comment += f" | {record['note']}"
            writer.writerow(
                [
                    prompt,
                    case["ideal"],
                    f"{record['model']} ({record['surface']})",
                    record["response"],
                    comment,
                ]
            )

    lines = ["# Gemini context evaluation results", ""]
    lines.append(f"Prompts built {manifest['built_at']}; {len(CASES)} synthetic cases.")
    lines += ["", "| Model | Condition | Passed |", "| --- | --- | --- |"]
    for (model, condition), results in sorted(tally.items()):
        lines.append(f"| {model} | {condition} | {sum(results)}/{len(results)} |")
    lines += ["", "| Case | Baseline tokens | LLMSlim tokens |", "| --- | --- | --- |"]
    for case in CASES:
        row = tokens[case["id"]]
        lines.append(f"| {case['id']} | {row['baseline_tokens']} | {row['llmslim_tokens']} |")
    (RESULTS / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
