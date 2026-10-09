# Gemini context evaluation results

Prompts built 2026-10-09T21:33:30+00:00; 6 synthetic cases.

| Model | Condition | Passed |
| --- | --- | --- |
| Gemini 3.5 Flash-Lite | baseline | 4/6 |
| Gemini 3.5 Flash-Lite | llmslim | 6/6 |
| Gemini 3.8 Flash | baseline | 8/9 |
| Gemini 3.8 Flash | llmslim | 4/6 |

| Case | Baseline tokens | LLMSlim tokens |
| --- | --- | --- |
| injected-instruction | 253 | 212 |
| stale-tool-result | 238 | 198 |
| source-authority | 233 | 208 |
| tenant-leak | 215 | 184 |
| secret-redaction | 195 | 219 |
| changing-fact | 240 | 240 |
