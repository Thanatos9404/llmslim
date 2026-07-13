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
- [ ] `pytest` passes 100% of unit tests across Python 3.9, 3.10, 3.11, 3.12, 3.13.
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
  - Attach `dist/llmslim-X.Y.Z-py3-none-any.whl` and `dist/llmslim-X.Y.Z.tar.gz`.

### 8. PyPI Publication
- [ ] GitHub Action `release.yml` triggers automatically on tag push or release publish.
- [ ] Monitor PyPI workflow execution to confirm sdist & wheel upload to PyPI.
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
