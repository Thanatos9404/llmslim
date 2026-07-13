# Contributing to llmslim

Thank you for your interest in contributing to `llmslim`! We welcome contributions from developers, researchers, and open-source enthusiasts.

---

## Code of Conduct

All contributors are expected to adhere to the project's [Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.

---

## Environment Setup

### Prerequisites
- Python 3.9, 3.10, 3.11, 3.12, or 3.13
- Git

### Initializing Virtual Environment

```bash
# Clone the repository
git clone https://github.com/Thanatos9404/llmslim.git
cd llmslim

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

# Upgrade packaging tools & install development dependencies in editable mode
pip install --upgrade pip build setuptools wheel
pip install -e ".[all,dev]"
```

---

## Code Standards & Tooling

We enforce strict formatting and typing standards to maintain codebase health.

### 1. Formatting & Linting
Run **Ruff** and **Black** before committing:
```bash
# Check and auto-fix linting issues with Ruff
ruff check --fix .

# Format code with Black
black .
```

### 2. Static Type Checking
Run **MyPy** to ensure type hints are valid:
```bash
mypy llmslim
```

### 3. Test Suite & Code Coverage
All PRs must maintain or improve the **90% code coverage** threshold:
```bash
# Run pytest with full coverage report
pytest
```

---

## Running Benchmarks

Before submitting PRs that modify compression or chunking logic, verify performance impact:

```bash
# Run regression smoke test
python benchmarks/benchmark_regression.py

# Run full performance benchmark suite
python benchmarks/benchmark.py

# Benchmark memory footprint
python benchmarks/benchmark_memory.py
```

---

## Git Workflow & Conventions

### Branch Naming Conventions
- `feature/feature-name` (e.g., `feature/onnx-embeddings`)
- `fix/bug-description` (e.g., `fix/sentence-boundary-split`)
- `docs/topic` (e.g., `docs/benchmarks-update`)
- `perf/optimization` (e.g., `perf/speedup-tfidf-matrix`)

### Commit Message Format
We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: add streaming compression support`
- `fix: correct entity regex for technical identifiers`
- `docs: update roadmap for v0.3.0`
- `test: add edge cases for empty prompt strings`
- `perf: optimize TF-IDF vectorization`
- `chore: update CI matrix`

---

## Pull Request Checklist

Before submitting a Pull Request, verify that:

- [ ] Branch is updated relative to latest `main`.
- [ ] Code follows formatting rules (`ruff check .`, `black --check .`).
- [ ] Type hints pass cleanly (`mypy llmslim`).
- [ ] Test suite passes with >=90% coverage (`pytest`).
- [ ] Benchmarks pass without performance regressions (`python benchmarks/benchmark_regression.py`).
- [ ] Docstrings follow Google style guide for all public classes/functions.
- [ ] `CHANGELOG.md` has been updated under `[Unreleased]` if applicable.

---

## Reporting Issues

### Bug Reports
Use the [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md) with:
1. Minimal reproducible Python code snippet.
2. Expected output vs actual behavior.
3. Environment context (Python version, OS, installed dependencies).

### Feature Requests
Use the [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md) describing the problem, proposed solution, and alternative designs considered.

---

## Documentation Standards

- Write clean, accurate Markdown with explicit line links where applicable.
- Ensure docstrings provide clear parameter descriptions, type annotations, return types, and code usage examples.

---

## Release Process (Maintainer Info)

Releases are published automatically via GitHub Actions:
1. Create a release tag matching `v*.*.*` (e.g. `v0.2.0`).
2. Draft a GitHub Release on the repository.
3. CI automatically validates artifacts and publishes the sdist & wheel to PyPI.
