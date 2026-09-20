# Planner CLI

The legacy compression command is unchanged. Adaptive planning uses a nested
command and accepts a JSON object with optional `messages`, `documents`,
`memories`, `tools`, and `query` keys:

```bash
llmslim plan context.json --model sarvam-105b \
  --max-input-tokens 32000 --reserve-output-tokens 4096 \
  --policy balanced --json --no-content
```

Use `-` instead of a path to read stdin. Input is capped at 20 MiB. `--json`
emits a structured plan; content is included only when explicitly allowed.
`--fail-on-infeasible` returns a non-zero status when mandatory context exceeds
the available budget. Secrets are not accepted as command-line flags.
