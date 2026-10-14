"""Builds the arms for the two retrieval suites in round 3: what the reader sees for each question.

  nq      NaturalQuestions-Open with 20 retrieved Wikipedia passages (nelson-liu/lost-in-the-middle), one gold
          position per question fixed in splits_r3.json. Budget: 25% of the passages' tokens, as in earlier rounds.
  hotpot  HotpotQA distractor validation, 10 paragraphs per question (2 gold, 8 distractors). Budget: 40%.

Every arm gets the same passages and the same token budget (budget = ratio x the full context's tokens, counted
with LLMSlim's counter for every arm):

  full        every passage
  order       passages in the order given (retrieval order for NQ) while they fit: plain top-k RAG
  rerank      whole passages ranked by cross-encoder/ms-marco-MiniLM-L-6-v2 (the reranker LLMSlim's optional
              semantic mode uses) while they fit, best first: the "just add a reranker" baseline
  llmslim     llmslim.compress_documents(passages, query=question, target_ratio) (lexical, no model)
  llmslim_rr  the same with relevance="semantic"
  lingua2     LLMLingua-2 (xlm-roberta-large), held to the budget in tokens
  longlingua  LongLLMLingua with the paper's NQ settings, LLaMA-2-7B-chat in fp16, held to the budget

  python build_rag.py --suite nq --data DATA --out DIR --arms llmslim rerank [--split test] [--sample] [--limit N]
Writes DIR/<suite>_<arm>.jsonl: {"id", "context", "tokens", "build_ms"}.
"""

from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path

HERE = Path(__file__).parent
RATIO = {"nq": 0.25, "hotpot": 0.40}
RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def count_tokens(text: str) -> int:
    from llmslim import count_tokens as ct

    return ct(text)


def load(suite: str, data: Path, split: str) -> list[dict]:
    splits = json.loads((HERE / "splits_r3.json").read_text())[suite]
    items = []
    if suite == "nq":
        files = {}
        for gold in (0, 9, 19):
            with gzip.open(
                data / "nq20" / f"gold_at_{gold}.jsonl.gz", "rt", encoding="utf-8"
            ) as handle:
                files[gold] = [json.loads(line) for line in handle]
        pairs = splits["test"] if split == "test" else [[i, 9] for i in splits["dev"]]
        for index, gold in pairs:
            row = files[gold][index]
            docs = [
                f"Document [{k + 1}](Title: {d['title']}) {d['text']}"
                for k, d in enumerate(row["ctxs"])
            ]
            items.append(
                {
                    "id": f"nq{index}-g{gold}",
                    "question": row["question"],
                    "answers": row["answers"],
                    "docs": docs,
                }
            )
    else:
        rows = {
            row["id"]: row
            for row in json.loads(
                (data / "hotpot_full" / "validation.json").read_text(encoding="utf-8")
            )
        }
        for qid in splits[split]:
            row = rows[qid]
            ctx = row["context"]
            docs = [
                f"{title}: {''.join(sentences).strip()}"
                for title, sentences in zip(ctx["title"], ctx["sentences"])
            ]
            items.append(
                {
                    "id": qid,
                    "question": row["question"],
                    "answers": [row["answer"]],
                    "docs": docs,
                    "type": row["type"],
                    "level": row["level"],
                }
            )
    return items


def fit_whole(docs: list[str], order: list[int], budget: int, joiner: str) -> str:
    kept, used = [], 0
    for index in order:
        cost = count_tokens(docs[index]) + 1
        if used + cost > budget:
            continue
        kept.append(docs[index])
        used += cost
    return joiner.join(kept)


class Arms:
    def __init__(self, suite: str, device: str):
        self.suite, self.device = suite, device
        self.joiner = "\n" if suite == "nq" else "\n\n"
        self._reranker = self._lingua2 = self._long = None

    def full(self, item, budget):
        return self.joiner.join(item["docs"])

    def order(self, item, budget):
        return fit_whole(item["docs"], list(range(len(item["docs"]))), budget, self.joiner)

    def rerank(self, item, budget):
        from sentence_transformers import CrossEncoder

        if self._reranker is None:
            self._reranker = CrossEncoder(RERANKER, device=self.device)
        scores = self._reranker.predict([(item["question"], d) for d in item["docs"]])
        return fit_whole(
            item["docs"],
            sorted(range(len(item["docs"])), key=lambda i: -float(scores[i])),
            budget,
            self.joiner,
        )

    def _llmslim(self, item, budget, **options):
        from llmslim import compress_documents

        results = compress_documents(
            item["docs"], query=item["question"], target_ratio=RATIO[self.suite], **options
        )
        return self.joiner.join(r.compressed_text for r in results if r.compressed_text.strip())

    def llmslim(self, item, budget):
        return self._llmslim(item, budget)

    def llmslim_rr(self, item, budget):
        return self._llmslim(item, budget, relevance="semantic")

    def lingua2(self, item, budget):
        if self._lingua2 is None:
            from llmlingua import PromptCompressor

            self._lingua2 = PromptCompressor(
                model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                use_llmlingua2=True,
                device_map=self.device,
            )
        out = self._lingua2.compress_prompt(
            item["docs"],
            target_token=budget,
            force_tokens=["\n", "?", ".", "!"],
            drop_consecutive=True,
        )
        return out["compressed_prompt"]

    def longlingua(self, item, budget):
        if self._long is None:
            import torch
            from llmlingua import PromptCompressor

            self._long = PromptCompressor(
                model_name="NousResearch/Llama-2-7b-chat-hf",
                device_map="auto",
                model_config={"torch_dtype": torch.float16},
            )
        out = self._long.compress_prompt(
            item["docs"],
            question=item["question"],
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(RATIO), required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--split", default="test", choices=["test", "dev"])
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--sample", action="store_true", help="only the pre-registered longlingua_sample"
    )
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    items = load(args.suite, args.data, args.split)
    if args.sample:
        keep = set(
            json.loads((HERE / "splits_r3.json").read_text())[args.suite]["longlingua_sample"]
        )
        items = [item for item in items if item["id"] in keep]
    items = items[: args.limit]
    arms = Arms(args.suite, args.device)
    args.out.mkdir(parents=True, exist_ok=True)
    for arm in args.arms:
        path = args.out / f"{args.suite}_{args.split}_{arm}.jsonl"
        done = (
            {json.loads(l)["id"] for l in path.open(encoding="utf-8")} if path.exists() else set()
        )
        started_all, built = time.time(), 0
        with path.open("a", encoding="utf-8") as handle:
            for item in items:
                if item["id"] in done:
                    continue
                budget = round(RATIO[args.suite] * count_tokens("\n".join(item["docs"])))
                started = time.perf_counter()
                context = getattr(arms, arm)(item, budget)
                ms = (time.perf_counter() - started) * 1000
                handle.write(
                    json.dumps(
                        {
                            "id": item["id"],
                            "context": context,
                            "tokens": count_tokens(context),
                            "budget": budget,
                            "build_ms": round(ms, 1),
                        }
                    )
                    + "\n"
                )
                handle.flush()
                built += 1
                if built in (1, 5) or built % 100 == 0:
                    left = (time.time() - started_all) / built * (len(items) - len(done) - built)
                    print(f"{path.name}: {built} built, about {left / 60:.0f} min left", flush=True)
        print(f"{path.name}: done", flush=True)


if __name__ == "__main__":
    main()
