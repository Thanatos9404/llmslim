# Failure analysis

The observable pattern is that fixed-rank dense and RRF improve some semantic paraphrases, but development-derived gates cannot safely distinguish their remaining multi-tool and tool-family misses. They expose the full catalog more often than BM25.

| Class | Observation | Outcome |
| --- | --- | --- |
| Semantic paraphrase | Dense accepts indirect event/mail/code/file wording. | One frozen all-required improvement vs BM25. |
| Lexical exact match | BM25 is already strong on direct tool terms. | Dense adds little selectivity. |
| Tool-family confusion | Search/create/cancel family members cluster semantically. | Conservative full-catalog fallback. |
| Multi-tool | One missing member invalidates success. | All-required metric governs the gate. |
| No-tool | Similarity is not tool necessity. | Independent gate retained 100% measured accuracy. |
| Multilingual | E5 processes Hindi/Chinese/Japanese test text. | 94.4% fail-open, so no selectivity claim. |
| Metadata poisoning | `_meta` and annotations never enter representations. | Boundary test passes. |
| Description poisoning | Pre-tokenization cap prevents costly stuffing. | Improved after ToolRet discovery. |

No chain-of-thought is recorded; these are observable rank and policy effects.
