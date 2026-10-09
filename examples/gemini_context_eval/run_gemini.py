"""Send every built prompt to Gemini and append the replies to results/responses.jsonl.

Requires ``pip install google-genai`` and a ``GEMINI_API_KEY`` environment
variable. The key is read by the Google Gen AI client and never printed.

    python examples/gemini_context_eval/run_gemini.py --model gemini-2.5-flash
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from google import genai
except ImportError as exc:
    raise SystemExit("Install with: pip install google-genai") from exc

from cases import CASES

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemini-2.5-flash")
    args = parser.parse_args()

    client = genai.Client()
    out = HERE / "results" / "responses.jsonl"
    out.parent.mkdir(exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        for case in CASES:
            for condition in ("baseline", "llmslim"):
                prompt = (HERE / "prompts" / f"{case['id']}.{condition}.txt").read_text(
                    encoding="utf-8"
                )
                reply = client.models.generate_content(model=args.model, contents=prompt)
                record = {
                    "case": case["id"],
                    "condition": condition,
                    "model": args.model,
                    "surface": "Gemini API",
                    "response": reply.text,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(case["id"], condition, "done")


if __name__ == "__main__":
    main()
