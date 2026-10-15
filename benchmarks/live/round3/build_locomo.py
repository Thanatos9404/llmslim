"""Builds the context-based arms for LoCoMo: what the reader sees for each question, at a token budget.

Every arm gets the same input: the conversation as one document per session, oldest first, one line per turn with
its date ("[8 May 2023] Caroline: ..."), as an agent's message log would store it. Whatever an arm keeps is what
the reader sees; nothing is re-added afterwards. Budgets are measured on the final text with LLMSlim's token
counter (tiktoken cl100k when installed), the same counter for every arm.

Arms:
  full          the whole conversation
  recent        the most recent lines that fit the budget
  rag           the lines most similar to the question (Qwen3-Embedding-0.6B, Mem0's embedder), in date order
  llmslim       llmslim.compress_documents(sessions, query=question) at the budget (lexical relevance, no model)
  llmslim_rr    the same with relevance="semantic" (LLMSlim's optional 22M cross-encoder)
  lingua2       LLMLingua-2 (xlm-roberta-large), held to the budget in tokens; it does not read the question
  longlingua    LongLLMLingua with the paper's settings (LLaMA-2-7B-chat, fp16), question-aware, held to the budget

  python build_locomo.py --data locomo10.json --out DIR --arms llmslim rag --budgets 2000 6000 [--convs 0 1]
Writes DIR/<arm>_<budget>.jsonl: {"id", "context", "tokens", "build_ms"}.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import locomo_data as ld  # noqa: E402

EMBEDDER = "Qwen/Qwen3-Embedding-0.6B"


def count_tokens(text: str) -> int:
    from llmslim import count_tokens as ct

    return ct(text)


def line(session: ld.Session, turn: ld.Turn) -> str:
    return f"[{session.date.day} {session.date:%B %Y}] {turn.speaker}: {turn.text}"


def documents(conversation: dict) -> list[str]:
    return ["\n".join(line(s, t) for t in s.turns) for s in ld.sessions(conversation)]


def lines_of(conversation: dict) -> list[str]:
    return [line(s, t) for s in ld.sessions(conversation) for t in s.turns]


def fit_lines(chosen: list[int], lines: list[str], budget: int) -> str:
    """Keep lines in the given priority order while they fit, then restore date order."""
    kept, used = [], 0
    for index in chosen:
        cost = count_tokens(lines[index]) + 1
        if used + cost > budget:
            continue
        kept.append(index)
        used += cost
    return "\n".join(lines[i] for i in sorted(kept))


class Arms:
    def __init__(self, device: str):
        self.device = device
        self._embedder = None
        self._lingua2 = None
        self._long = None

    # ---------------------------------------------------------------- baselines
    def full(self, conversation, question, budget):
        return "\n\n".join(documents(conversation))

    def recent(self, conversation, question, budget):
        lines = lines_of(conversation)
        return fit_lines(list(range(len(lines) - 1, -1, -1)), lines, budget)

    def rag(self, conversation, question, budget):
        from sentence_transformers import SentenceTransformer

        if self._embedder is None:
            fp16 = {"torch_dtype": "float16"} if self.device.startswith("cuda") else {}
            self._embedder = SentenceTransformer(EMBEDDER, device=self.device, model_kwargs=fp16)
        lines = lines_of(conversation)
        key = id(conversation)
        if getattr(self, "_cache_key", None) != key:
            self._cache_key, self._cache = (
                key,
                self._embedder.encode(lines, normalize_embeddings=True, batch_size=64),
            )
        query = self._embedder.encode([question], prompt_name="query", normalize_embeddings=True)[0]
        order = sorted(range(len(lines)), key=lambda i: -float(self._cache[i] @ query))
        return fit_lines(order, lines, budget)

    # ---------------------------------------------------------------- LLMSlim
    def _llmslim(self, conversation, question, budget, **options):
        from llmslim import compress_documents

        docs = documents(conversation)
        total = sum(count_tokens(d) for d in docs)
        ratio = budget / total
        for _ in range(4):  # hold the rendered text to the budget, as for every compressor
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

    def llmslim(self, conversation, question, budget):
        return self._llmslim(conversation, question, budget)

    def llmslim_rr(self, conversation, question, budget):
        return self._llmslim(conversation, question, budget, relevance="semantic")

    # ---------------------------------------------------------------- LLMLingua family
    def lingua2(self, conversation, question, budget):
        if self._lingua2 is None:
            from llmlingua import PromptCompressor

            self._lingua2 = PromptCompressor(
                model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                use_llmlingua2=True,
                device_map=self.device,
            )
        out = self._lingua2.compress_prompt(
            documents(conversation),
            target_token=budget,
            force_tokens=["\n", "?", ".", "!"],
            drop_consecutive=True,
        )
        return out["compressed_prompt"]

    def longlingua(self, conversation, question, budget):
        if self._long is None:
            import torch
            from llmlingua import PromptCompressor

            self._long = PromptCompressor(
                model_name="NousResearch/Llama-2-7b-chat-hf",
                device_map="auto",
                model_config={"torch_dtype": torch.float16},
            )
        out = self._long.compress_prompt(
            documents(conversation),
            question=question,
            target_token=budget,
            condition_in_question="after_condition",
            reorder_context="sort",
            dynamic_context_compression_ratio=0.3,
            condition_compare=True,
            context_budget="+100",
            rank_method="longllmlingua",
            concate_question=False,
        )
        return out["compressed_prompt"]


QUESTION_AGNOSTIC = {"full", "recent", "lingua2"}


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
    parser.add_argument("--convs", type=int, nargs="*")
    parser.add_argument(
        "--ids", type=Path, help="optional file with one question id per line (a sample)"
    )
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
    data = ld.load(args.data)
    wanted = set(args.ids.read_text().split()) if args.ids else None
    arms = Arms(args.device)
    args.out.mkdir(parents=True, exist_ok=True)
    for arm in args.arms:
        for budget in [0] if arm == "full" else args.budgets:
            label = f"{arm}-{args.tag}" if args.tag else arm
            path = args.out / (f"{label}.jsonl" if arm == "full" else f"{label}_{budget}.jsonl")
            done = (
                {json.loads(l)["id"] for l in path.open(encoding="utf-8")}
                if path.exists()
                else set()
            )
            with path.open("a", encoding="utf-8") as handle:
                for conv, conversation in enumerate(data):
                    if args.convs is not None and conv not in args.convs:
                        continue
                    shared = None
                    for question in ld.questions([conversation]):
                        qid = f"c{conv}{question.id[2:]}"
                        if qid in done or (wanted is not None and qid not in wanted):
                            continue
                        started = time.perf_counter()
                        if arm in QUESTION_AGNOSTIC and shared is not None:
                            context, ms = shared
                        else:
                            context = getattr(arms, arm)(conversation, question.question, budget)
                            ms = (time.perf_counter() - started) * 1000
                            if arm in QUESTION_AGNOSTIC:
                                shared = (context, ms)
                        handle.write(
                            json.dumps(
                                {
                                    "id": qid,
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
