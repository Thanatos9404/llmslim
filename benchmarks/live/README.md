# Real-model benchmarks: Claude Haiku 5.5

Measured in October 2026 with `claude-haiku-5-5` at `effort: low` through the Claude API. Every configuration
uses the same model, prompt template and scoring; only the context changes:

- **full**: the complete context.
- **LLMSlim**: the context after LLMSlim, at the stated budget.
- **truncate / recent**: the context cut, by the dataset's own rule, to exactly the token count LLMSlim produced.

The reported numbers come from questions that were never used to tune anything. Development checks used other
questions (`proxy.py` for free answer-retention checks, `dev_code.py` for code). Confidence intervals are
paired bootstrap 95% over the same questions. Weak results are reported with the strong ones.

Total API spend for everything below: about $17 (per-suite ledgers in `results/spend-*.json`).

## Results

### LongMemEval-S: memory over long chat histories

90 questions (15 per type) over histories of about 50 sessions (115k tokens). Official judge prompts, judged by
Haiku 5.5. Budget 8,000 tokens.

| Configuration | Accuracy | Context tokens | $ per 1k questions |
|---|---:|---:|---:|
| Full history | 82.2 | 114,006 | 90.72 |
| **LLMSlim Core 0.8.0**, `compress_documents` over sessions | **70.0** | 7,985 | 1.45 |
| LLMSlim Core 0.8.0, `compress` over the whole history | 66.7 | 7,993 | 1.46 |
| **LLMSlim Platform 0.9.1**, defaults | **63.3** | 7,600 | 1.36 |
| LLMSlim Core 0.7.2, `compress_documents` | 25.6 | 10,482 | 1.86 |
| LLMSlim Platform 0.9.0 (quality floor 0.5 so it compiles) | 18.9 | 7,287 | 1.30 |
| Most recent sessions that fit | 14.4 | 6,693 | 1.23 |

| Type (n=15 each) | Full | Core 0.8.0 | Platform 0.9.1 | Recent |
|---|---:|---:|---:|---:|
| knowledge-update | 80.0 | 86.7 | 86.7 | 33.3 |
| single-session-user | 100.0 | 86.7 | 93.3 | 13.3 |
| single-session-assistant | 93.3 | 93.3 | 80.0 | 20.0 |
| multi-session | 73.3 | 66.7 | 46.7 | 13.3 |
| temporal-reasoning | 60.0 | 46.7 | 46.7 | 6.7 |
| single-session-preference | 86.7 | 40.0 | 26.7 | 0.0 |

Core 0.8.0 vs full history: −12.2 points (95% CI −22.2 to −3.3) at 1/62 of the cost.

### HotpotQA (distractor): multi-hop retrieval QA

200 validation questions, official EM/F1, 10 paragraphs per question (about 2,200 tokens). LLMSlim budget: 40%.

| Configuration | EM | F1 | Input tokens | $ per 1k |
|---|---:|---:|---:|---:|
| Full context | 57.0 | 74.9 | 2,179 | 0.245 |
| **LLMSlim Core 0.8.0** | **54.0** | **68.0** | 935 | 0.134 |
| LLMSlim Core 0.7.2 | 50.5 | 61.7 | 1,159 | 0.180 |
| LLMSlim 0.7.2 `ContextRuntime` | 51.0 | 66.0 | 1,379 | 0.170 |
| Truncate to the same budget | 38.0 | 49.5 | 1,147 | 0.194 |
| No context | 34.5 | 43.8 | 84 | 0.120 |

Core 0.8.0 F1: +6.3 vs 0.7.2 (95% CI +0.5 to +12.3), +18.5 vs truncation (+11.5 to +25.3), −6.9 vs full (−11.4 to −2.8).

### NaturalQuestions, 20 documents ("lost in the middle")

The same 100 questions with the gold passage 1st, 10th and 20th (300 total). Metric: a gold answer appears in the
response. LLMSlim budget: 25%.

| Configuration | Accuracy | gold 1st | 10th | 20th | Tokens |
|---|---:|---:|---:|---:|---:|
| Full context | 86.3 | 88.0 | 87.0 | 84.0 | 2,889 |
| **LLMSlim Core 0.8.0** (`compress`) | **66.7** | 65.0 | 66.0 | 69.0 | 659 |
| LLMSlim Core 0.8.0 (`compress_documents`) | 64.0 | 62.0 | 64.0 | 66.0 | 655 |
| LLMSlim Core 0.7.2 (`compress_documents`, overshoots to 34%) | 71.0 | 75.0 | 70.0 | 68.0 | 995 |
| LLMSlim Core 0.7.2 (`compress`) | 62.3 | 63.0 | 58.0 | 66.0 | 727 |
| Passages in retrieval order, same budget | 52.0 | 95.0 | 32.0 | 29.0 | 669 |
| LLMLingua-2 (xlm-roberta-large, rate 0.25), 150 questions | pending | | | | |

LLMSlim's accuracy does not depend on where the answer sits. At equal tokens, Core 0.8.0 and 0.7.2's per-document
mode are about level (proxy check: 70% vs 69% answer retention at ~850-900 tokens). This is the weakest suite:
20 points below full context at 4.4x compression.

### LongBench v1: seven long-context tasks

30 samples per task (210), official prompts and metrics. Budget 3,000 tokens. Code tasks are scored on the first code
line inside the model's fenced block (the official first-line rule scores Haiku's prose preamble).

| Task | Full | Core 0.8.0 | Core 0.7.2 | Truncate |
|---|---:|---:|---:|---:|
| Qasper | 42.2 | 47.0 | 46.5 | 38.1 |
| 2WikiMQA | 76.9 | 80.5 | 71.9 | 47.4 |
| MuSiQue | 64.9 | 48.3 | 58.5 | 43.2 |
| GovReport | 19.0 | 17.4 | 17.7 | 17.0 |
| TriviaQA | 89.9 | 87.9 | 88.5 | 87.9 |
| LCC | 47.2 | 37.2 | 47.4 | 45.2 |
| RepoBench-P | 44.3 | 51.9 | 36.0 | 37.3 |
| **Macro** | **54.9** | **52.9** | **52.4** | **45.2** |
| Mean input tokens | 15,532 | 5,216 | 5,164 | 5,147 |

Core 0.8.0 macro: −2.0 vs full (95% CI −6.3 to +2.3), +7.7 vs truncation (+2.7 to +12.9).

Sampling noise is large at n=30: on the 23 LCC files short enough to be sent unchanged (identical prompts in every
arm), scores still ranged from 38.6 to 50.4. On the files that were compressed, RepoBench-P improved from 35.4
(0.7.2) to 53.5 (full: 43.7). MuSiQue fell, and is a known weak spot: whole-passage selection can miss the bridging
passage of a two-hop question.

### LongBench v2 (short split)

180 multiple-choice questions over long documents, codebases and structured data (30k tokens on average), official
prompt, middle truncation to 120k for every arm. LLMSlim budget: 25%.

| Configuration | Accuracy | Tokens | $ per 1k |
|---|---:|---:|---:|
| Full context | 60.0 | 30,493 | 7.62 |
| **LLMSlim Core 0.8.0** | **53.3** | 8,484 | 1.70 |
| LLMSlim Core 0.7.2 | 51.1 | 8,566 | 1.90 |
| Middle truncation, same budget | 48.3 | 8,566 | 1.94 |

### SWE-bench Verified Mini: coding agent

50 issues (25 Django, 25 Sphinx). A minimal bash-tool agent (`swe/agent.py`, mini-swe-agent style) on the official
per-task images; graded by the official `swebench` harness. LLMSlim compresses a command's output before it enters
the history (append-only, so prompt caching and replayed thinking stay valid).

| Configuration | Resolved | Prompt tokens per task | $ per task |
|---|---:|---:|---:|
| No compression, run A | 36 / 50 | 58,117 | 0.0032 |
| No compression, run B | 38 / 50 | 48,126 | 0.0027 |
| LLMSlim 0.7.2, outputs over 800 tokens | 34 / 50 | 58,850 | 0.0031 |
| LLMSlim 0.8.0 (pre-release build), outputs over 800 tokens | 35 / 50 | 69,466 | 0.0035 |
| LLMSlim 0.8.0 (pre-release build), outputs over 300 tokens | 35 / 50 | 86,646 | 0.0038 |
| **LLMSlim 0.8.0 (final), outputs over 800 tokens** | **38 / 50** | 51,332 | 0.0029 |

The final 0.8.0 matches the best uncompressed run (38 of 50) at a cost per task between the two uncompressed runs:
no harm, and little saving. Haiku keeps its context near 8k tokens with targeted commands, so there is not much to
remove, and the pre-release builds made it re-read more (more steps, more tokens). Compress long contexts, not
short coding loops. For comparison, LLMLingua-2 on tool output cost an agent 8 points in published work.

### InjecAgent: prompt injection through tool output

1,054 cases, enhanced setting. Attack success: the next turn calls the attacker's tool.

| Configuration | Attack success | Redundant user-tool calls |
|---|---:|---:|
| Native tool-use history | 0 / 1,054 | 1 |
| LLMSlim Platform 0.9.1 rendering | 0 / 1,054 | 50 |

Haiku 5.5 resisted every attack without help, so this benchmark shows no defence effect with this model.

## Published results from other systems

Different reader models, so compare each system's gap to its own full-context baseline, not raw scores.

| System | Benchmark | Reader | Score | Full context | Source |
|---|---|---|---:|---:|---|
| Zep | LongMemEval-S | GPT-4o | 71.2 | 60.2 | [arXiv:2501.13956](https://arxiv.org/abs/2501.13956) (self-reported) |
| Mem0 | LongMemEval-S | GPT-4o-mini | 53.6-66.4 | 55.4-56.8 | third-party re-runs, [arXiv:2507.03724](https://arxiv.org/abs/2507.03724) |
| LongLLMLingua, 4x | NQ 20 documents | GPT-3.5-Turbo | 71.2-75.0 | 54.1-75.7 | [arXiv:2310.06839](https://arxiv.org/abs/2310.06839) |
| LLMLingua-2, 3.9x | NQ 20 documents | GPT-3.5-Turbo | 39.9-48.6 | 54.1-75.7 | [arXiv:2403.12968](https://arxiv.org/abs/2403.12968) |
| LLMLingua-2, 3k | LongBench v1 | GPT-3.5-Turbo | 42.4 | 44.0 | [arXiv:2403.12968](https://arxiv.org/abs/2403.12968) |
| LLMLingua-2 on tool output | SWE-bench Verified (50) | not stated | 54% | 62% | [arXiv:2601.16746](https://arxiv.org/abs/2601.16746) |

## Reproduce

Data (not committed): LongBench v1 (`THUDM/LongBench`), LongBench v2 (`zai-org/LongBench-v2`), LongMemEval
(`xiaowu0162/longmemeval-cleaned`, `longmemeval_s_cleaned.json`), NaturalQuestions 20-document files from
`nelson-liu/lost-in-the-middle`, HotpotQA distractor validation, InjecAgent `data/` from `uiuc-kang-lab/InjecAgent`,
SWE-bench Verified Mini (`MariusHobbhahn/swe-bench-verified-mini`). Put them under `data/` as the scripts expect.

```bash
export LLMSLIM_KEY_FILE=/path/to/file/with/CLAUDE_API_KEY   # never printed or written
export HAIKU_CAP_USD=40                                      # hard spend cap across all suites
python suite_rag.py --limit 200                              # HotpotQA
python suite_longbench.py --per-task 30                      # LongBench v1
python bench2.py build --suite nq --n 300 --arms full llmslim_global llmslim_docs truncate
python bench2.py run   --suite nq --n 300 --arms full llmslim_global llmslim_docs truncate
python score2.py nq --by gold_at                             # likewise lbv2 (180), lme (90)
python swe/run.py --tag main --limit 50 --arms baseline llmslim   # in Linux with Docker
python injecagent.py --arms raw platform --settings enhanced      # needs LLMSlim Platform
```

Raw per-question results are in `results/*.jsonl.gz` (predictions truncated to 400-600 characters) and
`swe/runs/*/`.
In `swe/runs/v072/`, the arm recorded as `llmslim_eager` ran the baseline filter (a harness patch did not apply),
so it is the second uncompressed run, "run B" above; its predictions are `preds_baseline_b.jsonl.gz`.
