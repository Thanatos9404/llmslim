# Official Open Source Release Checklist (`RELEASE_CHECKLIST.md`)

This checklist outlines the mandatory verification steps required before publishing a new minor or major release of `llmslim` to PyPI and GitHub.

---

## Pre-Release Audit & Verification

### 1. Repository Health & Working Tree
- [ ] Working tree is clean (`git status` shows no uncommitted files or stray artifacts).
- [ ] No temporary files or test scratch files are tracked in version control.
- [ ] Dependencies in `pyproject.toml` are pinned with minimum version bounds.

### 2. Code Quality & Static Analysis
- [ ] `ruff check .` passes with 0 warnings or errors.
- [ ] `black --check .` passes cleanly across all modules and tests.
- [ ] `mypy llmslim` passes cleanly with 0 type errors.
- [ ] `py.typed` marker file is present in `llmslim/`.

### 3. Automated Test Suite & Coverage
- [ ] `pytest` passes 100% of unit tests across Python 3.10, 3.11, 3.12, 3.13.
- [ ] Code coverage threshold is **>= 90%** (`pytest --cov-fail-under=90`).
- [ ] Edge cases (empty strings, single sentences, massive prompts, unicode/multilingual) pass without exceptions.

### 4. Benchmark Quality & Performance Validation
- [ ] `python benchmarks/benchmark_regression.py` passes without performance or accuracy degradation.
- [ ] Latency remains < 50ms for typical 2K token chat prompts.
- [ ] Imperative instruction preservation remains at **100%**.
- [ ] Benchmark graphs updated if metrics changed (`python assets/generate_benchmark_charts.py`).

### 5. Open Source Documentation & Metadata
- [ ] `CHANGELOG.md` updated with release version, release date, and detailed list of changes under `[X.Y.Z]`.
- [ ] `README.md` version tags, status badges, and code examples match the target release.
- [ ] `CITATION.cff` version and `date-released` fields are synchronized.
- [ ] `SECURITY.md` supported versions table is updated.

---

## Release Execution Phase

### 6. Version Bump & Distribution Build
- [ ] Bump version in `pyproject.toml` (`version = "X.Y.Z"`).
- [ ] Bump version in `llmslim/__init__.py` (`__version__ = "X.Y.Z"`).
- [ ] Regenerate the API reference pages, which name the version: `python scripts/api_reference.py --write`.
  `tests/test_api_reference.py` checks them.
- [ ] Bump `version` in `server.json` (both places, and the `llmslim[mcp]==X.Y.Z` pin) and in
  `plugins/llmslim/.claude-plugin/plugin.json`. `tests/test_claude_plugin.py` checks they match.
- [ ] Bump the `llmslim[mcp]==X.Y.Z` pin in `plugins/llmslim/.mcp.json` and `plugins/llmslim/README.md`, `version`
  and the pin in `gemini-extension.json`, and the five one-click install links in the README's MCP section (Cursor
  and LM Studio carry the config base64-encoded). Directories reject a version range, so these stay exact.
  `tests/test_claude_plugin.py` checks them too.
- [ ] Bump `version` in the Codex manifest, `plugins/llmslim/.codex-plugin/plugin.json`. It starts the server from
  `plugins/llmslim/.mcp.json`, so its pin moves with the one above. `tests/test_claude_plugin.py` checks both.
- [ ] Bump `version` in `plugins/llmslim/plugin.json` and the pin in `plugins/llmslim/mcp.json` (the Agent Plugins
  files Copilot CLI reads). awesome-copilot pins a commit, so resubmit its external plugin entry after a release.
- [ ] Bump the VS Code extension's pin, `LLMSLIM_VERSION` in `plugins/vscode/src/command.ts`, and the pin in
  `plugins/vscode/README.md`; bump the extension's own `version` in `plugins/vscode/package.json` and add a
  `plugins/vscode/CHANGELOG.md` entry. `tests/test_claude_plugin.py` checks the pin. Once the extension is listed,
  publish the new version from `plugins/vscode` with `npx vsce publish` and `npx ovsx publish`.
- [ ] Bump the `llmslim[proxy]==X.Y.Z` pin in the uvx fallbacks of `plugins/llmslim/skills/*/SKILL.md`. `tests/test_claude_plugin.py` checks them.
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
- [ ] Commit version bump:
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

### 8. PyPI Publication
- [ ] GitHub Action `release.yml` triggers automatically on tag push or release publish.
- [ ] Monitor PyPI workflow execution to confirm sdist & wheel upload to PyPI.
- [ ] Check the GitHub release has the wheel, the sdist and `llmslim-X.Y.Z.cdx.json`, and that the attestations
  verify (see "Verifying a release" in `SECURITY.md`):
  ```bash
  gh attestation verify llmslim-X.Y.Z-py3-none-any.whl --repo Thanatos9404/llmslim     --signer-workflow Thanatos9404/llmslim/.github/workflows/release.yml
  pypi-attestations verify pypi --repository https://github.com/Thanatos9404/llmslim pypi:llmslim-X.Y.Z-py3-none-any.whl
  ```
- [ ] Verify clean installation from PyPI in an isolated environment:
  ```bash
  pip install --no-cache-dir llmslim==X.Y.Z
  python -c "import llmslim; print(llmslim.__version__)"
  ```

---

## Post-Release Phase

### 9. Post-Release Communication
- [ ] Update GitHub Discussions / Release Announcement thread.
- [ ] Share benchmarks and updates with the open-source NLP / RAG community.

### 10. Prepare Next Cycle
- [ ] Add `[Unreleased]` header at top of `CHANGELOG.md` for upcoming development.
