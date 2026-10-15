# Round 3 results: cost first

Measured 13-15 October 2026. Every system is read by the same model, Claude Haiku 5.5 (`claude-haiku-5-5`, effort
low), with the same answer prompt and the same judges; only the context changes. How the runs were kept honest, what
each system is, where Mem0 and Zep differ from their own harnesses, and everything that went wrong are in
[README.md](README.md). Every answer and judgement is in `results/`; `bash tables.sh` rebuilds every table below.

**The main criterion is cost**: what 1,000 questions cost end to end at list prices (the reader's answer call, Mem0's
and Zep's ingestion calls, and each system's build time priced as cloud machine time), against how many it gets
right. Every table marks the **cost frontier**, the arms that nothing else beats on both accuracy and cost, computed
twice: "as run", where a context that is the same for every question about a history was read from Anthropic's
prompt cache, and "no cache".

## Summary

**LoCoMo** (1,307 test questions on 8 long conversations, Mem0's judge). LLMSlim is on the cost frontier at every
budget; Mem0, Zep, LongLLMLingua and RAG are not.

| About this many tokens | LLMSlim (default) | LLMSlim + reranker | Mem0 | Zep | LongLLMLingua | LLMLingua-2 | RAG over turns |
|---|---|---|---|---|---|---|---|
| 1,000 | 87.5% for $0.67 | **90.5% for $0.70** | 88.7% for $2.43 (top 20) | | | | 78.9% for $0.68 |
| 2,500 | 91.7% for $0.89 | **93.0% for $0.95** | 91.0% for $2.66 (top 50) | 74.4% for $6.24 | 73.3% for $7.01 | 34.1% for $0.43 | 85.2% for $0.90 |
| 10,000 | **94.3% for $2.02** | | 91.6% for $3.74 (top 200) | | | 77.9% for $0.54 | 93.3% for $1.97 |

Cost per 1,000 questions. The full 27k-token history answers 95.1%: $0.83 per 1,000 when it is read from the cache
across a conversation's questions (as here, where they are asked back to back), $4.48 when it is not.

**LongMemEval-S** (180 test questions; histories of about 111k tokens; official judge). At 10,000 tokens LLMSlim
answers 77.8%, the same as the whole history, for $2.13 per 1,000 questions instead of $90.20 (prompts over 100k
tokens are billed at the higher rate). The most accurate compressed context here is not LLMSlim but RAG over turns
(dense retrieval with Qwen3-Embedding-0.6B): 80.6% at 10,000 tokens for $4.45, most of it GPU time to embed each
history. LLMSlim holds the cheaper end of the cost frontier ($0.98 to $2.13); LLMLingua-2 answers 7-16%. On the
questions the memory systems were run on:

| Sample | LLMSlim + reranker, 2,500 tokens | Mem0 top 200 | Zep | Full history |
|---|---|---|---|---|
| Mem0's 60 | 78.3% for $1.49 | 76.7% for $220.88 | | 78.3% for $90.20 |
| Zep's 24 | 87.5% for $1.43 | 83.3% for $220.84 | 58.3% for $697.56 | 91.7% for $90.22 |

Mem0's and Zep's cost is almost all ingestion: each question has its own 500-message history, and building their
memory of it costs about $0.22 (Mem0) and $0.70 (Zep) on Haiku 5.5.

**NaturalQuestions** (2,255) **and HotpotQA** (2,000), 20 and 10 retrieved passages cut to 25% and 40%. With its
reranker LLMSlim matches a plain reranker on NQ (73.5% vs 73.9%) and beats LongLLMLingua (72.7% vs 70.5% on its
sample) at a quarter of its cost; on HotpotQA the default LLMSlim (52.4%) beats the reranker (50.5%), LongLLMLingua
(50.4% vs 53.3% on its sample) and LLMLingua-2 (46.7%), at the lowest cost per correct answer of any compressor
(level with the plain reranker).

## Where LLMSlim loses

- **NQ with the default lexical mode.** 60.6%, against 73.9% for a plain reranker and 70.5% for LongLLMLingua:
  paraphrased questions need semantic matching. LLMSlim's optional reranker closes the gap (73.5%), so for
  open-domain retrieval it should be used.
- **Multi-hop and temporal questions at small budgets.** At 1,000 tokens Mem0's top 20 memories answer 88.7% to the
  default LLMSlim's 87.5% (paired difference +1.2, 95% interval -0.8 to +3.2): within noise overall, but Mem0 is
  clearly better on LoCoMo's multi-hop (88.7% vs 80.3%) and temporal (93.4% vs 85.7%) questions, where its extracted
  facts pack evidence from many sessions into few tokens. LLMSlim is better on single-hop at every budget (93.5% vs
  89.7% at 1,000). With the reranker LLMSlim is ahead overall (90.5%).
- **A cached full history.** On LoCoMo, where a conversation's questions come back to back, the cached full history
  (95.1% for $0.83) is cheaper than LLMSlim at 10,000 tokens ($2.02) and more accurate than every compressed context.
  LLMSlim is the cheaper choice when the context changes between questions, when questions arrive too far apart for
  the cache, or when the history is long enough to be billed at the long-prompt rate (LongMemEval).
- **LongMemEval against dense retrieval.** RAG over turns is ahead of LLMSlim at both budgets: 80.6% vs 77.8% at
  10,000 tokens (paired difference 2.8 points, 95% interval -3.3 to +8.9) and 76.1% vs 74.4% (LLMSlim with its
  reranker) at 2,500 (1.7 points, -4.4 to +7.2), at about twice the cost per question. Neither difference is
  significant with 180 questions, but both point the same way. On the dev questions RAG keeps 95% of the labelled
  evidence turns at 2,500 tokens and LLMSlim 83-85%, and giving LLMSlim the same embedding model as its relevance
  scorer (its `relevance=` accepts any scorer) does not close that gap (84.5%), so the difference is in how LLMSlim
  cuts and packs long turns, not in how it scores them. That is the next thing to work on. If a history is embedded
  once and asked many questions, RAG's cost falls further.
- **LongMemEval under Mem0's more lenient judge.** The full history answers 95.0% to LLMSlim's 89.4% (reranker,
  2,500 tokens); under the official judge they are level.

## LLMSlim versions

Three versions are reported (README.md has the rules): the release before this round, **v2** (turn-by-turn
transcripts, frozen before any test result was read) and **v3** (v2 plus chained rounds and quantity words, chosen on
dev only after v2's first test numbers). On LoCoMo v2 lifted the release from 84.4% to 87.5% at 1,000 tokens and
v3 is identical to v2 at every budget; on LongMemEval v3 adds 1.7 points to v2 at both budgets (official judge).
The `-nltk` rows are the `llmslim[nlp]` install, read from earlier local builds; they differ from the default
install by less than a point.

## Spend

Round 3 cost $97.57 in Claude API calls, as billed: every reader and judge call, Mem0's and Zep's ingestion, the
discarded and crashed runs described in README.md, and the dev checks (the ledger for every round so far stands at
$127.30, under the $150 cap). Batch calls were billed at half price; the tables count every answer at the list
price. Compute ran on free Kaggle notebooks (CPU and T4 GPUs) and the benchmark machine.

---

# Tables

Columns: accuracy with a 95% bootstrap interval; the paired difference from the reference LLMSlim arm on the
questions both answered; mean context tokens (tiktoken cl100k_base); median build time on the machine it ran on
(LLMSlim's lexical arms, the v2/v3 reranker arms and the full/recent/order baselines on Kaggle's CPU; the
LLMLingua family, RAG, the plain reranker and the release reranker arms on Kaggle's T4s; Mem0's and Zep's search on
the benchmark machine); reader cost per 1,000 questions as run and with no cache; memory ingestion plus build compute
per 1,000 questions; total; total per 1,000 correct answers; and the cost frontier.

