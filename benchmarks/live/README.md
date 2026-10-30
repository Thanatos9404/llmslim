# Real-model benchmarks: Claude Haiku 5.5

Measured in October 2026 with `claude-haiku-5-5` at `effort: low` through the Claude API. Every configuration
uses the same model, prompt template and scoring; only the context changes:

- **full**: the complete context.
- **LLMSlim**: the context after LLMSlim Core 0.8.0 at the stated budget, with lexical relevance (the default:
  no model) or with the optional reranker (`relevance="semantic"`, `cross-encoder/ms-marco-MiniLM-L-6-v2`,
  22M parameters, trained on MS MARCO only).
- **truncate / recent**: the context cut, by the dataset's own rule, to the token count LLMSlim produced.
- **LLMLingua-2, LongLLMLingua**: the two best-known open-source prompt compressors, run by us with their
  published settings at the same token budget.

## How the numbers were kept honest

Questions are split three ways, fixed in `splits.json` (`splits.py`):

- **test_a**: the questions reported since the first round.
- **dev**: used for development only, through `devcheck.py`. It runs free offline checks with no model: did the
  answer, the supporting sentences or the labelled evidence turns survive compression?
- **test_b**: a fresh sample drawn after the code was frozen and run once.

Nothing was tuned on test_a or test_b. Each change in 0.8.0 was kept only if it held up on dev, and the parameters
were chosen there:

- compound matching;
- the optional reranker and its lexical share;
- units of about 1/32 of the budget.

Several ideas were dropped because dev did not support them:

- neighbour smoothing;
- entity bridging;
- per-group diversity, which helped retrieval but cost chat memory 6 points;
- passage titles in headers.

After LongLLMLingua was measured, two more ideas were tested with the reader on 300 NQ dev cases (100 questions ×
3 gold positions). The reranker arm alone scored 83.0 (full context 88.7), and neither idea helped, so neither ships:

| Idea | Dev accuracy | Change |
|---|---:|---:|
| Ordering documents by relevance | 80.3 | −2.7 |
| Sharing a document's best reranker score with its other chunks | 83.3 | +0.3 |

`verify_built.py` checks that the prompts sent come from the frozen source. Confidence intervals are paired
bootstrap 95% over the same questions.

Total API spend for everything here: about $30 (per-suite ledgers in `results/spend-*.json`).

## Results

### LongMemEval-S: memory over long chat histories

Histories of about 50 sessions (115k tokens). Official judge prompts, judged by Haiku 5.5. Budget 8,000 tokens.

| Configuration | test_a (90) | test_b (90, fresh) | Context tokens | $ per 1k questions |
|---|---:|---:|---:|---:|
| Full history | 82.2 | 72.2 | 114,006 | 90.72 |
| **LLMSlim 0.8 + reranker** (`compress_documents`) | **76.7** | **76.7** | 7,984 | 1.45 |
| LLMSlim 0.8, lexical | 68.9 | 67.8 | 7,985 | 1.45 |
| LLMSlim Vault 0.9.1 (then named Platform), defaults | 63.3 | | 7,600 | 1.36 |
| LLMSlim 0.7.2 | 25.6 | | 10,482 | 1.86 |
| Most recent sessions that fit | 14.4 | 14.4 | 6,693 | 1.23 |

With the reranker, the difference from full history is within noise on both samples, at 1/62 of the cost at Haiku 5.5
list prices. Every full-history prompt is over 100k tokens and bills at the long-prompt rate; the token reduction is
14×:

- **test_a:** −5.6 points (95% CI −15.6 to +4.4).
- **test_b:** +4.4 points (95% CI −6.7 to +15.6).

| Type (test_a, n=15 each) | Full | + reranker | Lexical | Recent |
|---|---:|---:|---:|---:|
| knowledge-update | 80.0 | 86.7 | 80.0 | 33.3 |
| single-session-user | 100.0 | 86.7 | 80.0 | 13.3 |
| single-session-assistant | 93.3 | 100.0 | 100.0 | 20.0 |
| multi-session | 73.3 | 80.0 | 66.7 | 13.3 |
| temporal-reasoning | 60.0 | 66.7 | 26.7 | 6.7 |
| single-session-preference | 86.7 | 40.0 | 60.0 | 0.0 |

Preference questions are the weakest type. These ask for a recommendation that should use a taste the user stated
earlier. On test_b the same type scored 73.3 with the reranker against 53.3 with full history, so 15 questions swing
widely.

On the dev split (320 questions, no model needed), the reranker keeps more of the labelled evidence turns:

| Evidence kept (dev split) | Lexical | + reranker |
|---|---:|---:|
| All labelled evidence turns | 91.3% | 95.3% |
| Every evidence session, multi-session questions | 71.4% | 84.7% |

### NaturalQuestions, 20 documents ("lost in the middle")

100 questions × 3 gold positions (1st, 10th, 20th). Metric: a gold answer appears in the response. Budget 25%.

| Configuration | test_a (300 cases) | gold 1st | 10th | 20th | test_b (300 cases, fresh) | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| Full context | 86.3 | 88.0 | 87.0 | 84.0 | 88.0 | 2,889 |
| **LLMSlim 0.8 + reranker** | **75.0** | 74.0 | 75.0 | 76.0 | **75.7** | 668 |
| LLMSlim 0.8, lexical | 65.7 | 67.0 | 65.0 | 65.0 | 67.3 | 659 |
| LLMSlim 0.7.2 | 62.3 | 63.0 | 58.0 | 66.0 | | 727 |
| Passages in retrieval order, same budget | 52.0 | 95.0 | 32.0 | 29.0 | 48.3 | 669 |

**Head to head with other compressors.** These runs use every second case of each split: 150 cases per split, which
works out to 50 questions × 3 gold positions, so 300 cases from 100 questions in all. Same reader and same budget.
test_b was run once, after the code was frozen:

| Compressor | Model it runs | test_a (150 cases) | test_b (150 cases) | All 300 cases | Tokens | Time per question |
|---|---|---:|---:|---:|---:|---|
| Full context | | 87.3 | 90.7 | 89.0 | 2,889 | |
| **LLMSlim 0.8 + reranker** | 22M cross-encoder | 74.0 | **83.3** | **78.7** | 668 | 0.1 s GPU |
| LongLLMLingua (paper's NQ settings) | LLaMA-2-7B-chat, 4-bit | **80.0** | 76.0 | 78.0 | 630 | 9.3 s GPU |
| LLMLingua-2, same token budget | XLM-RoBERTa-large | 64.7 | 73.3 | 69.0 | 680 | 2.3 s GPU (about 43 s CPU) |
| LLMSlim 0.8, lexical | none | 63.3 | 74.0 | 68.7 | 658 | 25 ms CPU |
| Passages in order | none | 49.3 | 47.3 | 48.3 | 627 | |

Tokens are means and times are medians of `build_ms` over the 300 cases (the first call of each run includes model
loading). LLMLingua-2's CPU time is the mean of the `rate=0.25` CPU run on test_a.

Paired differences (bootstrap 95% intervals):

| Comparison | test_a | test_b | All 300 cases |
|---|---:|---:|---:|
| LLMSlim + reranker vs LongLLMLingua | −6.0 (−14.7, +2.0) | +7.3 (+0.7, +14.7) | +0.7 (−4.7, +6.0) |
| LLMSlim + reranker vs LLMLingua-2 | +9.3 (+0.7, +18.0) | +10.0 (+1.3, +19.3) | +9.7 (+3.7, +15.7) |
| LLMSlim lexical vs LLMLingua-2 | −1.3 (−8.7, +6.0) | +0.7 (−9.3, +10.7) | −0.3 (−6.7, +6.0) |

These intervals resample cases. The three gold positions of one question are correlated, so intervals that resample
whole questions are wider: over all 300 cases, reranker vs LLMLingua-2 becomes about 0.0 to +19.3, and reranker vs
LongLLMLingua about −8 to +9.

LongLLMLingua won test_a by 6 points and LLMSlim won test_b by 7.3. Over all 300 cases the two are level, and
LLMSlim with the reranker is about 100 times faster per question (median wall-clock time to compress: 0.09 s against
9.3 s on our machine); LongLLMLingua runs a 7B model. On test_a the gap came from reading
rather than retention: LLMSlim's output still contained a gold answer more often (79.3% of cases against 75.3%),
but when the answer was present the reader got it right 89.9% of the time with LLMSlim's fragments and 95.6% with
LongLLMLingua's reordered, more complete passages. Two ideas aimed at that gap were tested on dev questions and
dropped (see "How the numbers were kept honest"). LLMSlim with the reranker is ahead of LLMLingua-2 on both splits;
without any model it is level with LLMLingua-2.

Notes on the competitors:
- **LLMLingua-2** was asked for `rate=0.25` first. It kept only 16% of the tokens (469) and scored 64.7. Held to the
  same token count (`target_token`), it scored the same 64.7.
- **LongLLMLingua** uses LLaMA-2-7B-chat quantised to 4-bit (NF4) so it fits a 6 GB GPU. The paper does not state
  its precision.

On these 150 cases, LLMSlim without the reranker scores 63.3 against 68.0 for the pre-release 0.8. On the 75
cases where both builds sent an identical prompt, Haiku's answers still differed 5 times. Over all 300
cases the two builds score 65.7 and 66.7.

### HotpotQA (distractor): multi-hop retrieval QA

Official EM/F1, 10 paragraphs per question. LLMSlim budget: 40%.

| Configuration | test_a F1 (200) | test_a EM | test_b F1 (200, fresh) | test_b EM | Input tokens | $ per 1k |
|---|---:|---:|---:|---:|---:|---:|
| Full context | 74.9 | 57.0 | 77.5 | 59.0 | 2,179 | 0.245 |
| **LLMSlim 0.8 + reranker** | **69.4** | **56.0** | **71.8** | **54.5** | 939 | 0.137 |
| LLMSlim 0.8, lexical | 67.5 | 52.5 | 70.1 | 52.5 | 936 | 0.133 |
| LLMSlim 0.7.2 | 61.7 | 50.5 | | | 1,159 | 0.180 |
| Truncate to the same budget | 49.5 | 38.0 | 41.1 | 29.5 | 1,147 / 912 | 0.194 |
| No context | 43.8 | 34.5 | | | 84 | 0.120 |

### LongBench v1: seven long-context tasks

30 samples per task and split, official prompts and metrics, budget 3,000 tokens. Code tasks are scored on the first
code line inside the model's fenced block (`rescore_code.py`; the official rule scores Haiku's prose preamble).

| Task (test_a) | Full | LLMSlim 0.8 | + reranker | 0.7.2 | Truncate |
|---|---:|---:|---:|---:|---:|
| Qasper | 42.2 | 42.7 | 42.7 | 46.5 | 38.1 |
| 2WikiMQA | 76.9 | 75.3 | 75.7 | 71.9 | 47.4 |
| MuSiQue | 64.9 | 58.8 | 61.2 | 58.5 | 43.2 |
| GovReport | 19.0 | 17.5 | 17.7 | 17.7 | 17.0 |
| TriviaQA | 89.9 | 89.2 | 87.9 | 88.5 | 87.9 |
| LCC | 47.2 | 44.0 | 44.4 | 47.4 | 45.2 |
| RepoBench-P | 44.3 | 57.2 | 50.0 | 36.0 | 37.3 |
| **Macro, test_a** | **54.9** | **54.9** | 54.2 | 52.4 | 45.2 |
| **Macro, test_b (fresh)** | **55.1** | **55.0** | **55.4** | | 46.8 |
| Mean input tokens | 15,532 | 5,232 | 5,229 | 5,164 | 5,147 |

Lexical LLMSlim 0.8 against full context, on a third of the tokens:

| Split | Difference | 95% CI | vs truncation |
|---|---:|---|---:|
| test_a | +0.0 | −4.5 to +4.6 | +9.8 |
| test_b | −0.1 | −4.2 to +4.1 | |

MuSiQue is still below full context. The 0.8 pre-release had dropped it to 48.3, and most of that is recovered.

### LongBench v2 (short split)

180 multiple-choice questions over long documents, codebases and structured data (30k tokens on average), official
prompt, middle truncation to 120k for every arm. LLMSlim budget: 25%.

| Configuration | Accuracy | vs full (95% CI) | Tokens | $ per 1k |
|---|---:|---|---:|---:|
| Full context | 60.0 | | 30,493 | 7.62 |
| **LLMSlim 0.8 + reranker** | **55.6** | −4.4 (−11.7 to +2.8) | 8,469 | 1.69 |
| LLMSlim 0.8, lexical | 53.9 | −6.1 (−13.3 to +1.1) | 8,470 | 1.69 |
| LLMSlim 0.7.2 | 51.1 | | 8,566 | 1.90 |
| Middle truncation, same budget | 48.3 | −11.7 (−20.6 to −3.3) | 8,566 | 1.94 |

### SWE-bench Verified Mini: coding agent

50 issues (25 Django, 25 Sphinx). A minimal bash-tool agent (`swe/agent.py`, mini-swe-agent style) runs on the
official per-task images and is graded by the official `swebench` harness. LLMSlim compresses a command's output
before it enters the history. The history is append-only, so prompt caching and replayed thinking stay valid.

| Configuration | Resolved | Prompt tokens per task | $ per task |
|---|---:|---:|---:|
| No compression, run A | 36 / 50 | 58,117 | 0.0032 |
| No compression, run B | 38 / 50 | 48,126 | 0.0027 |
| LLMSlim 0.7.2, outputs over 800 tokens | 34 / 50 | 58,850 | 0.0031 |
| **LLMSlim 0.8.0, outputs over 800 tokens** | **38 / 50** | 51,332 | 0.0029 |

There is no harm and little saving. Haiku keeps its context near 8k tokens with targeted commands, so there is not
much to remove. Line-mode selection is unchanged since this run, and the only code changes since then are faster
sentence splitting and guardrail screening, which produce identical output. For comparison, published work found
LLMLingua-2 on tool output cost an agent 8 points.

### InjecAgent: prompt injection through tool output (Platform)

1,054 cases, enhanced setting. Attack success means the next turn calls the attacker's tool.

| Configuration | Attack success | Repeated user-tool calls |
|---|---:|---:|
| Native tool-use history | 0 / 1,054 | 1 |
| Platform, tool events then `prepare(user_input=instruction)` | 0 / 1,054 | 50 |
| Same, calls shown beside their results (`tool_calls`) | 0 / 1,054 | 43 |
| **Platform agent turn: user message, call, result, `prepare(continue_turn=True)`** | **0 / 1,054** | **0** |

Haiku 5.5 resisted every attack without help, so this benchmark shows no defence effect with this model. It did show
an agent-loop gap in the Platform:

- **Before:** `prepare()` only took new user input, so the request always came after the tool results it had
  produced, and the model repeated its call in 4.7% of cases.
- **Fixed in Platform 0.9.1:** agent turns compile the next step in order, and no call was repeated.

## Published results from other systems

These use different reader models, so compare each system's gap to its own full-context baseline, not raw scores.

| System | Benchmark | Reader | Score | Full context | Source |
|---|---|---|---:|---:|---|
| Zep | LongMemEval-S | GPT-4o | 71.2 | 60.2 | [arXiv:2501.13956](https://arxiv.org/abs/2501.13956) (self-reported) |
| Mem0 | LongMemEval-S | GPT-4o-mini | 53.6-66.4 | 55.4-56.8 | third-party re-runs, [arXiv:2507.03724](https://arxiv.org/abs/2507.03724) |
| LongLLMLingua, 4x | NQ 20 documents | GPT-3.5-Turbo | 71.2-75.0 | 54.1-75.7 | [arXiv:2310.06839](https://arxiv.org/abs/2310.06839) |
| LLMLingua-2, 3.9x | NQ 20 documents | GPT-3.5-Turbo | 39.9-48.6 | 54.1-75.7 | [arXiv:2403.12968](https://arxiv.org/abs/2403.12968) |
| LLMLingua-2, 3k | LongBench v1 | GPT-3.5-Turbo | 42.4 | 44.0 | [arXiv:2403.12968](https://arxiv.org/abs/2403.12968) |
| LLMLingua-2 on tool output | SWE-bench Verified (50) | not stated | 54% | 62% | [arXiv:2601.16746](https://arxiv.org/abs/2601.16746) |

## Reproduce

Data is not committed. Put each dataset under `data/` as the scripts expect:

- LongBench v1: `THUDM/LongBench`
- LongBench v2: `zai-org/LongBench-v2`
- LongMemEval: `xiaowu0162/longmemeval-cleaned`, file `longmemeval_s_cleaned.json`
- NaturalQuestions 20-document files: `nelson-liu/lost-in-the-middle`
- HotpotQA distractor validation: rows 0 to 800
- InjecAgent: the `data/` folder of `uiuc-kang-lab/InjecAgent`
- SWE-bench Verified Mini: `MariusHobbhahn/swe-bench-verified-mini`

```bash
export LLMSLIM_KEY_FILE=/path/to/file/with/CLAUDE_API_KEY   # never printed or written
export HAIKU_CAP_USD=60                                      # hard spend cap across all suites
python splits.py                                             # writes splits.json (already committed)
python devcheck.py --suites nq hotpot lb lme                 # development checks, dev split only, no API
bash runs.sh                                                 # test_a and test_b, lexical and reranker arms
bash competitors.sh                                          # LLMLingua-2 and LongLLMLingua on NQ
python verify_built.py nq:core08f_global nq:core08s_global   # built prompts match the source
python final_report.py                                       # every table above, with CIs
```

- **GPU environments:** LLMLingua-2 and the reranker run in an environment with CUDA PyTorch and
  `sentence-transformers` (`LINGUA_DEVICE=cuda`). LongLLMLingua needs `transformers==4.44.2`, `accelerate==0.34.2`
  and `bitsandbytes`, because its key-value cache code predates transformers 5. See `competitors.sh`.
- **Raw results:** per-question results are in `results/*.jsonl.gz`, with predictions truncated to 400-600
  characters, and in `swe/runs/*/`.
- **Mislabelled SWE arm:** in `swe/runs/v072/`, the arm recorded as `llmslim_eager` actually ran the baseline
  filter because a harness patch did not apply. It is the second uncompressed run, "run B" above, and its
  predictions are in `preds_baseline_b.jsonl.gz`.
