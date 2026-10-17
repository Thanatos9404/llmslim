# What `llmslim wrap claude` does to a Claude Code bill

This benchmark asks a narrow question: on a real Claude Code session, does running it through `llmslim wrap claude`
change what the API bills? Tokens not sent are not the same as money saved. Most of a Claude Code request is read from
the prompt cache at a tenth of the input price, and a run that takes one extra turn pays for the whole cached prefix
again. So this counts billed dollars, with cache reads and cache writes priced separately, and it reports every run.

## Protocol (written and committed before the measured runs)

- **Agent:** Claude Code 2.1.296 in print mode (`claude -p ... --output-format json`), model `claude-haiku-5-5`,
  default settings otherwise. Each run gets a fresh copy of the fixture and its own empty `CLAUDE_CONFIG_DIR`, so no
  user settings, CLAUDE.md, plugins or MCP servers take part. `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`.
- **Arms:**
  - `plain`: `claude` talking to the API directly;
  - `llmslim`: the same command through `llmslim wrap claude` from the published `llmslim` 0.11.0, default options,
    with a fresh proxy database per run.
- **Tasks** (`make_fixture.py`): a small billing package with about 260 passing parametrized tests, so `pytest -v`
  prints about 22 KB. That is under the roughly 30 KB at which Claude Code saves output to a file instead of showing
  it to the model.
  - `one-bug`: one bug (refund rounding). The prompt asks the agent to run `pytest -v`, fix the source without
    changing the tests, and run `pytest -v` again.
  - `three-bugs`: three bugs in three modules. The prompt asks the agent to fix them one at a time and run `pytest -v`
    after each fix.
- **Runs:** 8 per arm per task. The arms alternate (plain first on even runs, llmslim first on odd runs) so time of
  day and API load affect both.
- **Allowed tools:** Read, Edit, Write, Grep, Glob, and Bash or PowerShell limited to `pytest`, `python -m pytest`,
  `ls` and `cat`. At most 40 turns, 15 minutes per run.
- **Measured per run:**
  - billed dollars from Claude Code's per-model usage at Claude Haiku 5.5 list prices: input $0.10 and output $0.50
    per million tokens, cache reads 0.1x input, 5-minute cache writes 1.25x;
  - Claude Code's own `total_cost_usd`, as a cross-check;
  - turns, wall time, and the proxy's own `llmslim proxy stats`;
  - **success:** after the run, the whole suite passes and the test files are byte-identical to the fixture.
- **Reported:** every run, in `results/*.jsonl`. No run is dropped or rerun. A run that fails because of the API or
  the harness is reported as such and counted in the table with its cost.
- **Summary:** per task and arm, the median and mean billed cost, the success rate and the median turns, plus the
  difference in mean cost with a 95% bootstrap interval.

Before the measured runs, one smoke pair on `one-bug` checked the harness. It is not part of the results, and is
reported here because it shaped what we expect:

| Smoke run | Turns | Billed | Passed |
|---|---|---|---|
| plain | 7 | $0.00523 | yes |
| llmslim | 8 | $0.00626 | yes |

In both runs the agent limited the output itself. It ran `pytest -v 2>&1 | tail -80`, and later `| tail -5`. So the
proxy had one output long enough to shorten: the 80-line tail, 1,624 tokens, which it cut to 387. Over the five later
requests that kept 6,185 tokens out (`llmslim proxy stats` sums its counts over requests). Meanwhile the llmslim run
took one more turn, and each turn re-reads 16,000 to 18,000 cached tokens. If that pattern holds, the proxy saves little
or nothing on tasks like these, and the results will say so.

## Reproduce

```bash
pip install "llmslim[proxy]==0.11.0" pytest
export ANTHROPIC_API_KEY=...
python run.py --task one-bug --runs 8 --out results/one-bug.jsonl
python run.py --task three-bugs --runs 8 --out results/three-bugs.jsonl
python summarize.py results/*.jsonl
```

## Results

Not run yet.
