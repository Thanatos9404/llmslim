#!/usr/bin/env bash
# Regenerates every table in RESULTS.md from results/*.jsonl.gz (run from this folder): bash tables.sh > tables.md
set -euo pipefail
R=results
report() { python report.py "$@"; echo; }

# Memory systems' ingestion (Haiku 5.5 calls through meter_proxy.py), USD : questions served by that memory.
MEM0_LOCOMO="mem0=2.70:1540"   # all 10 conversations ingested; 1,540 questions
ZEP_LOCOMO="zep=6.28:1307"     # the 8 test conversations; 1,307 questions
GPU=(--gpu rag rerank lingua2 longlingua llmslim_rr --cpu llmslim_rr-v2 llmslim_rr-v3)  # v2/v3 reranker arms: CPU

LOCOMO=($R/locomo_test*.jsonl.gz)
echo "## LoCoMo, about 1,000 tokens"
report --results "${LOCOMO[@]}" --reference llmslim-v3_1000 --ingest $MEM0_LOCOMO $ZEP_LOCOMO "${GPU[@]}" \
  --arms llmslim-v3_1000 llmslim-v2_1000 llmslim_1000 llmslim_rr-v3_1000 mem0_top20 rag_1000
echo "## LoCoMo, about 2,500 tokens"
report --results "${LOCOMO[@]}" --reference llmslim-v3_2500 --ingest $MEM0_LOCOMO $ZEP_LOCOMO "${GPU[@]}" \
  --arms llmslim-v3_2500 llmslim-v2_2500 llmslim_2500 llmslim_rr-v3_2500 mem0_top50 zep rag_2500 lingua2_2500 \
  longlingua_2500 recent_2500
echo "## LoCoMo, about 10,000 tokens and the full history"
report --results "${LOCOMO[@]}" --reference llmslim-v3_10000 --ingest $MEM0_LOCOMO $ZEP_LOCOMO "${GPU[@]}" \
  --arms llmslim-v3_10000 llmslim-v2_10000 llmslim_10000 mem0_top200 rag_10000 lingua2_10000 full
echo "## LoCoMo, token F1 (no judge)"
report --results "${LOCOMO[@]}" --reference llmslim-v3_2500 --metric f1 --ingest $MEM0_LOCOMO $ZEP_LOCOMO "${GPU[@]}" \
  --arms llmslim-v3_1000 llmslim-v3_2500 llmslim-v3_10000 mem0_top20 mem0_top50 mem0_top200 zep rag_2500 \
  lingua2_2500 longlingua_2500 full
echo "## LoCoMo, LLMSlim with the [nlp] extra (NLTK sentence splitter)"
report --results "${LOCOMO[@]}" --reference llmslim-v2-nltk_2500 "${GPU[@]}" \
  --arms llmslim-v2-nltk_1000 llmslim-v2-nltk_2500 llmslim-v2-nltk_10000 llmslim-nltk_1000 llmslim-nltk_2500

for SUITE in nq hotpot; do
  FILES=($R/${SUITE}_test*.jsonl.gz)
  echo "## ${SUITE}"
  report --results "${FILES[@]}" --reference llmslim_rr-v3 "${GPU[@]}" \
    --arms full order rerank llmslim llmslim-v3 llmslim_rr llmslim_rr-v3 lingua2 llmslim-nltk
  echo "## ${SUITE}, LongLLMLingua's 1,000-question sample"
  report --results "${FILES[@]}" --reference llmslim_rr-v3 "${GPU[@]}" --ids "$R/${SUITE}_longlingua_ids.txt" \
    --arms full rerank llmslim-v3 llmslim_rr-v3 lingua2 longlingua
done

LME=($R/lme_test*.jsonl.gz)
for METRIC in score score_mem0_judge; do
  echo "## LongMemEval-S, 180 questions ($METRIC)"
  report --results "${LME[@]}" --reference llmslim-v3_2500 --metric $METRIC "${GPU[@]}" \
    --arms llmslim-v3_2500 llmslim-v3_10000 llmslim-v2_2500 llmslim-v2_10000 llmslim_rr-v3_2500 \
    llmslim_rr-v3_10000 recent_2500 recent_10000 rag_2500 rag_10000 lingua2_2500 lingua2_10000 full
done
for METRIC in score score_mem0_judge; do
  echo "## LongMemEval-S, Mem0's 60-question sample ($METRIC)"
  report --results "${LME[@]}" --reference llmslim-v3_2500 --metric $METRIC --ids "$R/lme_memory_sample.txt" \
    --ingest "mem0=$(cat $R/mem0_lme_ingest_usd.txt):60" "${GPU[@]}" \
    --arms llmslim-v3_2500 llmslim-v3_10000 llmslim_rr-v3_2500 rag_2500 rag_10000 mem0_top20 mem0_top50 \
    mem0_top200 full
  echo "## LongMemEval-S, Zep's 24-question sample ($METRIC)"
  report --results "${LME[@]}" --reference llmslim-v3_2500 --metric $METRIC --ids "$R/lme_zep_sample.txt" \
    --ingest "mem0=$(cat $R/mem0_lme_ingest_usd.txt):60" "zep=$(cat $R/zep_lme_ingest_usd.txt):24" "${GPU[@]}" \
    --arms llmslim-v3_2500 llmslim-v3_10000 llmslim_rr-v3_2500 rag_2500 mem0_top50 mem0_top200 zep full
done

# LLMSlim v4 (#51), chosen on dev after the other round-3 results, read once on test and not shipped (#52 reverted
# it). Kept apart so it does not change the cost frontier of the tables above.
for B in 1000 2500 10000; do
  echo "## LLMSlim v4 (not shipped), LoCoMo, about $((B / 1000)),$(printf %03d $((B % 1000))) tokens"
  ARMS=(llmslim-v3_$B llmslim-v4_$B)
  [ $B != 10000 ] && ARMS+=(llmslim_rr-v3_$B llmslim_rr-v4_$B)
  report --results "${LOCOMO[@]}" --reference llmslim-v3_$B "${GPU[@]}" --arms "${ARMS[@]}"
done
for METRIC in score score_mem0_judge; do
  for B in 2500 10000; do
    echo "## LLMSlim v4 (not shipped), LongMemEval-S, about $((B / 1000)),$(printf %03d $((B % 1000))) tokens ($METRIC)"
    report --results "${LME[@]}" --reference llmslim-v3_$B --metric $METRIC "${GPU[@]}" \
      --arms llmslim-v3_$B llmslim-v4_$B llmslim_rr-v3_$B llmslim_rr-v4_$B rag_$B
  done
done
