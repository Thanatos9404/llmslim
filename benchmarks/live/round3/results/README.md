# Round 3 result files

One JSON row per question and arm, gzipped. Every row has the arm, the question id, the score(s), the reader's
prediction, the context size, the build (or search) time, token counts and cost of the answer call, and whether the
call went through the Message Batches API. `../tables.sh` turns them into every table in `../RESULTS.md`.

| Files | Suite | Arms |
|---|---|---|
| `locomo_test_*.jsonl.gz` | LoCoMo, conversations 2-9 (1,307 questions) | `score` is Mem0's judge, `f1` token F1 |
| `lme_test_*.jsonl.gz` | LongMemEval-S test (180) | `score` is the official judge, `score_mem0_judge` Mem0's |
| `nq_test*.jsonl.gz`, `hotpot_test*.jsonl.gz` | NQ (2,255), HotpotQA (2,000) | `score`: NQ answer match, HotpotQA exact match (`f1` too) |
| `dev/` | the dev splits | the evidence behind round 3's two LLMSlim changes |

Arm names: `llmslim` is the release, `llmslim-v2` and `llmslim-v3` the two round-3 versions, `_rr` the optional
reranker, `-nltk` the `llmslim[nlp]` install; `_1000` and so on are the token budget. `mem0_topK` reads Mem0's top
K memories; `zep` is Zep's 20 facts and 20 entities; `full`, `recent`, `order`, `rerank` and `rag` are baselines;
`lingua2` and `longlingua` are LLMLingua-2 and LongLLMLingua.

Where each context came from: the public Kaggle notebooks (`kaggle_round3_*`), whose manifests list the sha256 of
every output. The v2/v3 lexical arms and the LongMemEval full and recent arms were read from local builds that match
the Kaggle outputs byte for byte (checked for every context); their rows carry the Kaggle build time. The `-nltk`
arms and the dev files come from local builds in an environment with NLTK installed.

`lme_memory_sample.txt`, `lme_zep_sample.txt` and `*_longlingua_ids.txt` are the pre-registered samples (from
`../splits_r3.json`); `mem0_lme_ingest_usd.txt` and `zep_lme_ingest_usd.txt` are what building their LongMemEval
memories cost (calls behind the final memories only; discarded and crashed runs excluded).
