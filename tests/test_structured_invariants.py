"""Property-based invariant assertions for structure-aware optimizers."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest

from llmslim.optimizers import optimize_json, optimize_markdown, optimize_xml


class TestStructuredInvariants:
    @pytest.mark.parametrize("target_ratio", [0.2, 0.4, 0.6, 0.8, 1.0])
    def test_json_validity_invariant(self, target_ratio):
        sample_json = json.dumps({
            "items": list(range(20)),
            "nested": {"a": 1, "b": 2, "c": list(range(10))},
            "status": "ok"
        }, indent=4)

        compressed = optimize_json(sample_json, target_ratio=target_ratio)
        assert compressed is not None
        # Invariant: output must always be parseable by json.loads
        parsed = json.loads(compressed)
        assert "items" in parsed
        assert "nested" in parsed

    @pytest.mark.parametrize("target_ratio", [0.2, 0.5, 0.8])
    def test_xml_validity_invariant(self, target_ratio):
        sample_xml = (
            "<root>"
            + "".join(f"<child id='{i}'>Text {i}</child>" for i in range(15))
            + "</root>"
        )

        compressed = optimize_xml(sample_xml, target_ratio=target_ratio)
        assert compressed is not None
        # Invariant: output must always be parseable by ET.fromstring
        root = ET.fromstring(compressed)
        assert root.tag == "root"

    @pytest.mark.parametrize("target_ratio", [0.2, 0.5, 0.8])
    def test_markdown_code_block_verbatim_invariant(self, target_ratio):
        code_content = "def sample_function():\n    return 42\n"
        sample_md = f"# Title\n\nSome intro text.\n\n```python\n{code_content}```\n\nMore prose here."

        compressed = optimize_markdown(sample_md, target_ratio=target_ratio)
        assert compressed is not None
        # Invariant: code block content inside ```...``` must be preserved verbatim
        assert code_content in compressed
        assert "# Title" in compressed
