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

## Measurement 1: llmslim 0.11.0 as released

| Task | Arm | Runs | Passed | Median turns | Median billed | Mean billed | Tokens not sent (median) |
|---|---|---|---|---|---|---|---|
| one-bug | plain | 8 | 8/8 | 8 | $0.00416 | $0.00425 | n/a |
| one-bug | llmslim | 8 | 8/8 | 9 | $0.00440 | $0.00437 | 8,040 |
| three-bugs | plain | 8 | 8/8 | 11 | $0.00538 | $0.00533 | n/a |
| three-bugs | llmslim | 8 | 8/8 | 11 | $0.00530 | $0.00529 | 10,428 |

- one-bug: mean billed cost +2.9% with llmslim (95% bootstrap interval of the difference: -$0.00031 to +$0.00052).
- three-bugs: -0.7% (-$0.00043 to +$0.00038).

**No measurable saving.** Reading the transcripts showed why. Through the 0.11.0 proxy, Claude Code's first request was
26,923 tokens instead of 19,795. With a custom base URL, Claude Code turns tool search off and sends every tool
definition on every request. That overhead cancelled what the compression saved. The fix (`wrap` sets
`ENABLE_TOOL_SEARCH=true`) brings the first request to 19,716 tokens against 19,712 without the proxy.

## Where a real Claude Code bill goes (offline, no API calls)

Corrected on 18 October 2026 (see Corrections at the end): the first version priced Claude Opus 5.5 cache reads at 0.1x
input, but Opus 5.5 reads cache at 0.05x.

We replayed the maintainer's own Claude Code transcripts offline: 32 sessions and the 412 subagent runs they started,
48,891 requests (all requests logged before 17 October 2026, 14:28 UTC), almost all Claude Opus 5.5, from day-to-day
agentic work. Each request is priced from its recorded usage at its model's list rates: Opus 5.5 at $4 input and $20
output per million tokens, cache reads at 0.05x input, 5-minute cache writes at 1.25x and 1-hour writes at 2x.

| Share of the bill | |
|---|---|
| Cache reads (the conversation re-read every turn) | 60.9% |
| Cache writes | 30.1% |
| Output, including thinking | 9.0% |
| Uncached input | 0.0% |

The ceiling for any tool-output compressor, assuming the same turns:
- If the output of Bash, PowerShell, Grep, Glob, WebFetch, WebSearch and Monitor cost **nothing at all**, the bill
  would be **13.4%** lower.
- If every tool's output cost nothing, file reads included, it would be **18.7%** lower.
- 0.11.1's compression (JSON left alone), replayed over the same sessions, removes **4.1%** of the bill. This replay
  can't show extra turns, which would lower these numbers.

By the request's prompt size, 49.8% of the bill came from requests of 400k tokens or more, and re-reading context
beyond 150k tokens was 33.3% of it (41.6% beyond 100k, 26.8% beyond 200k).

## Measurement 2 protocol (written before the runs)

- **Proxy:** the fixed `wrap` from commit `52a612858301`, installed from git; otherwise default options. Plain Claude
  Code as the control.
- **Tasks** (`tasks.py`):
  - `one-bug`, `three-bugs` and `five-bugs`: fix failing tests, running `pytest -v` after each fix;
  - `ci-log`: a failing simulated CI run, about 12 KB of log, whose cause sits in the middle;
  - `json-issues`: 90 issues as JSON, about 27 KB, where the refund reports are mentioned only in issue bodies;
  - `lint-fix`: 3 errors among about 260 warnings;
  - `rename`: rename a function across 20 files;
  - `explore`: write notes on a package, almost only file reads, which the proxy never changes.

  Each task has a check that runs after the agent finishes. An untouched fixture fails it and a reference fix
  passes it; we verified both for all eight before the runs.
- **Runs:** 10 per arm per task, 160 in total, with arms alternating within each task. Four tasks run in parallel.
- **Primary result:** the pooled change in mean billed cost. That is the mean over tasks of (llmslim mean / plain
  mean - 1), with a 95% bootstrap interval that resamples runs within each task.
- **Decision rule, fixed now:**
  - we call the saving **significant** only if the pooled saving is at least 10% and its interval excludes zero, with
    no task's success rate lower by more than one run;
  - we would call it **worth paying for** only at 20% or more.
- **Reporting:** every run is reported, as in measurement 1.

## Measurement 2 result, and why it can't be claimed

Measurement 2 ran 160 runs, all passing their checks. The pooled change was **-22.2%** (95% interval -24.5% to -19.6%),
but two tasks gave it away:
- `rename`: -70%;
- `explore`: -18%.

The proxy shortened **nothing** in either task, so the difference had to come from somewhere else. It did. Claude
Code recorded `permissionMode: "default"` in every plain run and `"auto"` in every llmslim run, and so did measurement
1. We checked the cause with one-line requests, all with Claude Code 2.1.296 and a clean environment:

| Setup | Permission mode |
|---|---|
| Plain `claude` | default |
| `ANTHROPIC_BASE_URL=https://api.anthropic.com` | default |
| `ANTHROPIC_BASE_URL` pointing at a standalone `llmslim proxy` | auto |
| `llmslim wrap claude` | auto |

The proxy forwarded the single `/v1/messages` request and nothing else. So Claude Code chooses a different default
permission mode when its base URL is a local proxy.

In auto mode, commands outside the allow-list were approved by Claude Code's classifier. In `rename`, the agent did the
whole rename with one `grep -rl ... | xargs sed -i` in 4 turns. In plain mode the same command was refused, so it made
20 separate edits in about 48 turns. Two things follow:
- The -22.2% mixes compression with a change in what the agent is allowed to do. It is not a result for the proxy.
- `llmslim wrap claude` changes the user's permission mode. That has to be fixed or clearly disclosed before any
  release.

## Measurement 3 protocol (amendment, written before the runs)

The same as measurement 2, except that both arms get the same `--permission-mode`, which `run.py` records per run:
- **3a**, `--permission-mode default` in both arms. This is the primary result, and the measurement 2 decision rule
  applies to it.
- **3b**, `--permission-mode auto` in both arms. A robustness check, reported next to 3a.

There are 160 runs each, with 3a and 3b running at the same time with four workers each. Every run is reported.

## Measurement 3 results

Every run recorded the permission mode it was given (`default` 160/160 in 3a, `auto` 160/160 in 3b).

| Task | 3a: default mode | 3b: auto mode |
|---|---|---|
| ci-log | **-32.4%** (-$0.0023 to -$0.0017) | **-25.6%** (-$0.0013 to -$0.0009) |
| lint-fix | **-20.6%** (-$0.0017 to -$0.0006) | **-17.0%** (-$0.0012 to -$0.0005) |
| three-bugs | -4.2% (n.s.) | **-14.9%** |
| five-bugs | -4.8% (n.s.) | **-11.1%** |
| one-bug | -4.2% (n.s.) | -1.9% (n.s.) |
| explore (nothing compressed) | -9.4% | +10.2% |
| rename (nothing compressed) | +3.5% (n.s.) | +10.3% (n.s.) |
| json-issues | **+114.2%** | +8.8% |
| **Pooled over 8 tasks** | **+5.3%** (+1.5% to +9.4%) | **-5.1%** (-8.1% to -1.9%) |

Percentages are the change in mean billed cost with llmslim. The intervals are 95% bootstrap intervals of the
per-run difference, or of the pooled change. n.s. means the interval includes zero.

**Decision rule: not met in either measurement.** In detail:
- The proxy clearly lowers the bill when an agent reads a long log it can't usefully cut itself: the simulated CI
  run, and lint output with three errors among 240 warnings.
- On test runs the agent already pipes through `tail`, so the change is small.
- On JSON it costs more. The proxy kept every issue but cut the `body` field, and the refund reports were only in the
  bodies. Its guess of which items mattered could use nothing but the command. The agent saw it was missing data,
  re-ran the command, looked for flags, then read the raw file: 12 turns instead of 4.
- `explore` and `rename`, where the proxy changed nothing, still moved by about 10%. Differences of that size on a
  single task can't be credited to compression.
- **Check failures (3 of 320 runs: plain 159/160, llmslim 158/160):**
  - `explore` once wrote NOTES.md inside `billing/` (3a, llmslim);
  - two `rename` runs (one per arm in 3b) renamed `calc_total` whole-word, so `test_calc_total` kept its name and the
    check's substring test failed;
  - none involved compressed output.

## Measurement 4 protocol: the 0.11.1 release candidate (written before the runs)

Measurement 4 checks that the three 0.11.1 fixes work as users run them, before release:
- tool search stays on;
- print-mode runs keep the default permission mode;
- JSON is left alone.

- **Build:** a wheel built from the release commit and installed in a clean virtual environment.
- **Permission mode:** **not** pinned. Both arms run as users would, so `wrap`'s own handling is what gets tested.
- **Tasks:** `json-issues` and `ci-log` (the regression and the win from measurement 3), plus `one-bug`. 10 runs per
  arm per task, alternating.
- **Release only if all of these hold:**
  1. every llmslim run records `permissionMode: "default"`, as every plain run does;
  2. `json-issues`: the 95% interval of the cost difference includes zero or favours llmslim;
  3. `ci-log`: the saving's 95% interval excludes zero;
  4. llmslim passes at least as many checks as plain, less one run per task.

Otherwise nothing is released, and the result is reported as is.

## Measurement 4 results: release conditions met

| Task | Change in mean billed cost with llmslim 0.11.1 | Passed (plain / llmslim) |
|---|---|---|
| ci-log | **-29.7%** (-$0.0023 to -$0.0012 per run) | 10/10 / 10/10 |
| json-issues | +0.9% (-$0.0003 to +$0.0004; JSON left alone, 4 turns in both arms) | 10/10 / 10/10 |
| one-bug | -8.0% (-$0.0007 to +$0.0001, n.s.) | 10/10 / 10/10 |

All four conditions held:
1. every llmslim run recorded `permissionMode: "default"` with no pinning (30/30), as every plain run did;
2. json-issues shows no regression;
3. ci-log still saves, with an interval that excludes zero;
4. pass rates are equal.

These three tasks were chosen to test the fixes, so their pooled number is not a summary of the proxy. Measurement 3
is.

## Corrections (18 October 2026)

A claim-by-claim check of the published figures against the raw runs found these errors. The pre-registered protocol
text above is left as it was written; the results sections are corrected in place.

- **Lint task:** the fixture prints exactly 240 warnings (24 files with 10 long lines each), not "about 260".
- **JSON task:** the fixture holds 90 issues, but the command the agent runs (`python issues.py list --json`) returns
  only the 74 open ones, about 27 KB. The proxy shortened that 74-issue list.
- **Real-session replay:**
  - It priced Claude Opus 5.5 cache reads at 0.1x input; Opus 5.5 reads cache at 0.05x.
  - With each model's own rates: cache reads 60.9% of the bill (not 75.6%), cache writes 30.1% (not 18.7%), output
    9.0% (not 5.6%).
  - Ceilings: 13.4% for compressible tools (not 13.8%), 18.7% for all tools (not 19.2%).
  - Re-reading beyond 150k: 33.3% (not 41.4%).
  - The proxy's replayed saving with 0.11.1's defaults is 4.1%. The earlier 4.3% used 0.11.0's JSON compression and
    the old rate.
  - "444 sessions" counted every transcript: 32 sessions plus the 412 subagent runs they started.
- **Ranges across permission modes:** the first summaries quoted ranges such as "-5% to +5%" that joined the
  primary result (default mode) with the robustness check (auto mode). Summaries now give the primary result
  first: pooled +5.3% in default mode, -5.1% in auto mode.
- **Environment:** every run inherited `DISABLE_MICROCOMPACT=1` from the shell that launched the harness, in both arms.
  Microcompaction only acts near the context limit, and these sessions stayed under about 40k tokens, so no result
  depends on it. A probe confirmed the runs used Claude Code's default effort (medium), although the shell also set
  `CLAUDE_EFFORT=xhigh`.

