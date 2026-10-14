"""Builds the context-based arms for LongMemEval-S (xiaowu0162/longmemeval-cleaned, longmemeval_s_cleaned.json):
what the reader sees for each question, at a token budget.

As for LoCoMo, every arm gets the same input: the chat history as one document per session, sessions in date order
(as Mem0's LongMemEval harness orders them), one line per message with its date ("[2023/05/20 (Sat) 02:21] user:
..."). Each history is about 115k tokens. Budgets are measured on the final text with LLMSlim's token counter.

Arms: full, recent, rag (Qwen3-Embedding-0.6B), llmslim, llmslim_rr, lingua2 (see build_locomo.py for each).

  python build_lme.py --data longmemeval_s_cleaned.json --out DIR --arms llmslim rag --budgets 2500 10000 \
      --split test|dev|memory_sample [--limit N]
Writes DIR/lme_<split>_<arm>_<budget>.jsonl: {"id", "context", "tokens", "build_ms"}.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from build_locomo import Arms as LocomoArms  # noqa: E402
from build_locomo import count_tokens, fit_lines  # noqa: E402


def sessions(row: dict) -> list[tuple[str, list[dict]]]:
    pairs = sorted(zip(row["haystack_dates"], row["haystack_sessions"]), key=lambda pair: pair[0])
    return [(date, turns) for date, turns in pairs if turns]


def lines_of(row: dict) -> list[str]:
    return [
        f"[{date}] {turn['role']}: {turn['content']}"
        for date, turns in sessions(row)
        for turn in turns
    ]


def documents(row: dict) -> list[str]:
    return [
        "\n".join(f"[{date}] {turn['role']}: {turn['content']}" for turn in turns)
        for date, turns in sessions(row)
    ]


class Arms(LocomoArms):
    """The LoCoMo arms, fed a LongMemEval history instead of a LoCoMo conversation."""

    def full(self, row, question, budget):
        return "\n\n".join(documents(row))

    def recent(self, row, question, budget):
        lines = lines_of(row)
        return fit_lines(list(range(len(lines) - 1, -1, -1)), lines, budget)

    def rag(self, row, question, budget):
        from sentence_transformers import SentenceTransformer

        if self._embedder is None:
            fp16 = {"torch_dtype": "float16"} if self.device.startswith("cuda") else {}
            self._embedder = SentenceTransformer(
                "Qwen/Qwen3-Embedding-0.6B", device=self.device, model_kwargs=fp16
            )
        lines = lines_of(row)
        vectors = self._embedder.encode(lines, normalize_embeddings=True, batch_size=64)
        query = self._embedder.encode([question], prompt_name="query", normalize_embeddings=True)[0]
        order = sorted(range(len(lines)), key=lambda i: -float(vectors[i] @ query))
        return fit_lines(order, lines, budget)

    def _llmslim(self, row, question, budget, **options):
        from llmslim import compress_documents

        docs = documents(row)
        ratio = budget / sum(count_tokens(d) for d in docs)
        for _ in range(4):
            results = compress_documents(
                docs, query=question, target_ratio=min(ratio, 1.0), **options
            )
            text = "\n\n".join(
                r.compressed_text.strip() for r in results if r.compressed_text.strip()
            )
            tokens = count_tokens(text)
            if tokens <= budget * 1.02:
                return text
            ratio *= budget / tokens * 0.98
        return text

    def lingua2(self, row, question, budget):
        if self._lingua2 is None:
            from llmlingua import PromptCompressor

            self._lingua2 = PromptCompressor(
                model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                use_llmlingua2=True,
                device_map=self.device,
            )
        out = self._lingua2.compress_prompt(
            documents(row),
            target_token=budget,
            force_tokens=["\n", "?", ".", "!"],
            drop_consecutive=True,
        )
        return out["compressed_prompt"]


def load(data: Path, split: str) -> list[dict]:
    rows = {row["question_id"]: row for row in json.loads(Path(data).read_text(encoding="utf-8"))}
    ids = json.loads((HERE / "splits_r3.json").read_text())["lme"][split]
    return [rows[qid] for qid in ids]


def default_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--budgets", type=int, nargs="+", required=True)
    parser.add_argument("--split", default="test", choices=["test", "dev", "memory_sample"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--device", default=None, help="default: cuda when available, else cpu")
    parser.add_argument(
        "--off",
        nargs="*",
        default=[],
        help="llmslim.focus switches to turn off, e.g. CHAINED_ROUNDS",
    )
    parser.add_argument("--tag", help="suffix for the output names, e.g. v2 for a newer LLMSlim")
    args = parser.parse_args()
    args.device = args.device or default_device()
    import llmslim.focus

    for switch in args.off:
        if not isinstance(getattr(llmslim.focus, switch, None), bool):
            raise SystemExit(f"llmslim.focus has no switch {switch}")
        setattr(llmslim.focus, switch, False)
    rows = load(args.data, args.split)[: args.limit]
    arms = Arms(args.device)
    args.out.mkdir(parents=True, exist_ok=True)
    for arm in args.arms:
        for budget in [0] if arm == "full" else args.budgets:
            path = args.out / (
                f"lme_{args.split}_full.jsonl"
                if arm == "full"
                else f"lme_{args.split}_{arm}{'-' + args.tag if args.tag else ''}_{budget}.jsonl"
            )
            done = (
                {json.loads(l)["id"] for l in path.open(encoding="utf-8")}
                if path.exists()
                else set()
            )
            with path.open("a", encoding="utf-8") as handle:
                for row in rows:
                    if row["question_id"] in done:
                        continue
                    started = time.perf_counter()
                    context = getattr(arms, arm)(row, row["question"], budget)
                    ms = (time.perf_counter() - started) * 1000
                    handle.write(
                        json.dumps(
                            {
                                "id": row["question_id"],
                                "context": context,
                                "tokens": count_tokens(context),
                                "build_ms": round(ms, 1),
                            }
                        )
                        + "\n"
                    )
                    handle.flush()
            print(f"{path.name}: done", flush=True)


if __name__ == "__main__":
    main()
