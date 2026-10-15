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
tokens are billed at the higher rate). On the questions the memory systems were run on:

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

About $135 of Claude API calls in all (cap $150), including every reader call, judge call, Mem0's and Zep's
ingestion, the discarded and crashed runs described in README.md, and the dev checks. Batch calls are billed at half
price; the tables count every answer at the list price.

---

# Tables

Columns: accuracy with a 95% bootstrap interval; the paired difference from the reference LLMSlim arm on the
questions both answered; mean context tokens (tiktoken cl100k_base); median build time on the machine it ran on
(LLMSlim's lexical arms, the v2/v3 reranker arms and the full/recent/order baselines on Kaggle's CPU; the
LLMLingua family, RAG, the plain reranker and the release reranker arms on Kaggle's T4s; Mem0's and Zep's search on
the benchmark machine); reader cost per 1,000 questions as run and with no cache; memory ingestion plus build compute
per 1,000 questions; total; total per 1,000 correct answers; and the cost frontier.

## LoCoMo, about 1,000 tokens
| Arm | n | score (95% CI) | vs llmslim-v3_1000 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| llmslim_rr-v3_1000 | 1307 | 90.5 (88.9-92.0) | +3.1 (+1.7, +4.5), n=1307 | 994 | 1,564 | 0.67 | 0.67 | 0.04 | 0.70 | 0.78 | as run, no cache |
| mem0_top20 | 1307 | 88.7 (86.9-90.4) | +1.2 (-0.8, +3.1), n=1307 | 976 | 150 | 0.67 | 0.67 | 1.76 | 2.43 | 2.74 |  |
| llmslim-v2_1000 | 1307 | 87.5 (85.5-89.3) | +0.0 (-1.3, +1.1), n=1307 | 994 | 104 | 0.66 | 0.66 | 0.00 | 0.66 | 0.76 | as run, no cache |
| llmslim-v3_1000 | 1307 | 87.5 (85.5-89.3) |  | 994 | 110 | 0.66 | 0.66 | 0.00 | 0.67 | 0.76 |  |
| llmslim_1000 | 1307 | 84.4 (82.5-86.3) | -3.1 (-4.7, -1.3), n=1307 | 1,006 | 116 | 0.67 | 0.67 | 0.00 | 0.67 | 0.79 |  |
| rag_1000 | 1307 | 78.9 (76.7-81.1) | -8.6 (-10.9, -6.3), n=1307 | 970 | 71 | 0.67 | 0.67 | 0.01 | 0.68 | 0.86 |  |

## LoCoMo, about 2,500 tokens
| Arm | n | score (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| llmslim_rr-v3_2500 | 1307 | 93.0 (91.5-94.3) | +1.2 (+0.2, +2.3), n=1307 | 2,495 | 2,360 | 0.90 | 0.90 | 0.06 | 0.95 | 1.03 | as run, no cache |
| llmslim-v3_2500 | 1307 | 91.7 (90.3-93.3) |  | 2,492 | 103 | 0.89 | 0.89 | 0.00 | 0.89 | 0.97 | as run, no cache |
| llmslim-v2_2500 | 1307 | 91.7 (90.2-93.1) | -0.1 (-1.1, +0.9), n=1307 | 2,492 | 103 | 0.89 | 0.89 | 0.00 | 0.89 | 0.97 | as run, no cache |
| mem0_top50 | 1307 | 91.0 (89.4-92.5) | -0.8 (-2.5, +0.9), n=1307 | 2,425 | 150 | 0.90 | 0.90 | 1.76 | 2.66 | 2.92 |  |
| llmslim_2500 | 1307 | 90.9 (89.3-92.4) | -0.8 (-2.1, +0.3), n=1307 | 2,501 | 112 | 0.88 | 0.88 | 0.00 | 0.88 | 0.97 | as run, no cache |
| rag_2500 | 1307 | 85.2 (83.2-87.0) | -6.6 (-8.6, -4.6), n=1307 | 2,430 | 71 | 0.88 | 0.88 | 0.01 | 0.90 | 1.05 |  |
| zep | 1307 | 74.4 (72.0-76.7) | -17.3 (-19.7, -14.8), n=1307 | 2,738 | 14,825 | 0.95 | 0.95 | 5.29 | 6.24 | 8.38 |  |
| longlingua_2500 | 300 | 73.3 (68.0-78.0) | -18.3 (-23.3, -13.3), n=300 | 2,005 | 42,934 | 0.81 | 0.81 | 6.20 | 7.01 | 9.56 |  |
| lingua2_2500 | 1307 | 34.1 (31.6-36.7) | -57.6 (-60.6, -54.8), n=1307 | 1,988 | 10,633 | 0.42 | 0.90 | 0.01 | 0.43 | 1.25 | as run |
| recent_2500 | 1307 | 20.7 (18.5-22.9) | -71.0 (-73.5, -68.4), n=1307 | 2,438 | 18 | 0.37 | 0.90 | 0.00 | 0.37 | 1.80 | as run |

## LoCoMo, about 10,000 tokens and the full history
| Arm | n | score (95% CI) | vs llmslim-v3_10000 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 1307 | 95.1 (93.9-96.3) | +0.8 (-0.2, +1.8), n=1307 | 27,133 | 3 | 0.83 | 4.48 | 0.00 | 0.83 | 0.87 | as run, no cache |
| llmslim-v2_10000 | 1307 | 94.3 (93.0-95.6) | +0.0 (-0.8, +0.8), n=1307 | 9,999 | 114 | 2.01 | 2.01 | 0.00 | 2.02 | 2.14 | no cache |
| llmslim-v3_10000 | 1307 | 94.3 (93.0-95.6) |  | 9,997 | 111 | 2.02 | 2.02 | 0.00 | 2.02 | 2.14 |  |
| llmslim_10000 | 1307 | 94.0 (92.7-95.2) | -0.3 (-1.2, +0.6), n=1307 | 9,998 | 115 | 1.96 | 1.96 | 0.00 | 1.96 | 2.09 | no cache |
| rag_10000 | 1307 | 93.3 (92.0-94.7) | -1.0 (-2.3, +0.2), n=1307 | 9,738 | 71 | 1.96 | 1.96 | 0.01 | 1.97 | 2.11 |  |
| mem0_top200 | 1307 | 91.6 (90.1-93.0) | -2.7 (-4.1, -1.2), n=1307 | 9,628 | 150 | 1.98 | 1.98 | 1.76 | 3.74 | 4.08 |  |
| lingua2_10000 | 1307 | 77.9 (75.6-80.1) | -16.4 (-18.6, -13.9), n=1307 | 7,904 | 15,598 | 0.53 | 2.01 | 0.01 | 0.54 | 0.70 | as run |

## LoCoMo, token F1 (no judge)
| Arm | n | f1 (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| llmslim-v3_10000 | 1307 | 32.5 (31.0-34.1) | +0.8 (-0.5, +2.0), n=1307 | 9,997 | 111 | 2.02 | 2.02 | 0.00 | 2.02 | 6.21 | as run, no cache |
| full | 1307 | 32.3 (30.9-33.8) | +0.6 (-0.7, +1.9), n=1307 | 27,133 | 3 | 0.83 | 4.48 | 0.00 | 0.83 | 2.56 | as run |
| llmslim-v3_2500 | 1307 | 31.7 (30.2-33.2) |  | 2,492 | 103 | 0.89 | 0.89 | 0.00 | 0.89 | 2.81 | no cache |
| llmslim-v3_1000 | 1307 | 31.2 (29.7-32.8) | -0.5 (-1.9, +0.8), n=1307 | 994 | 110 | 0.66 | 0.66 | 0.00 | 0.67 | 2.14 | as run, no cache |
| mem0_top200 | 1307 | 30.8 (29.3-32.4) | -0.9 (-2.3, +0.4), n=1307 | 9,628 | 150 | 1.98 | 1.98 | 1.76 | 3.74 | 12.14 |  |
| mem0_top50 | 1307 | 30.4 (28.9-31.8) | -1.4 (-2.8, +0.2), n=1307 | 2,425 | 150 | 0.90 | 0.90 | 1.76 | 2.66 | 8.75 |  |
| mem0_top20 | 1307 | 30.2 (28.7-31.8) | -1.5 (-2.9, -0.1), n=1307 | 976 | 150 | 0.67 | 0.67 | 1.76 | 2.43 | 8.03 |  |
| rag_2500 | 1307 | 29.1 (27.7-30.7) | -2.6 (-4.0, -1.2), n=1307 | 2,430 | 71 | 0.88 | 0.88 | 0.01 | 0.90 | 3.08 |  |
| longlingua_2500 | 300 | 25.7 (22.5-28.8) | -4.9 (-8.0, -2.0), n=300 | 2,005 | 42,934 | 0.81 | 0.81 | 6.20 | 7.01 | 27.26 |  |
| zep | 1307 | 21.3 (20.0-22.6) | -10.5 (-12.0, -8.9), n=1307 | 2,738 | 14,825 | 0.95 | 0.95 | 5.29 | 6.24 | 29.34 |  |
| lingua2_2500 | 1307 | 10.4 (9.5-11.4) | -21.3 (-23.0, -19.8), n=1307 | 1,988 | 10,633 | 0.42 | 0.90 | 0.01 | 0.43 | 4.09 | as run |

## LoCoMo, LLMSlim with the [nlp] extra (NLTK sentence splitter)
| Arm | n | score (95% CI) | vs llmslim-v2-nltk_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| llmslim-v2-nltk_10000 | 1307 | 93.7 (92.3-95.0) | +1.9 (+0.7, +3.2), n=1307 | 9,999 | 57 | 2.02 | 2.02 | 0.00 | 2.02 | 2.16 | as run, no cache |
| llmslim-v2-nltk_2500 | 1307 | 91.8 (90.4-93.2) |  | 2,492 | 137 | 0.89 | 0.89 | 0.00 | 0.89 | 0.97 | as run, no cache |
| llmslim-nltk_2500 | 1307 | 90.5 (89.0-92.0) | -1.3 (-2.3, -0.3), n=1307 | 2,501 | 199 | 0.88 | 0.88 | 0.01 | 0.88 | 0.98 | as run, no cache |
| llmslim-v2-nltk_1000 | 1307 | 87.7 (85.8-89.4) | -4.1 (-5.4, -2.8), n=1307 | 994 | 131 | 0.66 | 0.66 | 0.00 | 0.66 | 0.76 | as run, no cache |
| llmslim-nltk_1000 | 1307 | 84.6 (82.6-86.6) | -7.2 (-8.8, -5.6), n=1307 | 1,006 | 184 | 0.67 | 0.67 | 0.01 | 0.67 | 0.80 |  |

## nq
| Arm | n | score (95% CI) | vs llmslim_rr-v3 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 2255 | 78.4 (76.5-80.0) | +4.8 (+3.1, +6.5), n=2255 | 2,908 | 0 | 0.65 | 0.65 | 0.00 | 0.65 | 0.83 | as run, no cache |
| rerank | 2255 | 73.9 (72.1-75.7) | +0.4 (-1.2, +2.1), n=2255 | 686 | 40 | 0.29 | 0.29 | 0.01 | 0.30 | 0.40 | as run, no cache |
| llmslim_rr | 2255 | 73.6 (71.9-75.4) | +0.1 (-1.1, +1.2), n=2255 | 668 | 71 | 0.29 | 0.29 | 0.01 | 0.30 | 0.41 |  |
| llmslim_rr-v3 | 2255 | 73.5 (71.7-75.3) |  | 668 | 1,260 | 0.29 | 0.29 | 0.03 | 0.33 | 0.44 |  |
| llmslim | 2255 | 61.4 (59.5-63.4) | -12.1 (-14.0, -10.2), n=2255 | 660 | 14 | 0.30 | 0.30 | 0.00 | 0.30 | 0.48 |  |
| llmslim-nltk | 2255 | 60.8 (58.7-62.8) | -12.7 (-14.7, -10.8), n=2255 | 660 | 26 | 0.30 | 0.30 | 0.00 | 0.30 | 0.49 |  |
| llmslim-v3 | 2255 | 60.6 (58.6-62.6) | -12.9 (-14.8, -11.0), n=2255 | 660 | 18 | 0.29 | 0.29 | 0.00 | 0.30 | 0.49 |  |
| order | 2255 | 55.9 (53.9-58.0) | -17.6 (-20.0, -15.4), n=2255 | 692 | 2 | 0.30 | 0.30 | 0.00 | 0.30 | 0.54 |  |
| lingua2 | 2255 | 52.5 (50.5-54.5) | -21.0 (-23.1, -18.7), n=2255 | 684 | 3,548 | 0.34 | 0.34 | 0.52 | 0.87 | 1.65 |  |

## nq, LongLLMLingua's 1,000-question sample
| Arm | n | score (95% CI) | vs llmslim_rr-v3 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 1000 | 77.2 (74.5-79.8) | +4.5 (+2.0, +7.0), n=1000 | 2,907 | 0 | 0.65 | 0.65 | 0.00 | 0.65 | 0.84 | as run, no cache |
| rerank | 1000 | 73.6 (70.9-76.4) | +0.9 (-1.5, +3.5), n=1000 | 688 | 40 | 0.29 | 0.29 | 0.01 | 0.29 | 0.40 | as run, no cache |
| llmslim_rr-v3 | 1000 | 72.7 (70.0-75.4) |  | 668 | 1,252 | 0.30 | 0.30 | 0.03 | 0.33 | 0.45 |  |
| longlingua | 1000 | 70.5 (67.7-73.3) | -2.2 (-5.3, +0.8), n=1000 | 636 | 6,899 | 0.29 | 0.29 | 1.03 | 1.32 | 1.87 |  |
| llmslim-v3 | 1000 | 59.6 (56.5-62.6) | -13.1 (-15.9, -10.3), n=1000 | 659 | 18 | 0.30 | 0.30 | 0.00 | 0.30 | 0.50 |  |
| lingua2 | 1000 | 52.0 (48.9-55.1) | -20.7 (-24.2, -17.2), n=1000 | 683 | 3,548 | 0.34 | 0.34 | 0.52 | 0.86 | 1.66 |  |

## hotpot
| Arm | n | score (95% CI) | vs llmslim_rr-v3 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 2000 | 58.0 (55.9-60.2) | +5.8 (+4.1, +7.4), n=2000 | 1,315 | 0 | 0.24 | 0.24 | 0.00 | 0.24 | 0.41 | as run, no cache |
| llmslim_rr | 2000 | 53.0 (50.9-55.1) | +0.8 (-0.3, +1.8), n=2000 | 522 | 42 | 0.13 | 0.13 | 0.01 | 0.14 | 0.26 | as run, no cache |
| llmslim-v3 | 2000 | 52.4 (50.2-54.7) | +0.2 (-1.3, +1.8), n=2000 | 522 | 8 | 0.13 | 0.13 | 0.00 | 0.13 | 0.25 | as run, no cache |
| llmslim | 2000 | 52.3 (50.2-54.4) | +0.1 (-1.5, +1.7), n=2000 | 522 | 6 | 0.13 | 0.13 | 0.00 | 0.13 | 0.25 |  |
| llmslim-nltk | 2000 | 52.2 (50.1-54.5) | +0.0 (-1.5, +1.6), n=2000 | 522 | 10 | 0.13 | 0.13 | 0.00 | 0.13 | 0.25 |  |
| llmslim_rr-v3 | 2000 | 52.2 (50.0-54.4) |  | 522 | 681 | 0.13 | 0.13 | 0.02 | 0.15 | 0.29 |  |
| rerank | 2000 | 50.5 (48.4-52.6) | -1.8 (-3.5, +0.1), n=2000 | 487 | 29 | 0.12 | 0.12 | 0.01 | 0.13 | 0.25 | as run, no cache |
| lingua2 | 2000 | 46.7 (44.6-48.9) | -5.5 (-7.6, -3.5), n=2000 | 491 | 2,130 | 0.16 | 0.16 | 0.31 | 0.47 | 1.01 |  |
| order | 2000 | 36.1 (34.1-38.2) | -16.1 (-18.2, -13.8), n=2000 | 491 | 1 | 0.16 | 0.16 | 0.00 | 0.16 | 0.43 |  |

## hotpot, LongLLMLingua's 1,000-question sample
| Arm | n | score (95% CI) | vs llmslim_rr-v3 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 1000 | 58.5 (55.5-61.5) | +5.7 (+3.4, +8.0), n=1000 | 1,318 | 0 | 0.24 | 0.24 | 0.00 | 0.24 | 0.41 | as run, no cache |
| llmslim-v3 | 1000 | 53.3 (50.0-56.4) | +0.5 (-1.7, +2.7), n=1000 | 523 | 8 | 0.13 | 0.13 | 0.00 | 0.13 | 0.24 | as run, no cache |
| llmslim_rr-v3 | 1000 | 52.8 (49.7-55.8) |  | 523 | 679 | 0.13 | 0.13 | 0.02 | 0.15 | 0.29 |  |
| rerank | 1000 | 51.6 (48.4-54.7) | -1.2 (-3.6, +1.3), n=1000 | 488 | 29 | 0.12 | 0.12 | 0.00 | 0.13 | 0.24 | as run, no cache |
| longlingua | 1000 | 50.4 (47.4-53.5) | -2.4 (-5.3, +0.4), n=1000 | 449 | 4,220 | 0.13 | 0.13 | 0.64 | 0.77 | 1.52 |  |
| lingua2 | 1000 | 48.9 (45.7-52.1) | -3.9 (-7.0, -0.8), n=1000 | 492 | 2,130 | 0.16 | 0.16 | 0.31 | 0.47 | 0.96 |  |

## LongMemEval-S, 180 questions (score)
| Arm | n | score (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 180 | 77.8 (71.7-83.3) | +7.2 (+1.1, +13.3), n=180 | 111,372 | 1 | 90.21 | 90.21 | 0.00 | 90.21 | 115.98 |  |
| llmslim-v3_10000 | 180 | 77.8 (71.7-83.9) | +7.2 (+1.1, +12.8), n=180 | 10,008 | 514 | 2.12 | 2.12 | 0.01 | 2.13 | 2.74 | as run, no cache |
| llmslim-v2_10000 | 180 | 76.1 (70.0-82.8) | +5.6 (-1.1, +12.2), n=180 | 10,008 | 507 | 2.12 | 2.12 | 0.01 | 2.13 | 2.80 | as run, no cache |
| llmslim_rr-v3_10000 | 180 | 74.4 (68.3-81.1) | +3.9 (-1.1, +9.4), n=180 | 10,007 | 3,725 | 2.11 | 2.11 | 0.09 | 2.21 | 2.97 |  |
| llmslim_rr-v3_2500 | 180 | 74.4 (67.8-80.6) | +3.9 (-1.7, +9.4), n=180 | 2,501 | 3,405 | 0.96 | 0.96 | 0.09 | 1.05 | 1.41 | as run, no cache |
| llmslim-v3_2500 | 180 | 70.6 (63.9-77.2) |  | 2,501 | 562 | 0.96 | 0.96 | 0.01 | 0.98 | 1.38 | as run, no cache |
| llmslim-v2_2500 | 180 | 68.9 (62.2-75.6) | -1.7 (-7.2, +3.9), n=180 | 2,501 | 570 | 0.96 | 0.96 | 0.01 | 0.97 | 1.41 | as run, no cache |
| recent_10000 | 180 | 11.1 (6.7-16.1) | -59.4 (-66.7, -52.2), n=180 | 9,948 | 50 | 2.09 | 2.09 | 0.00 | 2.09 | 18.78 |  |
| recent_2500 | 180 | 8.3 (4.4-12.8) | -62.2 (-69.4, -55.0), n=180 | 2,480 | 54 | 0.90 | 0.90 | 0.00 | 0.90 | 10.77 | as run, no cache |

## LongMemEval-S, 180 questions (score_mem0_judge)
| Arm | n | score_mem0_judge (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 180 | 95.0 (91.7-97.8) | +12.2 (+7.2, +17.8), n=180 | 111,372 | 1 | 90.21 | 90.21 | 0.00 | 90.21 | 94.95 | as run, no cache |
| llmslim_rr-v3_2500 | 180 | 89.4 (85.0-93.3) | +6.7 (+3.3, +10.6), n=180 | 2,501 | 3,405 | 0.96 | 0.96 | 0.09 | 1.05 | 1.17 | as run, no cache |
| llmslim-v3_10000 | 180 | 88.9 (84.4-93.3) | +6.1 (+1.7, +10.6), n=180 | 10,008 | 514 | 2.12 | 2.12 | 0.01 | 2.13 | 2.40 |  |
| llmslim-v2_10000 | 180 | 87.8 (82.8-92.2) | +5.0 (+0.6, +9.4), n=180 | 10,008 | 507 | 2.12 | 2.12 | 0.01 | 2.13 | 2.43 |  |
| llmslim_rr-v3_10000 | 180 | 86.7 (81.7-91.7) | +3.9 (+0.0, +8.3), n=180 | 10,007 | 3,725 | 2.11 | 2.11 | 0.09 | 2.21 | 2.55 |  |
| llmslim-v3_2500 | 180 | 82.8 (77.2-87.8) |  | 2,501 | 562 | 0.96 | 0.96 | 0.01 | 0.98 | 1.18 | as run, no cache |
| llmslim-v2_2500 | 180 | 80.6 (75.0-86.1) | -2.2 (-6.1, +1.7), n=180 | 2,501 | 570 | 0.96 | 0.96 | 0.01 | 0.97 | 1.20 | as run, no cache |
| recent_10000 | 180 | 14.4 (9.4-20.0) | -68.3 (-75.0, -61.7), n=180 | 9,948 | 50 | 2.09 | 2.09 | 0.00 | 2.09 | 14.45 |  |
| recent_2500 | 180 | 11.1 (6.7-15.6) | -71.7 (-78.3, -65.6), n=180 | 2,480 | 54 | 0.90 | 0.90 | 0.00 | 0.90 | 8.08 | as run, no cache |

## LongMemEval-S, Mem0's 60-question sample (score)
| Arm | n | score (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 60 | 78.3 (68.3-88.3) | +6.7 (-1.7, +15.0), n=60 | 111,417 | 1 | 90.20 | 90.20 | 0.00 | 90.20 | 115.15 |  |
| llmslim_rr-v3_2500 | 60 | 78.3 (68.3-88.3) | +6.7 (-1.7, +16.7), n=60 | 2,501 | 3,400 | 0.95 | 0.95 | 0.09 | 1.04 | 1.33 | as run, no cache |
| llmslim-v3_10000 | 60 | 76.7 (65.0-86.7) | +5.0 (-3.3, +13.3), n=60 | 10,007 | 514 | 2.11 | 2.11 | 0.01 | 2.12 | 2.77 |  |
| mem0_top200 | 60 | 76.7 (66.7-86.7) | +5.0 (-6.7, +16.7), n=60 | 11,347 | 949 | 2.40 | 2.40 | 218.48 | 220.88 | 288.11 |  |
| mem0_top50 | 60 | 75.0 (63.3-85.0) | +3.3 (-5.0, +11.7), n=60 | 2,848 | 949 | 1.02 | 1.02 | 218.48 | 219.50 | 292.67 |  |
| llmslim-v3_2500 | 60 | 71.7 (60.0-83.3) |  | 2,501 | 563 | 0.95 | 0.95 | 0.01 | 0.96 | 1.34 | as run, no cache |
| mem0_top20 | 60 | 71.7 (60.0-83.3) | +0.0 (-11.7, +11.7), n=60 | 1,133 | 949 | 0.74 | 0.74 | 218.48 | 219.22 | 305.89 |  |

## LongMemEval-S, Zep's 24-question sample (score)
| Arm | n | score (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 24 | 91.7 (79.2-100.0) | +4.2 (-8.3, +16.7), n=24 | 111,243 | 1 | 90.22 | 90.22 | 0.00 | 90.22 | 98.42 | as run, no cache |
| llmslim-v3_2500 | 24 | 87.5 (75.0-100.0) |  | 2,501 | 562 | 0.92 | 0.92 | 0.01 | 0.94 | 1.07 | as run, no cache |
| llmslim_rr-v3_2500 | 24 | 87.5 (70.8-100.0) | +0.0 (-12.5, +12.5), n=24 | 2,498 | 3,373 | 0.92 | 0.92 | 0.09 | 1.01 | 1.15 |  |
| mem0_top50 | 24 | 87.5 (75.0-100.0) | +0.0 (-12.5, +12.5), n=24 | 2,844 | 976 | 1.00 | 1.00 | 218.48 | 219.48 | 250.83 |  |
| mem0_top200 | 24 | 83.3 (66.7-95.8) | -4.2 (-20.8, +12.5), n=24 | 11,348 | 976 | 2.36 | 2.36 | 218.48 | 220.84 | 265.01 |  |
| llmslim-v3_10000 | 24 | 79.2 (62.5-95.8) | -8.3 (-20.8, +0.0), n=24 | 10,005 | 516 | 2.09 | 2.09 | 0.01 | 2.11 | 2.66 |  |
| zep | 24 | 58.3 (37.5-79.2) | -29.2 (-45.8, -12.5), n=24 | 2,053 | 20,718 | 0.85 | 0.85 | 696.71 | 697.56 | 1195.81 |  |

## LongMemEval-S, Mem0's 60-question sample (score_mem0_judge)
| Arm | n | score_mem0_judge (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 60 | 90.0 (81.7-96.7) | +6.7 (-1.7, +16.7), n=60 | 111,417 | 1 | 90.20 | 90.20 | 0.00 | 90.20 | 100.22 | as run, no cache |
| llmslim_rr-v3_2500 | 60 | 86.7 (76.7-95.0) | +3.3 (+0.0, +8.3), n=60 | 2,501 | 3,400 | 0.95 | 0.95 | 0.09 | 1.04 | 1.21 | as run, no cache |
| mem0_top200 | 60 | 85.0 (75.0-93.3) | +1.7 (-8.3, +11.7), n=60 | 11,347 | 949 | 2.40 | 2.40 | 218.48 | 220.88 | 259.86 |  |
| mem0_top50 | 60 | 85.0 (75.0-93.3) | +1.7 (-8.3, +10.0), n=60 | 2,848 | 949 | 1.02 | 1.02 | 218.48 | 219.50 | 258.24 |  |
| llmslim-v3_10000 | 60 | 83.3 (73.3-91.7) | +0.0 (-6.7, +6.7), n=60 | 10,007 | 514 | 2.11 | 2.11 | 0.01 | 2.12 | 2.55 |  |
| llmslim-v3_2500 | 60 | 83.3 (73.3-91.7) |  | 2,501 | 563 | 0.95 | 0.95 | 0.01 | 0.96 | 1.15 | as run, no cache |
| mem0_top20 | 60 | 81.7 (71.7-91.7) | -1.7 (-10.0, +5.0), n=60 | 1,133 | 949 | 0.74 | 0.74 | 218.48 | 219.22 | 268.43 |  |

## LongMemEval-S, Zep's 24-question sample (score_mem0_judge)
| Arm | n | score_mem0_judge (95% CI) | vs llmslim-v3_2500 (paired, 95% CI) | Context tokens | Build ms (median) | Reader $/1k as run | Reader $/1k no cache | Memory + compute $/1k | Total $/1k as run | $ per 1k correct | Cost frontier |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| full | 24 | 95.8 (87.5-100.0) | +4.2 (+0.0, +12.5), n=24 | 111,243 | 1 | 90.22 | 90.22 | 0.00 | 90.22 | 94.14 | as run, no cache |
| llmslim-v3_10000 | 24 | 91.7 (79.2-100.0) | +0.0 (+0.0, +0.0), n=24 | 10,005 | 516 | 2.09 | 2.09 | 0.01 | 2.11 | 2.30 |  |
| llmslim-v3_2500 | 24 | 91.7 (79.2-100.0) |  | 2,501 | 562 | 0.92 | 0.92 | 0.01 | 0.94 | 1.02 | as run, no cache |
| llmslim_rr-v3_2500 | 24 | 91.7 (79.2-100.0) | +0.0 (+0.0, +0.0), n=24 | 2,498 | 3,373 | 0.92 | 0.92 | 0.09 | 1.01 | 1.10 |  |
| mem0_top200 | 24 | 87.5 (70.8-100.0) | -4.2 (-12.5, +0.0), n=24 | 11,348 | 976 | 2.36 | 2.36 | 218.48 | 220.84 | 252.39 |  |
| mem0_top50 | 24 | 87.5 (70.8-100.0) | -4.2 (-16.7, +8.3), n=24 | 2,844 | 976 | 1.00 | 1.00 | 218.48 | 219.48 | 250.83 |  |
| zep | 24 | 70.8 (54.2-87.5) | -20.8 (-41.7, +0.0), n=24 | 2,053 | 20,718 | 0.85 | 0.85 | 696.71 | 697.56 | 984.79 |  |

