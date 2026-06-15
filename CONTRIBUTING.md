# Contributing to context-compressor

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/Thanatos9404/context-compressor.git
cd context-compressor
pip install -e ".[all,dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

- Follow PEP 8 conventions.
- Use type hints for all public function signatures.
- Write docstrings for public classes and functions (Google style).
- Keep imports sorted: stdlib → third-party → local.

## Submitting a Pull Request

1. Fork the repo and create a feature branch from `main`.
2. Add tests for any new functionality.
3. Ensure all tests pass: `pytest tests/ -v`
4. Write a clear PR description explaining the change.
5. Submit!

## Reporting Bugs

Open an issue at [github.com/Thanatos9404/context-compressor/issues](https://github.com/Thanatos9404/context-compressor/issues) with:
- A minimal code example reproducing the bug.
- Expected vs. actual behavior.
- Python version and installed extras.

## Feature Requests

Open an issue with the `enhancement` label. Describe the use case, proposed API, and why it matters.
