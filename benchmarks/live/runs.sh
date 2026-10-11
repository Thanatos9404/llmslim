#!/bin/bash
# Final evaluation of the frozen release, lexical (core08f) and with the reranker (core08s), on the reported
# questions (test_a) and on the fresh sample (test_b). Sequential and resumable: finished items are skipped.
#
#   LLMSLIM_KEY_FILE=path/to/key.txt  BENCH_PY=path/to/python  bash benchmarks/live/runs.sh
#
# Run from the repository root so the package under test is the one in this checkout.
set -u
: "${LLMSLIM_KEY_FILE:?set LLMSLIM_KEY_FILE to a file that holds the API key}"
B="$(cd "$(dirname "$0")" && pwd)"
PY="${BENCH_PY:-python}"
export PYTHONPATH="$(pwd):$B" HAIKU_CAP_USD="${HAIKU_CAP_USD:-60}" PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
       HF_HUB_DISABLE_PROGRESS_BARS=1 TRANSFORMERS_VERBOSITY=error
quiet() { grep -v -i "warn\|symlink\|developer mode\|loading weights" | tail -3; }
b2() { HAIKU_SUITE="$1" "$PY" "$B/bench2.py" "${@:2}" 2>&1 | quiet; }

echo "== NQ"
b2 nq build --suite nq --n 300 --arms core08f_global
b2 nq build --suite nq --n 300 --arms core08s_global --workers 2
b2 nq run --suite nq --n 300 --arms core08f_global core08s_global
b2 nq build --suite nq --n 300 --split test_b --arms full core08f_global truncate --truncate-ref core08f_global
b2 nq build --suite nq --n 300 --split test_b --arms core08s_global --workers 2
b2 nq run --suite nq --n 300 --split test_b --arms full core08f_global core08s_global truncate

echo "== HotpotQA"
HAIKU_SUITE=rag "$PY" "$B/suite_rag.py" --only llmslim_doc=core08f_doc 2>&1 | quiet
HAIKU_SUITE=rag BENCH_RELEVANCE=semantic "$PY" "$B/suite_rag.py" --only llmslim_doc=core08s_doc 2>&1 | quiet
HAIKU_SUITE=rag "$PY" "$B/suite_rag.py" --split test_b --out "$B/results/suite_rag_b.jsonl" --only full=full,truncate=truncate,llmslim_doc=core08f_doc 2>&1 | quiet
HAIKU_SUITE=rag BENCH_RELEVANCE=semantic "$PY" "$B/suite_rag.py" --split test_b --out "$B/results/suite_rag_b.jsonl" --only llmslim_doc=core08s_doc 2>&1 | quiet

echo "== LongBench v1"
HAIKU_SUITE=longbench "$PY" "$B/suite_longbench.py" --per-task 30 --only llmslim=core08f 2>&1 | quiet
HAIKU_SUITE=longbench BENCH_RELEVANCE=semantic "$PY" "$B/suite_longbench.py" --per-task 30 --only llmslim=core08s 2>&1 | quiet
HAIKU_SUITE=longbench "$PY" "$B/suite_longbench.py" --per-task 30 --split test_b --out "$B/results/suite_longbench_b.jsonl" --only full=full,llmslim=core08f,truncate=truncate 2>&1 | quiet
HAIKU_SUITE=longbench BENCH_RELEVANCE=semantic "$PY" "$B/suite_longbench.py" --per-task 30 --split test_b --out "$B/results/suite_longbench_b.jsonl" --only llmslim=core08s 2>&1 | quiet

echo "== LongMemEval"
b2 lme build --suite lme --n 90 --arms core08f_docs
b2 lme build --suite lme --n 90 --arms core08s_docs --workers 2
b2 lme run --suite lme --n 90 --arms core08f_docs core08s_docs
b2 lme build --suite lme --n 90 --split test_b --arms full core08f_docs truncate --truncate-ref core08f_docs
b2 lme build --suite lme --n 90 --split test_b --arms core08s_docs --workers 2
b2 lme run --suite lme --n 90 --split test_b --arms full core08f_docs core08s_docs truncate

echo "== LongBench v2"
b2 lbv2 build --suite lbv2 --n 180 --arms core08f_global
b2 lbv2 build --suite lbv2 --n 180 --arms core08s_global --workers 2
b2 lbv2 run --suite lbv2 --n 180 --arms core08f_global core08s_global
echo "== done"
