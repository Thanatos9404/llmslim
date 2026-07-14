"""Tests for Developer Experience (DX) and CLI extensions in v0.3.0."""

from __future__ import annotations

import io
import sys
from unittest.mock import patch

import pytest

import llmslim
from llmslim.cli import main


TEST_TEXT = (
    "Machine learning is a field of computer science. "
    "It enables systems to learn from data automatically. "
    "Deep learning is a subset using multi-layer neural networks. "
    "Supervised learning trains on labeled data. "
    "Unsupervised learning finds hidden patterns in unlabeled data. "
) * 3


class TestPackageExports:
    def test_top_level_exports(self):
        assert hasattr(llmslim, "compress")
        assert hasattr(llmslim, "ContextCompressor")
        assert hasattr(llmslim, "CompressionResult")
        assert hasattr(llmslim, "ContentType")
        assert hasattr(llmslim, "ContentProfile")
        assert hasattr(llmslim, "analyze")
        assert hasattr(llmslim, "list_modes")
        assert hasattr(llmslim, "get_mode")
        assert llmslim.__version__ == "0.3.0"


class TestCLIExtensions:
    def test_cli_basic(self, tmp_path, capsys):
        inp_file = tmp_path / "input.txt"
        inp_file.write_text(TEST_TEXT, encoding="utf-8")

        res_code = main([str(inp_file), "-r", "0.5"])
        assert res_code == 0
        captured = capsys.readouterr()
        assert len(captured.out.strip()) > 0

    def test_cli_mode_and_detect(self, tmp_path, capsys):
        inp_file = tmp_path / "input.txt"
        inp_file.write_text(TEST_TEXT, encoding="utf-8")

        res_code = main([str(inp_file), "--detect", "--mode", "quality", "--stats"])
        assert res_code == 0
        captured = capsys.readouterr()
        assert "Mode" in captured.err or "Quality" in captured.err or "quality" in captured.err

    def test_cli_analyze_only(self, tmp_path, capsys):
        inp_file = tmp_path / "input.txt"
        inp_file.write_text(TEST_TEXT, encoding="utf-8")

        res_code = main([str(inp_file), "--analyze"])
        assert res_code == 0
        captured = capsys.readouterr()
        assert "Content Analysis Profile" in captured.out
        assert "Content Type" in captured.out
        assert "Confidence" in captured.out
