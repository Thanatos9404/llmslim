---
name: Bug Report
about: Create a report to help us reproduce and fix a bug in llmslim.
title: "[BUG] "
labels: ["bug", "triage"]
assignees: ""
---

### Describe the Bug
A clear and concise description of what the bug is.

### Minimal Reproducible Example
```python
from llmslim import compress

# Paste minimal snippet reproducing the bug here
text = "..."
result = compress(text)
```

### Expected Behavior
A clear description of what you expected to happen.

### Error Traceback / Logs
```text
# Paste full error stack trace here if applicable
```

### Environment Information
- **llmslim Version**: (e.g. `0.2.0`)
- **Python Version**: (e.g. `3.12.5`)
- **OS Platform**: (e.g. Ubuntu 22.04 / Windows 11 / macOS Sonoma)
- **Installed Optional Dependencies**: (e.g. `sentence-transformers`, `tiktoken`, `nltk`)

### Additional Context
Add any other context about the problem here (e.g. specific prompt domain, language, model tokens count).
