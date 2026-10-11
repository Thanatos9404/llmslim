#!/bin/bash
# LLMLingua-2 and LongLLMLingua on NQ (every second question of test_a and test_b), one model at a time.
#
#   LLMSLIM_KEY_FILE=path/to/key.txt  LINGUA_PY=path/to/python  LONGLINGUA_PY=path/to/python  bash benchmarks/live/competitors.sh
#
# LINGUA_PY: an environment with llmlingua and CUDA PyTorch. LONGLINGUA_PY: one with llmlingua,
# transformers==4.44.2, accelerate==0.34.2 and bitsandbytes (LongLLMLingua's cache code predates transformers 5).
set -u
: "${LLMSLIM_KEY_FILE:?set LLMSLIM_KEY_FILE to a file that holds the API key}"
B="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$(pwd):$B" HAIKU_CAP_USD="${HAIKU_CAP_USD:-60}" HAIKU_SUITE=nq PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
       HF_HUB_DISABLE_PROGRESS_BARS=1 TRANSFORMERS_VERBOSITY=error
quiet() { grep -v -i "warn\|symlink\|developer\|triton" | tail -2; }
for split in test_a test_b; do
  "${LONGLINGUA_PY:-python}" "$B/bench2.py" build --suite nq --n 300 --split "$split" --arms longllmlingua 2>&1 | quiet
  "${LONGLINGUA_PY:-python}" "$B/bench2.py" run --suite nq --n 300 --split "$split" --arms longllmlingua 2>&1 | quiet
  LINGUA_DEVICE="${LINGUA_DEVICE:-cuda}" "${LINGUA_PY:-python}" "$B/bench2.py" build --suite nq --n 300 --split "$split" --arms lingua2_eq 2>&1 | quiet
  "${LINGUA_PY:-python}" "$B/bench2.py" run --suite nq --n 300 --split "$split" --arms lingua2_eq 2>&1 | quiet
done
echo "== competitors done"
