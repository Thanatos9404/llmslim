# Official Open Source Release Checklist (`RELEASE_CHECKLIST.md`)

This checklist outlines the mandatory verification steps required before publishing a new release of `llmslim` to
PyPI and GitHub.

- **A final release** (`X.Y.Z`) is bumped, tagged and released from `main`: sections 1 to 10.
- **A release candidate** (`X.Y.ZrcN`, such as `1.0.0rc1`) is bumped and tagged on a release branch, and most of the
  publishing is skipped: see [Release candidates](#release-candidates) before you start.
- **The website** (llmslim.app) lives in its own private repository, `Thanatos9404/llmslim-web`. Nothing in this
  repository builds or deploys it; it copies what it needs from Core with `npm run sync:core` (section 10).

---

## Pre-Release Audit & Verification

### 1. Repository Health & Working Tree
- [ ] Working tree is clean (`git status` shows no uncommitted files or stray artifacts).
- [ ] No temporary files or test scratch files are tracked in version control.
- [ ] Dependencies in `pyproject.toml` are pinned with minimum version bounds.
- [ ] The pull requests planned for this release are merged, and CI is green on the commit you release.

### 2. Code Quality & Static Analysis
- [ ] `ruff check .` passes with 0 warnings or errors.
- [ ] `ruff format --check .` passes cleanly across all modules and tests.
- [ ] `mypy llmslim` passes cleanly with 0 type errors.
- [ ] `py.typed` marker file is present in `llmslim/`.

### 3. Automated Test Suite & Coverage
- [ ] `pytest` passes 100% of unit tests across Python 3.10, 3.11, 3.12, 3.13 and 3.14 on Ubuntu, and 3.12 on Windows
  and macOS (the `test` matrix in `.github/workflows/ci.yml`).
- [ ] Code coverage threshold is **>= 90%** (`pytest --cov-fail-under=90`).
- [ ] Edge cases (empty strings, single sentences, massive prompts, unicode/multilingual) pass without exceptions.
- [ ] The public API matches its snapshot (`tests/test_public_api.py`). After an intended change, regenerate it with
  `python scripts/public_api.py --write` and say what changed in the CHANGELOG.

### 4. Benchmark Quality & Performance Validation
- [ ] `python -m benchmarks.benchmark_regression` passes without performance or accuracy degradation.
- [ ] `python -m benchmarks.run --mode fast --no-archive` (the offline benchmark smoke test) passes. It overwrites
  the committed `benchmarks/results/latest.json`, `benchmarks/results/summary.json` and `benchmarks/reports/latest.md`
  with its smoke-test output, so restore them before you commit: `git restore benchmarks/results benchmarks/reports`.
- [ ] Latency remains < 50ms for typical 2K token chat prompts.
- [ ] Imperative instruction preservation remains at **100%**.
- [ ] Benchmark graphs updated if metrics changed (`python assets/generate_benchmark_charts.py`).

### 5. Open Source Documentation & Metadata
- [ ] `CHANGELOG.md` updated with release version, release date, and detailed list of changes under `[X.Y.Z]`.
- [ ] `README.md` version tags, status badges, and code examples match the target release.
- [ ] `CITATION.cff` version and `date-released` fields are synchronized.
- [ ] `SECURITY.md`: the supported versions table, and the dated `pip-audit` note under "Python 3.10". Its
  verification examples name files as `llmslim-<version>-py3-none-any.whl`; keep them that way, with no release in
  the file name.
- [ ] `docs/MIGRATE_FROM_MEM0.md` says which release its outputs come from ("llmslim 0.12.0 from PyPI", "Main reports
  its version as 0.12.0", the "(0.12.0)" headings and "the same on 0.12.0 and on main"). Update those sentences for
  the new release, and rerun the guide's commands if output changed.

---

## Release Execution Phase

### 6. Version Bump & Distribution Build
Every file below names the release. Where a test is named, it checks the pin equals `llmslim.__version__`, so a
missed file fails CI.

- [ ] Bump version in `pyproject.toml` (`version = "X.Y.Z"`).
- [ ] Bump version in `llmslim/__init__.py` (`__version__ = "X.Y.Z"`).
- [ ] Bump the expected version in `tests/test_dx.py`.
- [ ] Bump `version` and `date-released` in `CITATION.cff`.
- [ ] Turn `## [Unreleased]` in `CHANGELOG.md` into `## [X.Y.Z] - YYYY-MM-DD`. The API reference needs that dated
  heading, and an `[Unreleased]` section with entries would make it describe "the main branch" instead of the release.
- [ ] Regenerate the API reference, which names the version: `python scripts/api_reference.py --write`.
  `tests/test_api_reference.py` checks `docs/reference/api-reference.json`.
- [ ] Bump `version` in `server.json` (both places, and the `llmslim[mcp]==X.Y.Z` pin) and in
  `plugins/llmslim/.claude-plugin/plugin.json`. `tests/test_claude_plugin.py` checks they match.
- [ ] Bump the `llmslim[mcp]==X.Y.Z` pin in `plugins/llmslim/.mcp.json` and `plugins/llmslim/README.md`, and `version`
  and the pin in `gemini-extension.json`. Directories reject a version range, so these stay exact.
  `tests/test_claude_plugin.py` checks them too.
- [ ] Bump all **10** one-click install links in `README.md`: five near the top ("One click") and five in the MCP
  section ("One-click install"), each for VS Code, Cursor, LM Studio, Goose and Kiro. Cursor and LM Studio carry the
  config base64-encoded, so re-encode it; the others are URL-encoded. Also bump the version in the sentence above the
  second set ("Each link runs ..."). `tests/test_claude_plugin.py` decodes every link and checks the command.
- [ ] Bump `version` in the Codex manifest, `plugins/llmslim/.codex-plugin/plugin.json`. It starts the server from
  `plugins/llmslim/.mcp.json`, so its pin moves with the one above. `tests/test_claude_plugin.py` checks both.
- [ ] Bump `version` in `plugins/llmslim/plugin.json` and the pin in `plugins/llmslim/mcp.json` (the Agent Plugins
  files Copilot CLI reads).
- [ ] Bump the VS Code extension's pin, `LLMSLIM_VERSION` in `plugins/vscode/src/command.ts`, and the pin in
  `plugins/vscode/README.md`. `tests/test_claude_plugin.py` checks the pin. For a final release, also bump the
  extension's own `version` in `plugins/vscode/package.json` and add a `plugins/vscode/CHANGELOG.md` entry.
- [ ] Bump the `llmslim[proxy]==X.Y.Z` pin in the uvx fallbacks of `plugins/llmslim/skills/*/SKILL.md`. `tests/test_claude_plugin.py` checks them.
- [ ] For a final release, bump the Hermes Agent plugin, which no test checks: `version` and the `llmslim==X.Y.Z`
  dependency in `plugins/hermes/plugin.yaml`, both pins in `plugins/hermes/README.md`, and the pin in
  `docs/integrations/HERMES.md`.
- [ ] Clean previous builds: `rm -rf dist/ build/ *.egg-info`.
- [ ] Build source distribution and binary wheel:
  ```bash
  python -m build
  ```
- [ ] Validate distribution artifacts:
  ```bash
  twine check dist/*
  ```
- [ ] Inspect wheel and tarball file lists (`unzip -l dist/*.whl`) to ensure no tests or scratch files are packaged.

### 7. Tag Creation & GitHub Release
- [ ] Commit version bump. First check `git status` lists only the files bumped in section 6 (restore the benchmark
  outputs, see section 4):
  ```bash
  git commit -am "chore(release): prepare release vX.Y.Z"
  ```
- [ ] Create signed git tag:
  ```bash
  git tag -a vX.Y.Z -m "Release vX.Y.Z"
  git push origin main --tags
  ```
- [ ] Draft GitHub Release targeting tag `vX.Y.Z`:
  - Copy notes from `CHANGELOG.md`.
  - Attach nothing by hand: the release workflow attaches the wheel, the sdist and `llmslim-X.Y.Z.cdx.json` (the
    SBOM) that it built and attested.
  - `release.yml` refuses to publish unless the tag is exactly `"v" + version`.

### 8. PyPI Publication
- [ ] GitHub Action `release.yml` triggers automatically when the release is published.
- [ ] Monitor PyPI workflow execution to confirm sdist & wheel upload to PyPI.
- [ ] Check the GitHub release has the wheel, the sdist and `llmslim-X.Y.Z.cdx.json`, and that the attestations
  verify (see "Verifying a release" in `SECURITY.md`):
  ```bash
  gh attestation verify llmslim-X.Y.Z-py3-none-any.whl --repo Thanatos9404/llmslim \
    --signer-workflow Thanatos9404/llmslim/.github/workflows/release.yml
  pypi-attestations verify pypi --repository https://github.com/Thanatos9404/llmslim pypi:llmslim-X.Y.Z-py3-none-any.whl
  ```
- [ ] Verify clean installation from PyPI in an isolated environment:
  ```bash
  pip install --no-cache-dir llmslim==X.Y.Z
  python -c "import llmslim; print(llmslim.__version__)"
  ```

### 9. Directories and catalogs (final releases only)
These happen outside this repository, after the release is on PyPI. None of them is done for a release candidate.

- [ ] **MCP Registry.** Publish `server.json` with `mcp-publisher`: the founder runs the GitHub device login
  (`mcp-publisher login github`), then `mcp-publisher publish` from the repository root. The registry name is
  `io.github.Thanatos9404/llmslim`, with that casing. Check the README's MCP Registry badge finds the new version.
- [ ] **Hermes Agent plugin catalog.** `hermes plugins install llmslim` installs the commit reviewed for the catalog,
  so open a pull request to `NousResearch/hermes-agent` that re-pins the llmslim entry to the release commit.
- [ ] **awesome-copilot.** Its external plugin entry pins a commit: resubmit it with the release commit.
- [ ] **VS Code Marketplace and Open VSX.** Run the `vscode-publish.yml` workflow by hand (or `npx vsce publish` and
  `npx ovsx publish` from `plugins/vscode`) for the extension version bumped in section 6.
- [ ] **Glama.** Create the release on the server's Glama page, so its score covers the new version.

---

## Post-Release Phase

### 10. The website, communication and the next cycle
- [ ] **Website** (in `llmslim-web`, after the release is on PyPI): run `npm run sync:core` and commit the result
  (each release tag from 1.0 on carries its own `docs/reference/api-reference.json`; that repository's README says
  how to keep a release's reference beside main's). Bump the Core pin in its `requirements.txt` and the Studio test
  that pins it, and `DEFAULT_DOCS_VERSION` when a new docs version becomes the default.
- [ ] Update GitHub Discussions / Release Announcement thread.
- [ ] Share benchmarks and updates with the open-source NLP / RAG community.
- [ ] Add `[Unreleased]` header at top of `CHANGELOG.md` for upcoming development.

---

## Release candidates

A release candidate is published to PyPI as a pre-release, so `pip install llmslim` keeps installing the last final
release and only `pip install "llmslim==1.0.0rc1"` (or `--pre`) gets the candidate. It must not reach anyone who
installs from this repository's default branch: Claude Code, Codex and Gemini CLI install the plugin and the extension
from `main` (`.claude-plugin/marketplace.json` points at `./plugins/llmslim`, and `gemini-extension.json` is at the
root), and `tests/test_claude_plugin.py` makes every pin equal `llmslim.__version__`. So the candidate is bumped and
tagged on a release branch, and **`main` and every plugin pin stay on the last final release** (0.12.0 until 1.0.0).

### Cut the candidate on a release branch
- [ ] Merge everything planned for the candidate into `main`, and check CI is green there.
- [ ] Create the branch from that commit:
  ```bash
  git fetch origin
  git switch -c release/1.0.0rc1 origin/main
  ```
- [ ] On the branch, make the section 6 bumps with `1.0.0rc1` (PEP 440 spelling: no dash, no dot before `rc`):
  - `pyproject.toml`, `llmslim/__init__.py`, `tests/test_dx.py` and `CITATION.cff` (version and date);
  - `CHANGELOG.md`: `## [Unreleased]` becomes `## [1.0.0rc1] - YYYY-MM-DD`, then regenerate the API reference
    (`python scripts/api_reference.py --write`);
  - `server.json` (bumped so the tests pass; it is not published);
  - the three plugin manifests (`plugins/llmslim/.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`,
    `plugin.json`), the `llmslim[mcp]` pins in `plugins/llmslim/.mcp.json`, `mcp.json` and `README.md`,
    `gemini-extension.json`, and the `llmslim[proxy]` pins in `plugins/llmslim/skills/*/SKILL.md`;
  - the VS Code pin in `plugins/vscode/src/command.ts` and `plugins/vscode/README.md` (the extension is not
    published);
  - all 10 README one-click links, re-encoding the base64 ones for Cursor and LM Studio.
- [ ] On the branch, leave alone: the classifier (it stays `Development Status :: 4 - Beta` until 1.0.0), the Hermes
  files, `plugins/vscode/package.json` and its CHANGELOG, the README's prose version mentions and badges,
  `docs/MIGRATE_FROM_MEM0.md` and the `SECURITY.md` table. Those change with the final release.
- [ ] Run sections 2 to 4 on the branch, push it, and check CI: `ci.yml` runs on pushes to `release/**` as well as
  `main`. Section 4 rewrites the committed benchmark results, so restore them and check `git status` lists only the
  bumped files (and `docs/reference/api-reference.json`) before you commit:
  ```bash
  git restore benchmarks/results benchmarks/reports
  git status --short
  git commit -am "chore(release): prepare release v1.0.0rc1"
  git push -u origin release/1.0.0rc1
  ```

### Tag and publish the candidate
- [ ] Tag the branch's head and publish a GitHub **pre-release** from it. Publishing it runs `release.yml`, which
  checks the tag is `"v" + version`, builds, attests and uploads to PyPI:
  ```bash
  git tag -a v1.0.0rc1 -m "Release v1.0.0rc1"
  git push origin v1.0.0rc1
  gh release create v1.0.0rc1 --verify-tag --prerelease --latest=false \
    --title "LLMSlim 1.0.0rc1" --notes-file <notes.md>
  ```
  The notes say it is a release candidate, how to install it (`pip install "llmslim==1.0.0rc1"`), that only fixes go
  in until the final release, and its known limitations; link `docs/UPGRADING.md`.
- [ ] Check section 8 with `1.0.0rc1`, and also that a plain `pip install llmslim` in a clean environment still
  installs the last final release.
- [ ] Once it is on PyPI, open a pull request to `main` for the two sentences that say the candidate is not out yet:
  "These commands work once 1.0.0rc1 is on PyPI. Until then, ..." under "Try the release candidate" in
  `docs/UPGRADING.md`, and "(`pip install "llmslim==1.0.0rc1"` once it is out)" in the README's Changelog section.
  Only those sentences change; `main`'s version, pins and links stay.

### What is NOT published for a release candidate
- [ ] No **MCP Registry** entry: a published candidate could become the registry's latest version, and `1.0.0rc1` is
  a PEP 440 version, not semver. The branch's `server.json` stays unpublished.
- [ ] No **VS Code Marketplace** or **Open VSX** release (don't run `vscode-publish.yml`).
- [ ] No **Hermes catalog** re-pin and no **awesome-copilot** resubmission: both pin a commit for every user.
- [ ] No **npm** release of `clients/typescript`, and no **Glama** release.
- [ ] No change to `main`'s version, pins or links (only the two sentences above), and no **website** change: its
  `requirements.txt` and `DEFAULT_DOCS_VERSION` stay on the final release, and `npm run sync:core` keeps following
  `main`.

### Fixes while the candidate is out
- [ ] Every fix lands on `main` first, by pull request, as usual.
- [ ] If another candidate is needed, cherry-pick the fixes from `main` onto the release branch (or cut a fresh
  `release/1.0.0rc2` from `main` and repeat the bumps), then tag and publish `v1.0.0rc2` the same way.
- [ ] Never commit a fix to the release branch only.

### After the final release: bringing the branch back
The release branch is never merged into `main`: its own commits are the candidate's version bumps, which the final
release replaces, and merging them would put `rc` pins on `main`.

- [ ] Before the final bump, list what the branch has that `main` doesn't:
  ```bash
  git fetch origin
  git log --oneline origin/main..origin/release/1.0.0rc1
  ```
  Only the `chore(release)` bump commits may remain. Cherry-pick anything else onto `main` by pull request first.
- [ ] Release `1.0.0` from `main` with sections 1 to 10, including the [1.0.0 extras](#100-extras) below. In
  `CHANGELOG.md`, `## [1.0.0] - YYYY-MM-DD` covers everything since 0.12.0 and says that 1.0.0rc1 was its release
  candidate.
- [ ] Once `v1.0.0` is out, delete the branch (`git push origin --delete release/1.0.0rc1`). The `v1.0.0rc1` tag keeps
  the candidate's commit.

### 1.0.0 extras
On top of section 6, the 1.0.0 release PR changes these:

- [ ] `pyproject.toml`: the classifier becomes `Development Status :: 5 - Production/Stable`.
- [ ] `docs/integrations/HERMES.md`: besides its `llmslim==` pin, the example dependency `"llmslim>=0.10.0,<1"` becomes
  `"llmslim>=1.0,<2"`, so the documented range admits 1.x (the same example is in the website's
  `src/data/integrations.ts`).
- [ ] `README.md`: the Core version line and the version row near the top, the tests and coverage badges (update them
  or remove them), the Changelog section's "including 0.12.0" and its note on trying the release candidate.
- [ ] Text that speaks of 1.0 as coming: the intro of `docs/API_STABILITY.md`, the HTTP transport's version note in
  `docs/MCP.md`, "Try the release candidate" in `docs/UPGRADING.md`, and the status lines of `docs/roadmap/1.0.md`.
- [ ] `SECURITY.md`: the supported versions table (1.x supported, 0.12.x not) and its "Until 1.0.0 is released"
  sentences.
- [ ] `clients/typescript`: release npm 0.3.0 if its `explain` support should ship with 1.0.
- [ ] Leave history alone: past CHANGELOG entries, `docs/releases/` and the README's dated benchmark notes.
