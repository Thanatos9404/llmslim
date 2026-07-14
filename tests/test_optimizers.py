"""Tests for llmslim.optimizers — structure-aware compression for JSON, YAML, Markdown, and XML."""

from __future__ import annotations

import json

from llmslim import compress
from llmslim.analysis import ContentType
from llmslim.optimizers import (
    optimize_json,
    optimize_markdown,
    optimize_structured,
    optimize_xml,
    optimize_yaml,
)

JSON_TEST_DATA = """{
    "users": [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "user"},
        {"id": 3, "name": "Charlie", "role": "user"},
        {"id": 4, "name": "David", "role": "user"},
        {"id": 5, "name": "Eve", "role": "guest"}
    ],
    "metadata": {
        "status": "active",
        "count": 5
    }
}"""

YAML_TEST_DATA = """
# App Deployment configuration
apiVersion: apps/v1
kind: Deployment # inline comment
metadata:
  name: test-app
spec:
  replicas: 5
  template:
    spec:
      containers:
        - name: app
          image: nginx:latest
"""

MARKDOWN_TEST_DATA = """
# System Overview

This is the main introduction section.
It describes the overall system architecture.

## Code Example

```python
def main():
    print("Hello World")
```

## Details

Paragraph one of details.
Paragraph two of details.
Paragraph three of details.
"""

XML_TEST_DATA = """<root>
    <items>
        <item id="1">First</item>
        <item id="2">Second</item>
        <item id="3">Third</item>
        <item id="4">Fourth</item>
        <item id="5">Fifth</item>
    </items>
</root>"""


class TestJSONOptimizer:
    def test_compacts_json_validity(self):
        res = optimize_json(JSON_TEST_DATA, target_ratio=0.5)
        assert res is not None
        # Must be valid JSON
        parsed = json.loads(res)
        assert "users" in parsed
        assert len(parsed["users"]) <= 5

    def test_invalid_json_returns_none(self):
        assert optimize_json("{invalid json") is None


class TestYAMLOptimizer:
    def test_strips_comments_and_whitespace(self):
        res = optimize_yaml(YAML_TEST_DATA, target_ratio=0.5)
        assert res is not None
        assert "# App Deployment configuration" not in res
        assert "apiVersion: apps/v1" in res


class TestMarkdownOptimizer:
    def test_preserves_code_blocks_and_headings(self):
        res = optimize_markdown(MARKDOWN_TEST_DATA, target_ratio=0.5)
        assert res is not None
        assert "# System Overview" in res
        assert "```python" in res
        assert 'print("Hello World")' in res


class TestXMLOptimizer:
    def test_prunes_elements_valid_xml(self):
        res = optimize_xml(XML_TEST_DATA, target_ratio=0.5)
        assert res is not None
        assert "<root>" in res
        assert "<items>" in res

    def test_invalid_xml_returns_none(self):
        assert optimize_xml("<root><unclosed></root>") is None


class TestStructuredDispatch:
    def test_dispatch_json(self):
        res = optimize_structured(JSON_TEST_DATA, ContentType.JSON, 0.5)
        assert res is not None
        assert json.loads(res)

    def test_dispatch_unsupported(self):
        assert optimize_structured("hello", ContentType.GENERAL_TEXT, 0.5) is None


class TestCompressIntegrationWithStructured:
    def test_compress_json_detect_content(self):
        res = compress(JSON_TEST_DATA, target_ratio=0.5, detect_content=True)
        assert res.content_type == ContentType.JSON
        assert res.structure_preserved is True
        # Output is valid JSON
        assert json.loads(res.compressed_text)
