# Round 3: LLMSlim against Mem0, Zep, LLMLingua-2 and LongLLMLingua

Measured in October 2026. Every system is read by the same model, Claude Haiku 5.5 (`claude-haiku-5-5`, effort low),
with the same prompt and the same judge, at the same context budget. Only the context changes.

Results: [RESULTS.md](RESULTS.md) (filled in when the runs finish).

## What changed from earlier rounds, and why

Earlier rounds were criticised on three points, and this round answers each:

| Criticism | What this round does |
|---|---|
| "Self-run on the author's machine" | Every compressor's build step (LLMSlim, LLMLingua-2, LongLLMLingua, the retrieval baselines) runs in public Kaggle notebooks, pinned to a commit, with the data fetched from its original source and checked by sha256. They make no model API calls; anyone can rerun them and compare the outputs byte for byte. |
| "LongLLMLingua was handicapped (4-bit)" | LongLLMLingua runs LLaMA-2-7B-chat in **float16**, the precision its weights are published in, on Kaggle's 2× T4, with the paper's settings. |
| "Memory systems were only cited, never run" | **Mem0** (open source, 2.2.1) and **Zep** (its open-source engine, Graphiti 0.30.2) are run head to head, each following its vendor's own published LoCoMo and LongMemEval protocol, with Mem0's own answer and judge prompts used for every system. |
| Small samples | NaturalQuestions 2,255 questions, HotpotQA 2,000, LoCoMo 1,540, LongMemEval-S 180. |

## How the numbers were kept honest

- **Splits were committed before any result.** `splits_r3.json`, from `splits_r3.py`, was pushed in commits `6713c93` and
  `2110c3e`, before any round-3 model call. Later additions (Zep's LongMemEval sample) were also committed before any
  result they could affect, and none of them changed an earlier split.
- **Tuning used dev only.** LoCoMo conversations 0-1, the LongMemEval dev questions, and the earlier NQ and HotpotQA
  dev questions. The one LLMSlim change made in this round, turn-by-turn transcripts (PR #48), was chosen and checked
  there. It was frozen and merged before any test result was read.
- **Both LLMSlim configurations are reported everywhere:** lexical (the default, no model) and with its optional 22M
  reranker. Neither is picked per suite.
- **Before and after.** The release as it was (0.8.1 plus merged changes up to `e607cbd`) is reported next to the
  round-3 change (`0accc73`).
- **Competitors in their own words.** Answer and judge prompts are Mem0's, vendored verbatim in `vendor/`
  (Apache-2.0). LongMemEval also uses its official judge, the headline there; LoCoMo also reports token F1, its
  original metric, which needs no model.
- **One meter for everything.** Every Mem0 and Zep LLM call goes through `meter_proxy.py`. It pins the model to Haiku
  5.5, adds the key so the libraries never see it, and records every call's tokens and cost. Ingestion cost is
  reported per system.

### LLMSlim's two installs

`pip install llmslim` splits sentences with a built-in regex splitter; `pip install llmslim[nlp]` adds NLTK, and
LLMSlim then uses NLTK's Punkt splitter. The public Kaggle builds use the default install, so the headline LLMSlim
rows are the default install. Some LLMSlim rows were first read from local builds in an environment that had NLTK
installed; their contexts differ from the Kaggle builds wherever a sentence boundary differs (about half the NQ
and HotpotQA questions, a tenth of LoCoMo's). They are reported too, labelled `-nltk`, as the `[nlp]` install.
Every other arm's local build matched its Kaggle build byte for byte.

## Systems

| System | Version | How it ran |
|---|---|---|
| LLMSlim | release `e607cbd`; round 3 `0accc73` | `compress_documents(sessions or passages, query=question, target_ratio)`; `relevance="semantic"` for the reranker variant (`cross-encoder/ms-marco-MiniLM-L-6-v2`) |
| Mem0 OSS | mem0ai 2.2.1 with spaCy and fastembed (BM25) | Mem0's harness (`mem0ai/memory-benchmarks@4b61c5d`): one LoCoMo turn per `add()`, a user/assistant pair per `add()` on LongMemEval, `search(top_k=200)`; read at top 20, 50 and 200 |
| Zep (Graphiti) | graphiti-core 0.30.2 on Neo4j 2026.09 | Zep's harness (`getzep/zep-papers`): each LoCoMo message an episode; each LongMemEval session an episode; 20 facts (cross-encoder) and 20 entities (RRF) in Zep's own context template |
| LLMLingua-2 | llmlingua 0.2.2, `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` | held to the same token budget (`target_token`) |
| LongLLMLingua | llmlingua 0.2.2, `NousResearch/Llama-2-7b-chat-hf`, float16 | the paper's NQ settings, held to the same token budget; on pre-registered samples (it takes about 7 s a question on a T4) |
| Rerank-only | `cross-encoder/ms-marco-MiniLM-L-6-v2` | whole passages ranked by the reranker LLMSlim's semantic mode uses, best first, while they fit |
| RAG over turns | `Qwen/Qwen3-Embedding-0.6B` | the turns most similar to the question, in date order, while they fit |
| Full / recent / order | | the whole context; the latest turns that fit; passages in retrieval order that fit |

### Where Mem0 and Zep differ from their own harnesses

Each difference is in their favour or is forced by this benchmark's rules (one model for every system):

- Both use Claude Haiku 5.5 for extraction (the only model used in this benchmark). Haiku 5.5 rejects sampling
  parameters, so the proxy drops `temperature`; long system prompts are marked cacheable, which changes the bill,
  not the output.
- Both use local `Qwen/Qwen3-Embedding-0.6B`, the embedder of Mem0's own published OSS runs; Zep uses its BGE reranker.
- Mem0 OSS rejects `add(timestamp=...)` (a platform feature), so its own OSS harness dates every memory at ingestion
  time and resolves "yesterday" against today. Here each memory gets its session's date as `created_at`, and the
  extraction prompt's Observation Date is the session's date.
- Zep Cloud is a hosted service; this runs Graphiti, the engine Zep is built on, on Neo4j (Graphiti's primary
  backend). Zep's own LoCoMo script read a photo-caption key LoCoMo does not have; here every system sees the captions.
- On LongMemEval, Zep's run added every message on its own; here each session is one episode, to keep the cost of
  Graphiti's several calls per episode within budget.
- On LongMemEval, Mem0's default output cap (2,000 tokens) cut off about 2% of its extraction replies, which Mem0 then
  drops. The cap is raised to 8,192 for Mem0's LongMemEval run; the 12 questions first built under the old cap were
  rebuilt before any reader saw them. (No LoCoMo extraction reply reached 2,000 tokens.)
- Mem0 runs on the 24 LongMemEval questions of `zep_sample` (4 per question type); its extraction costs about $0.33
  a question on these 500-message histories. Zep's graph costs about $0.68 a question (a measured one-question
  pilot: 49 session episodes, 445 calls), so to stay inside the spend cap Zep runs on the first 2 questions of each
  type in `zep_sample` (12 questions, the pilot's included). This cut was made before any Zep or Mem0 LongMemEval
  answer was read, and Mem0 and Zep are compared on those same 12.

### What was not run

- LongLLMLingua on LongMemEval: its LLaMA-2-7B scorer takes about 7 s for a 3k-token NQ context on a T4, so the 180
  histories of about 115k tokens would need roughly 13 hours, more than one Kaggle session allows. It is reported on
  NQ, HotpotQA and LoCoMo.

## Reproduce

1. Builds: the public notebooks (`kaggle_round3_*.ipynb`, or `kaggle_run.py setup|data|build|package` on any Linux GPU).
2. Memory systems: `meter_proxy.py`, then `mem0_locomo.py`, `zep_locomo.py`, `mem0_lme.py`, `zep_lme.py` (Neo4j for Zep).
3. Reader and judges: `reader_rag.py`, `reader_locomo.py`, `reader_lme.py` with a Claude API key; `report.py` for tables.
