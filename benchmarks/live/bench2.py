"""Round-2 benchmarks on Claude Haiku 5.5: NaturalQuestions multi-document QA (lost-in-the-middle, 20 documents),
LongBench v2 (multiple choice, long documents) and LongMemEval-S (memory over ~50 chat sessions).

Two stages, both resumable:
  build  python bench2.py build --suite nq --arms full llmslim_global llmslim_docs truncate lingua2
         writes built/<suite>/<arm>.jsonl with the exact prompt each arm sends (compression timed locally)
  run    python bench2.py run --suite nq --arms full llmslim_global ...
         sends each prompt once and scores it; results/<suite>.jsonl

Arms (same template and model; only the context differs):
  full            the complete context
  llmslim_global  llmslim.compress(context, query=question) to the suite budget
  llmslim_docs    llmslim.compress_documents(docs, query=question) at the suite ratio (documented RAG call)
  lingua2         LLMLingua-2 (xlm-roberta-large, MeetingBank) at the same rate: the open-source standard
  truncate        the suite's natural cut to the llmslim_global token count
                  (nq: keep documents in retrieval order; lbv2: middle truncation; lme: most recent sessions)
  platform        LLMSlim Platform 0.9 prepare() at the same budget (LongMemEval only; built by platform_lme.py)
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import gzip
import json
import random
import re
import string
import sys
import time
from pathlib import Path

import haiku_client as hc

HERE = Path(__file__).parent
DATA = HERE / "data"
BUILT = HERE / "built"
RESULTS = HERE / "results"
TRUNCATE_REF = {"arm": "llmslim_global"}
SPLIT = {
    "name": "test_a"
}  # test_b: the fresh held-out sample in splits.json (built/<suite>_b, results/<suite>_b)


def tag(suite: str) -> str:
    return {"test_a": suite, "test_b": f"{suite}_b", "dev": f"{suite}_dev", "test_c": f"{suite}_c"}[
        SPLIT["name"]
    ]


def count_tokens(text: str) -> int:
    from llmslim import count_tokens as ct

    return ct(text)


# ------------------------------------------------------------------ NaturalQuestions, 20 documents

NQ_PROMPT = (
    "Write a high-quality answer for the given question using only the provided search results "
    "(some of which might be irrelevant).\n\n{context}\n\nQuestion: {question}\nAnswer:"
)


def nq_load(n: int) -> list[dict]:
    """The same n questions with the gold document first, in the middle (10th) and last (20th)."""
    per_position = max(1, n // 3)
    picks = None
    items = []
    for gold in (0, 9, 19):
        with gzip.open(DATA / "nq20" / f"gold_at_{gold}.jsonl.gz", "rt", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        if picks is None:
            picks = sorted(random.Random(2026).sample(range(len(rows)), per_position))
            if SPLIT["name"] != "test_a":
                picks = json.loads((HERE / "splits.json").read_bytes())["nq"][SPLIT["name"]][
                    :per_position
                ]
                picks = sorted(picks)
        for i in picks:
            row = rows[i]
            docs = [
                f"Document [{k + 1}](Title: {d['title']}) {d['text']}"
                for k, d in enumerate(row["ctxs"])
            ]
            items.append(
                {
                    "id": f"nq{i}-g{gold}",
                    "question": row["question"],
                    "answers": row["answers"],
                    "docs": docs,
                    "context": "\n".join(docs),
                    "meta": {"gold_at": gold},
                }
            )
    return items


def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def nq_score(item: dict, prediction: str) -> float:
    """best_subspan_em from lost-in-the-middle: a normalised gold answer appears in the normalised prediction."""
    pred = normalize(prediction)
    return float(any(normalize(a) in pred for a in item["answers"]))


# ------------------------------------------------------------------ LongBench v2 (short split)

LBV2_PROMPT = """Please read the following text and answer the question below.

<text>
{context}
</text>

What is the correct answer to this question: {question}
Choices:
(A) {A}
(B) {B}
(C) {C}
(D) {D}

Format your response as follows: "The correct answer is (insert answer here)"."""


def lbv2_load(n: int) -> list[dict]:
    rows = json.loads((DATA / "longbench_v2" / "data.json").read_bytes())
    rows = [r for r in rows if r["length"] == "short"]
    random.Random(2026).shuffle(rows)
    items = []
    for r in rows[:n]:
        # LongBench v2's own protocol: middle-truncate to the model's window (here 120k tokens) for every arm.
        context = middle_truncate(r["context"], 120_000)
        items.append(
            {
                "id": r["_id"],
                "question": r["question"],
                "answers": [r["answer"]],
                "context": context,
                "docs": None,
                "choices": {k: r[f"choice_{k}"] for k in "ABCD"},
                "meta": {"domain": r["domain"], "difficulty": r["difficulty"]},
            }
        )
    return items


def middle_truncate(text: str, budget: int) -> str:
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    ids = enc.encode(text, disallowed_special=())
    if len(ids) <= budget:
        return text
    half = budget // 2
    return enc.decode(ids[:half]) + enc.decode(ids[-half:])


def lbv2_score(item: dict, prediction: str) -> float:
    found = re.search(r"correct answer is \(?\s*([A-D])\s*\)?", prediction, re.I) or re.search(
        r"\(([A-D])\)", prediction
    )
    return float(bool(found) and found.group(1).upper() == item["answers"][0])


# ------------------------------------------------------------------ LongMemEval-S

LME_PROMPT = (
    "I will give you several history chats between you and a user. Please answer the question based on "
    "the relevant chat history.\n\n\nHistory Chats:\n\n{context}\n\nCurrent Date: {date}\nQuestion: {question}\nAnswer:"
)
LME_TYPES = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "multi-session",
    "knowledge-update",
    "temporal-reasoning",
]


def lme_session_text(index: int, date: str, session: list[dict]) -> str:
    turns = json.dumps(
        [{"role": t["role"], "content": t["content"]} for t in session], ensure_ascii=False
    )
    return f"### Session {index + 1}:\nSession Date: {date}\nSession Content:\n{turns}\n"


def lme_load(n: int) -> list[dict]:
    rows = json.loads((DATA / "longmemeval" / "longmemeval_s_cleaned.json").read_bytes())
    rng = random.Random(2026)
    per_type = max(1, n // len(LME_TYPES))
    items = []
    fresh = (
        None
        if SPLIT["name"] == "test_a"
        else set(json.loads((HERE / "splits.json").read_bytes())["lme"][SPLIT["name"]])
    )
    for qtype in LME_TYPES:
        group = [r for r in rows if r["question_type"] == qtype]
        chosen = (
            rng.sample(group, min(per_type, len(group)))
            if fresh is None
            else [r for r in group if r["question_id"] in fresh]
        )
        for r in chosen:
            docs = [
                lme_session_text(i, d, s)
                for i, (d, s) in enumerate(zip(r["haystack_dates"], r["haystack_sessions"]))
            ]
            items.append(
                {
                    "id": r["question_id"],
                    "question": r["question"],
                    "answers": [str(r["answer"])],
                    "docs": docs,
                    "context": "\n".join(docs),
                    "date": r["question_date"],
                    "meta": {
                        "type": qtype,
                        "abstention": r["question_id"].endswith("_abs"),
                        "sessions": r["haystack_sessions"],
                        "dates": r["haystack_dates"],
                    },
                }
            )
    return items


JUDGE = {
    "default": (
        "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response "
        "contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or "
        "contains all the intermediate steps to get the correct answer, you should also answer yes. If the response "
        "only contains a subset of the information required by the answer, answer no. \n\nQuestion: {q}\n\nCorrect "
        "Answer: {a}\n\nModel Response: {r}\n\nIs the model response correct? Answer yes or no only."
    ),
    "temporal-reasoning": (
        "I will give you a question, a correct answer, and a response from a model. Please answer yes if the "
        "response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct "
        "answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the "
        "response only contains a subset of the information required by the answer, answer no. In addition, do not "
        "penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, "
        "etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's "
        "response is still correct. \n\nQuestion: {q}\n\nCorrect Answer: {a}\n\nModel Response: {r}\n\nIs the model "
        "response correct? Answer yes or no only."
    ),
    "knowledge-update": (
        "I will give you a question, a correct answer, and a response from a model. Please answer yes if the "
        "response contains the correct answer. Otherwise, answer no. If the response contains some previous information "
        "along with an updated answer, the response should be considered as correct as long as the updated answer is the "
        "required answer.\n\nQuestion: {q}\n\nCorrect Answer: {a}\n\nModel Response: {r}\n\nIs the model response "
        "correct? Answer yes or no only."
    ),
    "single-session-preference": (
        "I will give you a question, a rubric for desired personalized response, and a response from a "
        "model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does "
        "not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the "
        "user's personal information correctly.\n\nQuestion: {q}\n\nRubric: {a}\n\nModel Response: {r}\n\nIs the model "
        "response correct? Answer yes or no only."
    ),
    "abstention": (
        "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if "
        "the model correctly identifies the question as unanswerable. The model could say that the information is "
        "incomplete, or some other information is given but the asked information is not.\n\nQuestion: {q}\n\n"
        "Explanation: {a}\n\nModel Response: {r}\n\nDoes the model correctly identify the question as unanswerable? "
        "Answer yes or no only."
    ),
}


def lme_judge(api, item: dict, prediction: str) -> tuple[float, float]:
    key = (
        "abstention"
        if item["meta"]["abstention"]
        else (item["meta"]["type"] if item["meta"]["type"] in JUDGE else "default")
    )
    prompt = JUDGE[key].format(q=item["question"], a=item["answers"][0], r=prediction)
    response, _, usd = hc.call(api, max_tokens=512, messages=[{"role": "user", "content": prompt}])
    return float("yes" in hc.text_of(response).strip().lower()[:12]), usd


# ------------------------------------------------------------------ suite table

SUITES = {
    "nq": {
        "load": nq_load,
        "budget": ("ratio", 0.25),
        "max_tokens": 1024,
        "render": lambda it, ctx: NQ_PROMPT.format(context=ctx, question=it["question"]),
    },
    "lbv2": {
        "load": lbv2_load,
        "budget": ("ratio", 0.25),
        "max_tokens": 2048,
        "render": lambda it, ctx: LBV2_PROMPT.format(
            context=ctx, question=it["question"], **it["choices"]
        ),
    },
    "lme": {
        "load": lme_load,
        "budget": ("tokens", 8000),
        "max_tokens": 1536,
        "render": lambda it, ctx: LME_PROMPT.format(
            context=ctx, date=it["date"], question=it["question"]
        ),
    },
}


def query_of(item: dict) -> str:
    if item.get("choices"):
        return item["question"] + "\n" + "\n".join(item["choices"].values())
    return item["question"]


def target_ratio(suite: str, item: dict) -> float:
    kind, value = SUITES[suite]["budget"]
    if kind == "ratio":
        return value
    return min(1.0, value / max(1, count_tokens(item["context"])))


# ------------------------------------------------------------------ arm builders (context text only)


def arm_full(suite, item):
    return item["context"]


def arm_llmslim_global(suite, item, **options):
    from llmslim import compress

    ratio = target_ratio(suite, item)
    return (
        item["context"]
        if ratio >= 1
        else compress(
            item["context"], target_ratio=ratio, query=query_of(item), **options
        ).compressed_text
    )


def arm_llmslim_docs(suite, item, **options):
    from llmslim import compress_documents

    if not item.get("docs"):
        return arm_llmslim_global(suite, item, **options)
    ratio = target_ratio(suite, item)
    results = compress_documents(item["docs"], query=query_of(item), target_ratio=ratio, **options)
    return "\n".join(r.compressed_text for r in results if r.compressed_text.strip())


_LINGUA = None


def arm_lingua2(suite, item):
    global _LINGUA
    if _LINGUA is None:
        from llmlingua import PromptCompressor

        _LINGUA = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
            use_llmlingua2=True,
            device_map=LINGUA_DEVICE,
        )
    ratio = target_ratio(suite, item)
    if ratio >= 1:
        return item["context"]
    context = item["docs"] if item.get("docs") else [item["context"]]
    out = _LINGUA.compress_prompt(
        context, rate=ratio, force_tokens=["\n", "?", ".", "!"], drop_consecutive=True
    )
    return out["compressed_prompt"]


_LONG = None


def arm_longllmlingua(suite, item):
    """LongLLMLingua (Jiang et al., 2024) with the paper's NaturalQuestions settings: question-aware coarse-to-fine
    compression, document reordering and dynamic ratios, scored by LLaMA-2-7B-chat (here in 4-bit to fit a 6 GB GPU),
    held to the same token budget as LLMSlim."""
    global _LONG
    if _LONG is None:
        import torch
        from llmlingua import PromptCompressor
        from transformers import BitsAndBytesConfig

        quant = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4"
        )
        _LONG = PromptCompressor(
            model_name="NousResearch/Llama-2-7b-chat-hf",
            device_map="auto",
            model_config={"quantization_config": quant},
        )
    ratio = target_ratio(suite, item)
    if ratio >= 1:
        return item["context"]
    budget = round(ratio * count_tokens(item["context"]))
    out = _LONG.compress_prompt(
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


def arm_lingua2_eq(suite, item):
    """LLMLingua-2 held to LLMSlim's token budget: asked for `rate=0.25`, it keeps ~16% (its rate counts its own
    tokens), so this arm passes the budget in tokens instead."""
    global _LINGUA
    if _LINGUA is None:
        from llmlingua import PromptCompressor

        _LINGUA = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
            use_llmlingua2=True,
            device_map=LINGUA_DEVICE,
        )
    ratio = target_ratio(suite, item)
    if ratio >= 1:
        return item["context"]
    budget = round(ratio * count_tokens(item["context"]))
    context = item["docs"] if item.get("docs") else [item["context"]]
    out = _LINGUA.compress_prompt(
        context, target_token=budget, force_tokens=["\n", "?", ".", "!"], drop_consecutive=True
    )
    return out["compressed_prompt"]


def arm_truncate(suite, item, budget_tokens: int):
    if suite == "nq":
        kept, used = [], 0
        for doc in item["docs"]:
            cost = count_tokens(doc)
            if used + cost > budget_tokens:
                break
            kept.append(doc)
            used += cost
        return "\n".join(kept)
    if suite == "lme":
        kept, used = [], 0
        for doc in reversed(item["docs"]):
            cost = count_tokens(doc)
            if used + cost > budget_tokens:
                break
            kept.append(doc)
            used += cost
        return "\n".join(reversed(kept))
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    ids = enc.encode(item["context"], disallowed_special=())
    if len(ids) <= budget_tokens:
        return item["context"]
    half = budget_tokens // 2
    return enc.decode(ids[:half]) + enc.decode(ids[-half:])


STRIDE = {"lingua2": 2, "lingua2_eq": 2, "longllmlingua": 2}
LINGUA_DEVICE = __import__("os").environ.get(
    "LINGUA_DEVICE", "cpu"
)  # LLMLingua-2 runs on every second question (CPU cost)
BUILDERS = {
    "full": arm_full,
    "llmslim_global": arm_llmslim_global,
    "llmslim_docs": arm_llmslim_docs,
    "lingua2": arm_lingua2,
    "lingua2_eq": arm_lingua2_eq,
    "longllmlingua": arm_longllmlingua,
}
# The same calls under the v0.8 source (run with the Core worktree on the import path); v0.7.2 arms keep their names.
BUILDERS.update({"llmslim08_global": arm_llmslim_global, "llmslim08_docs": arm_llmslim_docs})
BUILDERS.update(
    {"core080_global": arm_llmslim_global, "core080_docs": arm_llmslim_docs}
)  # final 0.8.0


# Frozen 0.8.0 release candidate: lexical (default) and with the reranker.
BUILDERS.update(
    {
        "core08f_global": arm_llmslim_global,
        "core08f_docs": arm_llmslim_docs,
        "core08s_global": lambda s, it: arm_llmslim_global(s, it, relevance="semantic"),
        "core08s_docs": lambda s, it: arm_llmslim_docs(s, it, relevance="semantic"),
    }
)


def _build_one(job):
    suite, arm, item = job
    started = time.perf_counter()
    context = BUILDERS[arm](suite, item)
    ms = (time.perf_counter() - started) * 1000
    return {
        "id": item["id"],
        "context_tokens": count_tokens(context),
        "ms": round(ms, 1),
        "prompt": SUITES[suite]["render"](item, context),
    }


def build(suite: str, arms: list[str], n: int, workers: int) -> None:
    import llmslim

    items = SUITES[suite]["load"](n)
    out_dir = BUILT / tag(suite)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(
        json.dumps({"llmslim": llmslim.__version__, "n": len(items)})
    )
    for arm in arms:
        if arm in ("truncate", "platform"):
            continue
        path = out_dir / f"{arm}.jsonl"
        done = (
            {
                json.loads(l)["id"]
                for l in path.read_bytes().decode("utf-8").split(chr(10))
                if l.strip()
            }
            if path.exists()
            else set()
        )
        # A slow compressor (LLMLingua-2 on CPU) can run on every k-th question; items are position-major,
        # so a stride keeps the answer-position split balanced.
        todo = [
            (suite, arm, it)
            for i, it in enumerate(items)
            if it["id"] not in done and i % STRIDE.get(arm, 1) == 0
        ]
        started = time.perf_counter()
        pool_size = 1 if "lingua" in arm else workers
        with path.open("a", encoding="utf-8") as sink:
            if pool_size == 1:
                results = map(_build_one, todo)
            else:
                pool = cf.ProcessPoolExecutor(pool_size)
                results = pool.map(_build_one, todo, chunksize=1)
            for row in results:
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()
        print(
            f"{suite}/{arm}: built {len(todo)} in {time.perf_counter() - started:.0f}s", flush=True
        )
    if "truncate" in arms:
        reference = {
            json.loads(l)["id"]: json.loads(l)["context_tokens"]
            for l in (out_dir / f"{TRUNCATE_REF['arm']}.jsonl")
            .read_bytes()
            .decode("utf-8")
            .split(chr(10))
            if l.strip()
        }
        with (out_dir / "truncate.jsonl").open("w", encoding="utf-8") as sink:
            for it in items:
                context = arm_truncate(suite, it, reference[it["id"]])
                sink.write(
                    json.dumps(
                        {
                            "id": it["id"],
                            "context_tokens": count_tokens(context),
                            "ms": 0,
                            "prompt": SUITES[suite]["render"](it, context),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        print(f"{suite}/truncate: built {len(items)}", flush=True)


def run(suite: str, arms: list[str], n: int, workers: int) -> None:
    items = {it["id"]: it for it in SUITES[suite]["load"](n)}
    out = RESULTS / f"{tag(suite)}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {
            (json.loads(l)["id"], json.loads(l)["arm"])
            for l in out.read_bytes().decode("utf-8").split(chr(10))
            if l.strip()
        }
        if out.exists()
        else set()
    )
    jobs = []
    for arm in arms:
        for line in (
            (BUILT / tag(suite) / f"{arm}.jsonl").read_bytes().decode("utf-8").split(chr(10))
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if row["id"] in items and (row["id"], arm) not in done:
                jobs.append((arm, row))
    api = hc.client()
    print(f"{suite}: {len(jobs)} calls; spent so far ${hc.spent():.2f}", flush=True)

    def one(job):
        arm, row = job
        item = items[row["id"]]
        if (
            "request" in row
        ):  # LLMSlim Platform: its compiled request (system + messages), sent unchanged
            response, seconds, usd = hc.call(
                api, max_tokens=SUITES[suite]["max_tokens"], **row["request"]
            )
        else:
            response, seconds, usd = hc.call(
                api,
                max_tokens=SUITES[suite]["max_tokens"],
                messages=[{"role": "user", "content": row["prompt"]}],
            )
        prediction = hc.text_of(response)
        judge_usd = 0.0
        if suite == "lme":
            score, judge_usd = lme_judge(api, item, prediction)
        else:
            score = (nq_score if suite == "nq" else lbv2_score)(item, prediction)
        u = response.usage
        return {
            "suite": suite,
            "id": row["id"],
            "arm": arm,
            "score": score,
            "meta": {k: v for k, v in item["meta"].items() if k not in ("sessions", "dates")},
            "context_tokens": row["context_tokens"],
            "build_ms": row["ms"],
            "prompt_tokens": hc.prompt_tokens(u),
            "output_tokens": u.output_tokens,
            "usd": round(usd, 6),
            "judge_usd": round(judge_usd, 6),
            "seconds": round(seconds, 2),
            "stop": response.stop_reason,
            "prediction": prediction[:600],
        }

    with out.open("a", encoding="utf-8") as sink, cf.ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(one, job) for job in jobs]
        for future in cf.as_completed(futures):
            try:
                sink.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
                sink.flush()
            except hc.BudgetExceeded as error:
                print("STOP:", error, flush=True)
                pool.shutdown(cancel_futures=True)
                break
            except Exception as error:  # noqa: BLE001
                print("call failed:", type(error).__name__, str(error)[:200], flush=True)
    print(f"{suite}: done; spent ${hc.spent():.2f}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["build", "run"])
    parser.add_argument("--suite", required=True, choices=list(SUITES))
    parser.add_argument("--arms", nargs="+", required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--split", default="test_a", choices=["test_a", "test_b", "dev", "test_c"])
    parser.add_argument(
        "--truncate-ref",
        default="llmslim_global",
        help="arm whose token counts the truncate arm matches",
    )
    args = parser.parse_args()
    SPLIT["name"] = args.split
    TRUNCATE_REF["arm"] = args.truncate_ref
    (build if args.stage == "build" else run)(args.suite, args.arms, args.n, args.workers)


if __name__ == "__main__":
    sys.exit(main())
