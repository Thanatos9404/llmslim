# Multilingual robustness report

This separate robustness suite has four semantic requests each in English, Hindi, Chinese, and Japanese, plus a no-tool and multi-tool case. It is not a replacement for the frozen primary corpus and is too small to claim language-general product quality.

The pinned E5 model accepts each script and the dense dynamic policy retained all required tools and correctly withheld the no-tool case, but only by failing open on 94.4% of this suite. This validates Unicode handling and safety fallback—not multilingual selectivity.
