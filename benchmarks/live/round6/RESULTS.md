# Round 6 results: agent memory on BEAM-1M

Measured 24-27 October 2026 on held-out data: BEAM's 1M tier, 35 conversations of about 946,000 tokens each and 700
questions across 10 types. LLMSlim was developed on BEAM's smaller tiers only, and none of this data was opened while
it was tuned. Every system was read and judged once.

This round is published as results only: this report and [summary.json](summary.json), which holds the same aggregate
numbers in machine-readable form. The protocol, the harness and the per-question answers are not published with this
round. The protocol was fixed before the first paid call. Its one change to the ship rule and the claim wording was
made while Mem0 was still building its memories, before any system had answered a question on this data (see
[the ship rule](#the-ship-rule)).

## Summary

Every system is read by Claude Haiku 5.5 with BEAM's answer prompt, three times per question, and scored by BEAM's
rubric judge (also Haiku 5.5). The score is the mean rubric score out of 100. Mem0 (OSS 2.2.1, extraction on) and Zep
(Graphiti 0.30.2) stored every exchange through their own pipelines, with Haiku 5.5 as their LLM and
Qwen3-Embedding-0.6B as their embedder. LLMSlim ran with its reranker (`relevance="semantic"`). Cost is per 1,000
questions at list prices, with BEAM's 20 questions per conversation. It counts the answer call, Mem0's and Zep's
memory-building calls, and each system's compute.

| System | Context tokens (mean) | Score out of 100 (95% CI) | Cost per 1,000 questions |
| :--- | :---: | :---: | :---: |
| **LLMSlim 0.12 + reranker, 2,500 budget** | 2,436 | **44.6** (41.9 to 47.3) | **$1.22** |
| Mem0, top 50 memories | 3,020 | 43.4 (40.9 to 45.8) | $73.12 |
| **LLMSlim 0.12 + reranker, 10,000 budget** | 9,766 | **47.3** (44.3 to 50.3) | **$2.61** |
| Mem0, top 200 memories | 12,095 | 46.7 (44.1 to 49.3) | $74.53 |
| LLMSlim 0.11.1 + reranker, 2,500 / 10,000 | 2,493 / 9,985 | 38.0 (35.3 to 40.8) / 41.6 (38.6 to 44.6) | $0.91 / $2.21 |
| Zep, on 30 of the 35 conversations* | 3,397 | 38.4 (35.6 to 41.2) | $330.07 |

\* Zep ran on a seeded draw of 30 conversations to cap its cost. On those 30, LLMSlim 0.12 scored 45.9 and 48.3.

"LLMSlim 0.12" is commit 16a2708, the version that became 0.12.0 after hardening; see
[Limitations](#limitations) for how the two compare.

**What it shows:**
- **On par with Mem0, at a fraction of the cost.** LLMSlim is +1.2 points at 2,500 tokens (95% CI -0.7 to +3.2) and
  +0.6 at 10,000 (-1.6 to +2.7). Neither difference is significant, so we do not claim to beat Mem0. It is 60x
  cheaper per 1,000 questions at 2,500 tokens and 28.6x cheaper at 10,000, at list prices, because Mem0 makes an LLM
  call for every exchange it stores and LLMSlim makes none.
- **Ahead of Zep** by 7.5 to 9.9 points, on Zep's 30 conversations: +7.5 at 2,500 tokens (+4.5 to +10.4) and +9.9 at
  10,000 (+6.8 to +12.9).
- **Ahead of 0.11.1.** On the same questions LLMSlim 0.12 scored 44.6 and 47.3 where 0.11.1 scored 38.0 and 41.6,
  with no question type more than 1.3 points lower.

## Where LLMSlim loses

Against Mem0, per question type (70 questions each):
- **Summarization:** -8.9 points at 2,500 tokens (-13.1 to -4.7) and -4.0 at 10,000 (-7.8 to -0.2).
- **Multi-session reasoning at 10,000 tokens:** -6.0 (-10.1 to -1.8).
- **Information extraction:** -4.6 at 2,500 tokens (-12.3 to +3.2) and -4.9 at 10,000 (-12.3 to +2.6). Neither is
  significant.

And beyond accuracy:
- **Search latency with the reranker.** With the reranker on the benchmark laptop's CPU, a search over a
  946,000-token history took 3.6 s at the median at 2,500 tokens and 4.9 s at 10,000 (p95 6.1 s and 6.7 s). The
  default lexical search, which `llmslim mcp` uses, takes about 45 ms at the median on a 100,000-token history
  ([docs/MEMORY.md](../../../docs/MEMORY.md)), but it was not scored in this round.
- **The ship rule was relaxed.** It was loosened before any LLMSlim result on this data was read. The original,
  stricter per-type bar, which also required the lower bounds for instruction following and summarization to stay
  within 5 points of Mem0, would have failed on summarization (both budgets) and instruction following (10,000
  tokens). Both verdicts are [below](#the-ship-rule).

## Setup

**Data.** BEAM's 1M tier (`Mohammadta/BEAM`, `data/1M-00000-of-00001.parquet`): 35 conversations, 20 probing
questions each (2 of each of 10 types), 700 questions in all, 70 per type. Where BEAM's own answer generation reads
a truncated history (16 of the 35 conversations), the same prefix is used here. The evaluated histories hold 34,585
user/assistant exchanges, about 946,000 tokens per conversation on average (cl100k). No history fits in Haiku 5.5's
1M-token window, so there is no whole-history baseline in this round.

**Systems.**

| Arm | What the reader gets |
| :--- | :--- |
| LLMSlim 0.12 + reranker | `Memory.search(question, budget=2500 or 10000, relevance="semantic")` at commit 16a2708, with that commit's defaults. The reranker is `cross-encoder/ms-marco-MiniLM-L-6-v2` (22M parameters) on the CPU. No LLM call when storing or searching. |
| LLMSlim 0.11.1 + reranker | The same call on `llmslim[semantic,fast-tokens]==0.11.1` from PyPI, the previous release. |
| Mem0, top 50 / top 200 | Mem0 OSS 2.2.1 with extraction (`infer=True`, Mem0's default): every exchange added in order with Haiku 5.5 as its LLM, Qwen3-Embedding-0.6B as its embedder and embedded Qdrant with BM25. One search per question (`top_k=200`, Mem0's default threshold, no reranker); the reader gets the top 50 or top 200 memories with their dates, in the format of Mem0's own BEAM harness. |
| Zep | Graphiti 0.30.2 on Neo4j, one exchange per episode, Haiku 5.5 as its LLM, Qwen3-Embedding-0.6B and `BAAI/bge-reranker-v2-m3`. Search returns 20 facts and 20 entities in Zep's LongMemEval context template. |

Mem0's and Zep's LLM calls went through one metering proxy that recorded every call.

**Reader.** BEAM's answer prompt (`answer_generation_for_rag`), Claude Haiku 5.5 (`claude-haiku-5-5`), effort low,
`max_tokens` 4,096. **Three reads per question** for every arm, each judged on its own; a question's score is the
mean of its three judged reads.

**Judge.** BEAM's rubric judge on Haiku 5.5, one call per rubric item (scored 0, 0.5 or 1); the judge never sees the
question, and a read's score is the mean over its rubric items, out of 100. Event-ordering questions are also scored
with BEAM's ordering metric, reported apart. Before any test answer was judged, the judge scored 40 deliberately
wrong answers (20 with a swapped detail, 20 answering a different question): 4.8 points on average, under the bar of
15.

**Budgets.** LLMSlim at 2,500 and 10,000 tokens. Mem0's top 50 and top 200 memories are its pairs for those budgets
(3,020 and 12,095 tokens on average, more than LLMSlim's). Zep's 20 facts and 20 entities came to 3,397 tokens.
Context tokens are counted with tiktoken's cl100k_base.

**Statistics.** The unit is the conversation: a conversation's score is the mean of its questions, and a comparison
is the paired difference of per-conversation scores, with a t interval (34 degrees of freedom on 35 conversations, 29
on Zep's 30) and a paired percentile cluster bootstrap (2,000 resamples). The four comparisons with Mem0 and Zep also
carry an exact sign-flip p and a Holm-adjusted one-sided p. Per-type intervals are descriptive and wide, and they
are not adjusted for multiple comparisons.

**Cost.** USD per 1,000 questions at Claude Haiku 5.5 list prices (batch calls counted at list price, not the
half price they were billed at):
- **Reader:** one read per question (the mean of its three reads), since a product reads once.
- **Memory building:** Mem0's and Zep's LLM calls for each conversation's final successful build (retries and
  rebuilds after interruptions are not counted), spread over that conversation's 20 questions. LLMSlim makes none.
- **Compute:** device-busy time, priced at $0.526 an hour for GPU work (a T4) and $0.0892 an hour for CPU work
  (2 vCPUs): embedding and search for Mem0 and Zep, storing and reranking for LLMSlim.
- Judge calls are not counted for any system.

## Comparisons with Mem0 and Zep

LLMSlim 0.12 minus the competitor, in points. Conversations: 35 for Mem0, Zep's 30 for Zep.

| | Difference | Conversations | Mean (95% t CI) | Paired bootstrap 95% | Sign-flip p (exact) | Holm-adjusted one-sided p | Reading |
|---|---|---|---|---|---|---|---|
| M2500 | 2,500 tokens - Mem0 top 50 | 35 | +1.23 (-0.70, +3.15) | (-0.59, +3.04) | 0.2032 | 0.2048 | on par |
| M10000 | 10,000 tokens - Mem0 top 200 | 35 | +0.55 (-1.56, +2.66) | (-1.49, +2.50) | 0.597 | 0.299 | on par |
| Z2500 | 2,500 tokens - Zep | 30 | +7.47 (+4.49, +10.45) | (+4.77, +10.08) | 2.265e-05 | 2.657e-05 | ahead |
| Z10000 | 10,000 tokens - Zep | 30 | +9.86 (+6.80, +12.91) | (+7.13, +12.58) | 3.036e-07 | 6.224e-07 | ahead |

"On par" means the point estimate is at least -1 and both lower bounds are above -5, but the lower bound is not above
0. "Ahead" needs both lower bounds above 0.

## Every arm

Columns: the mean rubric score with its 95% t interval and its cluster bootstrap; the paired difference from Mem0 at
the same budget; the read-to-read standard deviation within a question (reader and judge noise together, in points);
the pass rate (share of questions scoring at least 50); BEAM's composite (the mean of the 10 per-type means, event
ordering scored by its ordering metric); mean context tokens; and the reader's stop reasons over every read.

### All 35 conversations

| Arm | Questions | Judged reads | Score (95% t CI) | Cluster bootstrap 95% | vs Mem0, same budget | Read-to-read SD | Pass rate | BEAM composite | Context tokens | Stop reasons | Judge parse failures |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 700 | 2,100 | 44.6 (41.9 to 47.3) | 42.0 to 47.2 | +1.2 (-0.7 to +3.2) | 9.4 | 44.4 (41.0 to 47.9) | 44.3 (41.6 to 46.9) | 2,436 | end_turn 2,100 | 0 |
| Mem0, top 50 memories | 700 | 2,100 | 43.4 (40.9 to 45.8) | 41.1 to 45.7 | | 8.3 | 42.1 (38.9 to 45.4) | 42.9 (40.5 to 45.3) | 3,020 | end_turn 2,100 | 0 |
| LLMSlim 0.11.1 + reranker, 2,500 | 700 | 2,100 | 38.0 (35.3 to 40.8) | 35.5 to 40.5 | -5.3 (-7.8 to -2.8) | 8.3 | 36.4 (33.2 to 39.7) | 38.1 (35.4 to 40.7) | 2,493 | end_turn 2,100 | 0 |
| LLMSlim 0.12 + reranker, 10,000 | 700 | 2,100 | 47.3 (44.3 to 50.3) | 44.5 to 50.1 | +0.6 (-1.6 to +2.7) | 9.5 | 47.9 (44.2 to 51.5) | 46.5 (43.6 to 49.4) | 9,766 | end_turn 2,100 | 0 |
| Mem0, top 200 memories | 700 | 2,100 | 46.7 (44.1 to 49.3) | 44.2 to 49.2 | | 9.9 | 46.7 (42.7 to 50.7) | 46.2 (43.6 to 48.8) | 12,095 | end_turn 2,094, max_tokens 6 | 0 |
| LLMSlim 0.11.1 + reranker, 10,000 | 700 | 2,100 | 41.6 (38.6 to 44.6) | 38.9 to 44.5 | -5.1 (-7.1 to -3.2) | 9.4 | 40.1 (36.0 to 44.3) | 41.6 (38.7 to 44.4) | 9,985 | end_turn 2,100 | 0 |

### Zep's 30 conversations

Conversations 1, 2, 3, 4, 7, 10 to 18, and 20 to 35: the first 30 of an order drawn with a fixed seed before any
result, so every arm is compared with Zep on the same questions.

| Arm | Questions | Judged reads | Score (95% t CI) | Cluster bootstrap 95% | vs Mem0, same budget | Read-to-read SD | Pass rate | BEAM composite | Context tokens | Stop reasons | Judge parse failures |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 600 | 1,800 | 45.9 (43.3 to 48.5) | 43.6 to 48.4 | +1.2 (-1.0 to +3.3) | 9.5 | 45.7 (42.4 to 48.9) | 45.5 (43.0 to 48.0) | 2,434 | end_turn 1,800 | 0 |
| Mem0, top 50 memories | 600 | 1,800 | 44.7 (42.3 to 47.1) | 42.5 to 47.0 | | 8.1 | 43.5 (40.2 to 46.8) | 44.3 (41.9 to 46.6) | 2,984 | end_turn 1,800 | 0 |
| LLMSlim 0.11.1 + reranker, 2,500 | 600 | 1,800 | 39.3 (36.7 to 41.8) | 37.0 to 41.7 | -5.5 (-8.2 to -2.7) | 8.0 | 37.7 (34.4 to 40.9) | 39.2 (36.7 to 41.7) | 2,492 | end_turn 1,800 | 0 |
| LLMSlim 0.12 + reranker, 10,000 | 600 | 1,800 | 48.3 (45.1 to 51.4) | 45.4 to 51.3 | -0.1 (-2.3 to +2.2) | 9.6 | 48.7 (44.9 to 52.4) | 47.4 (44.3 to 50.4) | 9,755 | end_turn 1,800 | 0 |
| Mem0, top 200 memories | 600 | 1,800 | 48.4 (46.1 to 50.6) | 46.3 to 50.6 | | 9.5 | 48.8 (45.0 to 52.7) | 47.7 (45.4 to 50.0) | 11,912 | end_turn 1,794, max_tokens 6 | 0 |
| LLMSlim 0.11.1 + reranker, 10,000 | 600 | 1,800 | 43.0 (40.0 to 46.0) | 40.2 to 45.9 | -5.4 (-7.6 to -3.2) | 9.7 | 41.5 (37.1 to 45.9) | 42.9 (40.0 to 45.8) | 9,984 | end_turn 1,800 | 0 |
| Zep | 600 | 1,800 | 38.4 (35.6 to 41.2) | 35.8 to 41.1 | | 7.7 | 35.8 (32.4 to 39.3) | 38.4 (35.6 to 41.1) | 3,397 | end_turn 1,800 | 0 |

On Zep's 30 conversations LLMSlim at 10,000 tokens is level with Mem0's top 200 (-0.1); the on-par reading above is
on all 35.

## Per question type

### Scores, all 35 conversations

Mean ± 95% t half-width, 70 questions per type.

| Arm | Abstention | Contradiction resolution | Event ordering | Information extraction | Instruction following | Knowledge update | Multi-session reasoning | Preference following | Summarization | Temporal reasoning |
|---|---|---|---|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 79.8 ± 7.4 | 29.9 ± 6.0 | 23.4 ± 4.8 | 53.8 ± 9.2 | 62.1 ± 9.0 | 51.9 ± 11.5 | 31.1 ± 7.2 | 66.7 ± 7.3 | 26.5 ± 4.3 | 20.6 ± 5.7 |
| Mem0, top 50 memories | 69.6 ± 8.9 | 23.6 ± 4.0 | 23.7 ± 5.0 | 58.4 ± 9.5 | 57.2 ± 9.8 | 45.5 ± 12.0 | 33.6 ± 7.5 | 68.6 ± 8.0 | 35.4 ± 5.5 | 18.0 ± 6.1 |
| LLMSlim 0.11.1 + reranker, 2,500 | 74.0 ± 7.9 | 20.2 ± 5.2 | 18.2 ± 3.5 | 47.0 ± 8.9 | 38.9 ± 7.2 | 46.9 ± 11.4 | 29.9 ± 6.7 | 58.4 ± 8.8 | 24.7 ± 4.6 | 21.9 ± 6.2 |
| LLMSlim 0.12 + reranker, 10,000 | 74.9 ± 9.3 | 28.3 ± 5.1 | 29.0 ± 5.4 | 58.8 ± 8.6 | 65.2 ± 7.9 | 50.5 ± 12.7 | 33.9 ± 8.2 | 71.2 ± 5.9 | 37.6 ± 6.0 | 23.3 ± 5.6 |
| Mem0, top 200 memories | 69.5 ± 8.8 | 22.5 ± 4.8 | 25.1 ± 4.7 | 63.6 ± 8.9 | 62.7 ± 8.4 | 50.8 ± 11.4 | 39.9 ± 8.6 | 68.9 ± 7.7 | 41.6 ± 5.4 | 22.6 ± 6.4 |
| LLMSlim 0.11.1 + reranker, 10,000 | 74.9 ± 9.0 | 22.2 ± 4.7 | 20.0 ± 4.4 | 52.1 ± 10.1 | 46.8 ± 8.6 | 51.2 ± 11.5 | 32.9 ± 8.1 | 63.4 ± 7.8 | 33.7 ± 5.1 | 18.8 ± 5.9 |

### Scores, Zep's 30 conversations

60 questions per type.

| Arm | Abstention | Contradiction resolution | Event ordering | Information extraction | Instruction following | Knowledge update | Multi-session reasoning | Preference following | Summarization | Temporal reasoning |
|---|---|---|---|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 81.0 ± 8.1 | 30.8 ± 6.8 | 23.3 ± 5.5 | 54.2 ± 10.5 | 65.0 ± 8.9 | 54.7 ± 12.3 | 34.2 ± 7.6 | 67.7 ± 7.3 | 25.6 ± 4.7 | 22.5 ± 6.0 |
| Mem0, top 50 memories | 69.9 ± 10.1 | 23.6 ± 4.2 | 23.5 ± 5.6 | 61.1 ± 9.6 | 58.8 ± 10.8 | 49.4 ± 13.1 | 36.0 ± 8.4 | 71.3 ± 7.7 | 34.7 ± 6.1 | 19.0 ± 6.7 |
| LLMSlim 0.11.1 + reranker, 2,500 | 76.7 ± 8.6 | 20.0 ± 5.3 | 19.1 ± 4.0 | 48.1 ± 9.8 | 39.7 ± 8.0 | 49.7 ± 12.7 | 31.6 ± 7.4 | 59.0 ± 9.3 | 24.6 ± 5.1 | 24.2 ± 6.5 |
| LLMSlim 0.12 + reranker, 10,000 | 76.5 ± 10.4 | 28.1 ± 5.8 | 29.5 ± 6.2 | 58.4 ± 9.8 | 68.8 ± 7.8 | 51.9 ± 14.0 | 36.4 ± 9.1 | 71.6 ± 6.2 | 35.9 ± 6.4 | 25.6 ± 5.6 |
| Mem0, top 200 memories | 70.1 ± 9.9 | 23.7 ± 5.1 | 25.2 ± 5.4 | 66.2 ± 9.2 | 66.2 ± 8.8 | 53.1 ± 12.8 | 42.8 ± 9.5 | 71.2 ± 7.5 | 41.2 ± 6.2 | 24.0 ± 6.8 |
| LLMSlim 0.11.1 + reranker, 10,000 | 76.5 ± 10.0 | 22.8 ± 5.2 | 20.0 ± 5.0 | 55.2 ± 10.6 | 48.6 ± 8.6 | 53.1 ± 12.7 | 35.3 ± 8.9 | 64.7 ± 8.0 | 32.0 ± 5.1 | 21.8 ± 6.2 |
| Zep | 75.3 ± 10.8 | 19.2 ± 4.4 | 18.6 ± 5.0 | 46.0 ± 9.7 | 48.0 ± 9.1 | 32.5 ± 10.4 | 31.8 ± 9.4 | 62.4 ± 8.0 | 25.5 ± 3.9 | 24.9 ± 7.9 |

### Paired differences against Mem0 and Zep

LLMSlim 0.12 minus the competitor, per type, with 95% t intervals (descriptive, unadjusted).

| Type | vs Mem0 top 50, 2,500 tokens | vs Mem0 top 200, 10,000 tokens | vs Zep, 2,500 tokens (30 conversations) | vs Zep, 10,000 tokens (30 conversations) |
|---|---|---|---|---|
| Abstention | +10.1 (+3.3 to +17.0) | +5.4 (-0.1 to +10.8) | +5.7 (-6.2 to +17.6) | +1.3 (-10.0 to +12.5) |
| Contradiction resolution | +6.3 (+0.0 to +12.6) | +5.8 (+0.3 to +11.3) | +11.7 (+4.3 to +19.1) | +8.9 (+1.7 to +16.1) |
| Event ordering | -0.3 (-3.3 to +2.7) | +4.0 (+1.1 to +6.8) | +4.7 (+1.1 to +8.2) | +10.8 (+7.1 to +14.6) |
| Information extraction | -4.6 (-12.3 to +3.2) | -4.9 (-12.3 to +2.6) | +8.1 (-1.0 to +17.3) | +12.4 (+3.4 to +21.3) |
| Instruction following | +5.0 (-2.6 to +12.5) | +2.5 (-5.2 to +10.1) | +17.0 (+7.4 to +26.7) | +20.8 (+11.6 to +29.9) |
| Knowledge update | +6.4 (-4.8 to +17.7) | -0.4 (-10.4 to +9.7) | +22.2 (+6.3 to +38.1) | +19.4 (+1.8 to +37.1) |
| Multi-session reasoning | -2.5 (-7.6 to +2.5) | -6.0 (-10.1 to -1.8) | +2.3 (-7.7 to +12.4) | +4.6 (-5.6 to +14.8) |
| Preference following | -1.9 (-9.5 to +5.7) | +2.4 (-2.5 to +7.2) | +5.2 (-2.4 to +12.9) | +9.2 (+2.0 to +16.5) |
| Summarization | -8.9 (-13.1 to -4.7) | -4.0 (-7.8 to -0.2) | +0.1 (-4.2 to +4.4) | +10.4 (+5.0 to +15.9) |
| Temporal reasoning | +2.6 (-0.7 to +5.9) | +0.7 (-3.3 to +4.7) | -2.4 (-8.5 to +3.6) | +0.7 (-5.4 to +6.8) |

No type is more than 10 points behind either competitor at either budget. Every type more than 3 points behind is
listed under [Where LLMSlim loses](#where-llmslim-loses).

### Against 0.11.1

LLMSlim 0.12 minus 0.11.1 at the same budget, all 35 conversations (estimate, 95% t interval, exact sign-flip p).
The ship rule needs every estimate above -3.

| Type | 2,500 tokens | p | 10,000 tokens | p |
|---|---|---|---|---|
| Abstention | +5.71 (-1.27, +12.70) | 0.1137 | -0.00 (-7.59, +7.59) | 1 |
| Contradiction resolution | +9.76 (+3.06, +16.46) | 0.005732 | +6.07 (+0.81, +11.33) | 0.02628 |
| Event ordering | +5.16 (+1.51, +8.81) | 0.005418 | +9.00 (+4.64, +13.37) | 0.0001714 |
| Information extraction | +6.83 (-0.14, +13.79) | 0.0535 | +6.72 (-0.58, +14.02) | 0.0693 |
| Instruction following | +23.19 (+13.69, +32.70) | 2.013e-05 | +18.41 (+10.26, +26.56) | 6.21e-05 |
| Knowledge update | +5.00 (-3.01, +13.01) | 0.2364 | -0.71 (-9.03, +7.60) | 0.9094 |
| Multi-session reasoning | +1.19 (-4.19, +6.57) | 0.6612 | +1.02 (-4.27, +6.30) | 0.7196 |
| Preference following | +8.29 (+0.79, +15.80) | 0.02926 | +7.86 (+1.72, +13.99) | 0.01346 |
| Summarization | +1.76 (-1.25, +4.77) | 0.2418 | +3.98 (+0.66, +7.31) | 0.02069 |
| Temporal reasoning | -1.31 (-6.41, +3.79) | 0.6439 | +4.52 (+0.89, +8.15) | 0.01495 |

## Event ordering: BEAM's ordering metric

Event-ordering questions scored two ways: the rubric judge, and BEAM's ordering metric (tau_norm, F1 and their
product, final_score, all out of 100). Mean with 95% t interval.

| Arm | Rubric judge | tau_norm | F1 | final_score |
|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 23.4 (18.6 to 28.2) | 20.0 (18.5 to 21.5) | 8.5 (6.1 to 10.9) | 2.3 (1.5 to 3.2) |
| Mem0, top 50 memories | 23.7 (18.7 to 28.7) | 19.3 (18.0 to 20.6) | 7.0 (4.9 to 9.2) | 1.9 (1.2 to 2.6) |
| LLMSlim 0.11.1 + reranker, 2,500 | 18.2 (14.7 to 21.7) | 18.6 (17.5 to 19.6) | 5.3 (3.3 to 7.3) | 1.4 (0.8 to 2.0) |
| LLMSlim 0.12 + reranker, 10,000 | 29.0 (23.6 to 34.4) | 21.1 (19.4 to 22.8) | 10.2 (7.7 to 12.8) | 2.9 (2.0 to 3.8) |
| Mem0, top 200 memories | 25.1 (20.4 to 29.7) | 19.5 (17.9 to 21.1) | 7.4 (5.1 to 9.6) | 2.0 (1.2 to 2.9) |
| LLMSlim 0.11.1 + reranker, 10,000 | 20.0 (15.6 to 24.5) | 19.7 (18.2 to 21.2) | 7.8 (5.2 to 10.4) | 2.3 (1.3 to 3.2) |
| Zep (its 30 conversations) | 18.6 (13.6 to 23.6) | 18.0 (16.9 to 19.1) | 5.4 (3.6 to 7.3) | 1.3 (0.8 to 1.8) |

Every system orders events poorly on million-token histories.

## The ship rule

The protocol was fixed before the first paid call with a stricter, per-type bar. On 25 October, while Mem0 was still
building its memories and before any reader call of any system (so before any score on this data existed), the ship
rule was loosened and the claim wording was made to follow the evidence. Both verdicts are reported.

**Ship rule (primary): SHIP at both budgets.** At each budget, all three must hold:
- **R1:** LLMSlim minus Mem0, all questions: point estimate at least -1 point.
- **R2:** its one-sided 97.5% lower bound above -5 points, by both the t interval and the paired bootstrap.
- **R3:** against 0.11.1 at the same budget, every question type's point estimate above -3 points
  ([table above](#against-0111)).

| Budget | Rule | Estimate | 95% t interval | Decisive value | Result | Paired bootstrap 95% |
|---|---|---|---|---|---|---|
| 2,500 | R1 | +1.23 | (-0.70, +3.15) | estimate +1.23 | PASS | (-0.59, +3.04) |
| 2,500 | R2 | +1.23 | (-0.70, +3.15) | lower bound -0.70 | PASS | (-0.59, +3.04) |
| 2,500 | R3 | lowest type: temporal reasoning -1.31 | (-6.41, +3.79) | estimate -1.31 | PASS | (-5.83, +3.69) |
| 10,000 | R1 | +0.55 | (-1.56, +2.66) | estimate +0.55 | PASS | (-1.49, +2.50) |
| 10,000 | R2 | +0.55 | (-1.56, +2.66) | lower bound -1.56 | PASS | (-1.49, +2.50) |
| 10,000 | R3 | lowest type: knowledge update -0.71 | (-9.03, +7.60) | estimate -0.71 | PASS | (-8.57, +7.14) |

**The original, stricter bar: would not ship.** It also required the per-type lower bound against Mem0 to stay above
-5 for instruction following and summarization, at both budgets (decisive value: the lower of the t and bootstrap
lower limits). Under the ship rule these rows are reported as weak spots, not gates.

| Budget | Type | Estimate | 95% t interval | Paired bootstrap 95% | Lower bound | Above -5? |
|---|---|---|---|---|---|---|
| 2,500 | Instruction following | +4.96 | (-2.59, +12.51) | (-2.06, +11.98) | -2.59 | yes |
| 2,500 | Summarization | -8.90 | (-13.10, -4.69) | (-12.86, -5.03) | -13.10 | no |
| 10,000 | Instruction following | +2.46 | (-5.16, +10.08) | (-4.56, +9.52) | -5.16 | no |
| 10,000 | Summarization | -3.96 | (-7.75, -0.16) | (-7.47, -0.20) | -7.75 | no |

Its other conditions (the overall lower bound above -5, and every type above -3 against 0.11.1) pass at both
budgets.

**Claim wording**, as the rule allows it: on par with Mem0 at 2,500 tokens (+1.2 points, 95% t -0.7 to +3.2,
bootstrap -0.6 to +3.0) and at 10,000 tokens (+0.6, t -1.6 to +2.7, bootstrap -1.5 to +2.5); ahead of Zep on 30
conversations at 2,500 tokens (+7.5, t +4.5 to +10.4, bootstrap +4.8 to +10.1) and at 10,000 tokens (+9.9, t +6.8
to +12.9, bootstrap +7.1 to +12.6). "Beats Mem0" would need both lower bounds above 0; neither budget has that.

## Cost

USD per 1,000 questions at list prices ([method](#setup)). "Per conversation" is what one conversation costs to store
and then ask 5, 20 or 100 questions.

### All 35 conversations

| Arm | Score | Reader | Memory building (LLM calls) | Compute | Total per 1,000 questions | Per conversation at 5 / 20 / 100 questions |
|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 44.6 | $0.632 | $0.000 | $0.587 | **$1.219** | $0.006 / $0.024 / $0.122 |
| Mem0, top 50 memories | 43.4 | $0.709 | $56.280 | $16.135 | **$73.124** | $1.451 / $1.462 / $1.521 |
| LLMSlim 0.11.1 + reranker, 2,500 | 38.0 | $0.608 | $0.000 | $0.304 | **$0.911** | $0.005 / $0.018 / $0.091 |
| LLMSlim 0.12 + reranker, 10,000 | 47.3 | $1.804 | $0.000 | $0.805 | **$2.609** | $0.013 / $0.052 / $0.261 |
| Mem0, top 200 memories | 46.7 | $2.111 | $56.280 | $16.135 | **$74.526** | $1.458 / $1.491 / $1.662 |
| LLMSlim 0.11.1 + reranker, 10,000 | 41.6 | $1.877 | $0.000 | $0.337 | **$2.214** | $0.011 / $0.044 / $0.221 |

Mem0 at 2,500 tokens costs 60.0x LLMSlim's total, and 28.6x at 10,000. Most of Mem0's cost is the extraction calls
that build its memory ($56.28 per 1,000 questions), which it pays once per stored exchange whatever is asked later.

**Cost frontier.** An arm is dominated only by a cheaper arm whose paired difference from it has a one-sided 97.5%
lower bound above -5 points. LLMSlim 0.12 at 2,500 tokens and 0.11.1 at 2,500 tokens are on the frontier (0.12 is
undominated in 95% of bootstrap resamples, 0.11.1 in 100%); both Mem0 arms are dominated by LLMSlim 0.12.

### Zep's 30 conversations

| Arm | Score | Reader | Memory building (LLM calls) | Compute | Total per 1,000 questions | Per conversation at 5 / 20 / 100 questions |
|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 2,500 | 45.9 | $0.632 | $0.000 | $0.570 | **$1.202** | $0.006 / $0.024 / $0.120 |
| Mem0, top 50 memories | 44.7 | $0.708 | $57.192 | $13.286 | **$71.186** | $1.413 / $1.424 / $1.483 |
| LLMSlim 0.11.1 + reranker, 2,500 | 39.3 | $0.610 | $0.000 | $0.305 | **$0.915** | $0.005 / $0.018 / $0.091 |
| LLMSlim 0.12 + reranker, 10,000 | 48.3 | $1.811 | $0.000 | $0.788 | **$2.598** | $0.013 / $0.052 / $0.260 |
| Mem0, top 200 memories | 48.4 | $2.101 | $57.192 | $13.286 | **$72.579** | $1.420 / $1.452 / $1.622 |
| LLMSlim 0.11.1 + reranker, 10,000 | 43.0 | $1.891 | $0.000 | $0.336 | **$2.228** | $0.011 / $0.045 / $0.223 |
| Zep | 38.4 | $0.746 | $320.214 | $9.107 | **$330.067** | $6.589 / $6.601 / $6.667 |

## Latency

LLMSlim's search time per question with the reranker, measured while building the contexts on the benchmark laptop
(a shared machine that was running other work), with the reranker on its CPU. CPU time counts every core.

| Version | Budget | Median | p95 | Mean | Max | CPU time per search (mean) |
|---|---|---|---|---|---|---|
| LLMSlim 0.12 | 2,500 | 3.56 s | 6.07 s | 3.75 s | 9.17 s | 23.6 s |
| LLMSlim 0.12 | 10,000 | 4.88 s | 6.68 s | 4.82 s | 7.51 s | 32.4 s |
| LLMSlim 0.11.1 | 2,500 | 3.70 s | 4.59 s | 3.69 s | 5.90 s | 12.2 s |
| LLMSlim 0.11.1 | 10,000 | 3.89 s | 4.84 s | 3.92 s | 9.78 s | 13.5 s |

Storing a whole conversation took a median of 1.66 s (0.12) and 1.30 s (0.11.1), at most 2.02 s and 2.16 s. Each
search reranks candidates from the whole 946,000-token history; the default lexical mode, with no model, is far
faster (about 45 ms on a 100,000-token history, measured separately) but was not scored here.

## Spend

What the run billed in Claude API calls (batch calls at half price): $251.32 in all, of which Mem0's memory building
was $42.21 and Zep's $192.13 (both including calls repeated when a store was resumed or rebuilt after an
interruption), and the judge check $0.03. Readers and judges, every read:

| Arm | Questions | Reader calls | Judged answers | Readers $ | Judge $ | Total $ |
|---|---|---|---|---|---|---|
| LLMSlim 0.12 + reranker, 10,000 | 700 | 2,100 | 2,100 | 1.894 | 1.186 | 3.080 |
| LLMSlim 0.12 + reranker, 2,500 | 700 | 2,100 | 2,100 | 0.664 | 1.156 | 1.819 |
| LLMSlim 0.11.1 + reranker, 10,000 | 700 | 2,100 | 2,100 | 1.971 | 1.151 | 3.122 |
| LLMSlim 0.11.1 + reranker, 2,500 | 700 | 2,100 | 2,100 | 0.638 | 1.114 | 1.752 |
| Mem0, top 200 memories | 700 | 2,100 | 2,100 | 2.217 | 1.256 | 3.473 |
| Mem0, top 50 memories | 700 | 2,100 | 2,100 | 0.745 | 1.248 | 1.993 |
| Zep | 600 | 1,800 | 1,800 | 0.671 | 1.048 | 1.719 |

## Limitations

- **One reader.** Every answer is Claude Haiku 5.5's, and the judge is Haiku 5.5 too. A stronger reader could change
  both the scores and the gaps. The judge passed its leniency check (4.8 points on 40 wrong answers), but it is one
  model.
- **The ship rule was relaxed.** It was loosened before any LLMSlim result on this data was read, but it is looser
  than the bar the protocol was first fixed with, which would have failed on summarization (both budgets) and
  instruction following (10,000 tokens). Both verdicts are above.
- **Zep on a seeded 30.** Zep ran on 30 of the 35 conversations, drawn with a fixed seed before any result, to cap
  its cost. Its comparisons are on those 30 only, and say so.
- **The cost ratios assume BEAM's 20 questions per conversation.** Mem0's cost is mostly the one-time extraction cost
  of each stored exchange, so with more questions per conversation the gap gets smaller (see the per-conversation
  column: $1.462 against $0.024 at 20 questions, $1.521 against $0.122 at 100, at 2,500 tokens).
- **Cost details that favour or burden the competitors.** Mem0's extraction calls are priced as they ran, with the
  prompt cache our metering proxy put on its long system prompt; without that cache they cost more, so this favours
  Mem0. Compute is priced on the device each store was built on: Mem0's embedder ran on the laptop's GPU for some
  conversations and on its CPU for others (where they did not fit in the GPU's memory), and CPU embedding takes much
  longer, so
  part of Mem0's $16.14 of compute per 1,000 questions comes from that. Its extraction calls ($56.28) are most of its
  cost either way.
- **Latency was measured on a shared laptop with the reranker on its CPU.** The times above are from the benchmark
  machine while it was running other work; a dedicated machine or a GPU would be faster. The lexical mode was not
  scored.
- **0.12.0 is not byte for byte the benchmarked commit.** The "LLMSlim 0.12" arms ran commit 16a2708, from a
  pre-release branch that is not in the public history; 0.12.0 is that code after hardening. In the hardening's parity
  checks it returned the same bytes as 16a2708 on 14,377 of 14,377 English test rows, and rebuilding 80 development
  contexts (from BEAM's smaller tiers, not this data) gave 80 of 80 identical. Inputs with no Latin-script words were
  changed on purpose and can differ. The 1,400 round-6 contexts were not rebuilt with 0.12.0, so this is evidence of
  equivalence on English text, not a rerun.
- **One benchmark.** BEAM-1M is synthetic, long, English chat between a user and an assistant. Other histories
  (shorter, multilingual, multi-party, tool-heavy) may rank the systems differently.

## What is not published

The protocol, the harness, the contexts, the answers, the judgements and the per-question scores stay private for
this round. [summary.json](summary.json) holds every aggregate number above. No BEAM conversation text or question is
copied into this repository; BEAM is available from its authors on Hugging Face.
