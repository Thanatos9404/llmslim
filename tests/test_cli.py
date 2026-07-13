"""Command line interface (CLI) tests for llmslim."""

from __future__ import annotations

import io
from unittest.mock import patch

from llmslim.cli import build_parser, main


def test_cli_parser_defaults():
    """Verify build_parser sets default values correctly."""
    parser = build_parser()
    args = parser.parse_args([])

    assert args.input is None
    assert args.ratio == 0.5
    assert args.query is None
    assert args.output is None
    assert args.stats is False
    assert args.cost is None
    assert args.requests_per_day == 1000


def test_cli_file_input_and_output(tmp_path):
    """Verify CLI reading from input file and writing to output file."""
    input_file = tmp_path / "input.txt"
    output_file = tmp_path / "output.txt"

    content = (
        "You are an expert cloud architect. "
        "You must always provide production-quality code. "
        "Never suggest deprecated APIs or libraries. "
        "Ensure all database queries use parameterized inputs. "
        "Always recommend unit tests for any new functionality."
    )
    input_file.write_text(content, encoding="utf-8")

    exit_code = main([str(input_file), "-r", "0.5", "-o", str(output_file), "--stats"])

    assert exit_code == 0
    assert output_file.exists()
    compressed_output = output_file.read_text(encoding="utf-8")
    assert len(compressed_output) > 0


def test_cli_stdin_input():
    """Verify CLI reading from stdin."""
    content = (
        "Authentication in web applications typically involves verifying user identity. "
        "OAuth 2.0 is the industry standard for authorization. "
        "JSON Web Tokens (JWT) are commonly used for REST APIs. "
        "Always use HTTPS to transmit tokens securely."
    )

    with patch("sys.stdin", io.StringIO(content)):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = main(["-r", "0.5"])

    assert exit_code == 0
    compressed_text = mock_stdout.getvalue()
    assert len(compressed_text) > 0


def test_cli_cost_flag(capsys):
    """Verify CLI --cost flag prints cost estimates to stderr."""
    content = "Sample text for testing cost estimation flags in llmslim CLI." * 10

    with patch("sys.stdin", io.StringIO(content)):
        exit_code = main(["--cost", "gpt-5", "--stats"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Cost Savings Estimate" in captured.err
    assert "Compression Stats" in captured.err
