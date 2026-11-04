"""Command line interface (CLI) tests for llmslim."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from typing import List
from unittest.mock import patch

import pytest

from llmslim.cli import COMMANDS, build_parser, main

#: Every command ``main`` runs besides compressing text. Listed here as well as in ``COMMANDS``, so dropping one from
#: the help fails a test.
EXPECTED_COMMANDS = ["serve", "mcp", "import", "proxy", "wrap", "plan", "context", "tools"]


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


@pytest.fixture
def plain_help(monkeypatch):
    """Help as plain text, at a fixed width: Python 3.14's argparse colours help on a terminal."""
    monkeypatch.setenv("PYTHON_COLORS", "0")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("COLUMNS", "80")


def _help(capsys, arguments: List[str]) -> str:
    with pytest.raises(SystemExit) as exited:
        main(arguments)
    assert exited.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def _listed_commands(text: str) -> List[List[str]]:
    """The ``commands:`` section of the top-level help, as [name, description] rows."""
    lines = text.splitlines()
    start = lines.index("commands:") + 1
    rows = []
    for line in lines[start:]:
        if not line.strip():
            break
        name, _, description = line.strip().partition(" ")
        rows.append([name, description.strip()])
    return rows


def test_help_lists_every_command_with_a_line_each(capsys, plain_help):
    text = _help(capsys, ["--help"])
    assert text.splitlines()[:2] == [
        "usage: llmslim [options] [input]",
        "       llmslim <command> [options]",
    ]
    listed = _listed_commands(text)
    assert [name for name, _ in listed] == EXPECTED_COMMANDS
    assert [name for name, _, _ in COMMANDS] == EXPECTED_COMMANDS
    for (name, description), (_, line, _) in zip(listed, COMMANDS):
        assert description == line and description.endswith("."), name
    assert "Run 'llmslim <command> --help' for a command's options." in text
    # The compress mode's input and options are still described.
    assert "  input " in text.split("positional arguments:", 1)[1]
    for flag in ("--ratio", "--query", "--output", "--stats", "--cost"):
        assert flag in text


def test_help_fits_an_80_column_terminal(capsys, plain_help):
    text = _help(capsys, ["-h"])
    assert max(len(line) for line in text.splitlines()) <= 80


@pytest.mark.parametrize(
    "command",
    [[name] for name in EXPECTED_COMMANDS]
    + [["proxy", "stats"], ["tools", "inspect"], ["tools", "measure"]],
    ids=lambda command: " ".join(command),
)
def test_every_command_has_its_own_help(capsys, plain_help, command):
    # --help prints the command's own usage and exits 0 before it opens a store or starts a server.
    text = _help(capsys, [*command, "--help"])
    assert text.startswith(f"usage: llmslim {' '.join(command)} "), text.splitlines()[0]
    assert "options:" in text


def test_a_file_that_is_not_a_command_is_compressed(tmp_path, capsys):
    notes = tmp_path / "notes.txt"
    notes.write_text(
        "The depot reviewed routine maintenance on Monday. "
        "The backup generator failed because its fuel filter was clogged. "
        "Lunch was moved to the second floor.",
        encoding="utf-8",
    )
    assert main([str(notes), "-q", "Why did the generator fail?", "-r", "0.6"]) == 0
    assert "fuel filter" in capsys.readouterr().out


def test_the_installed_entry_point_prints_the_command_list():
    environment = {**os.environ, "PYTHON_COLORS": "0", "NO_COLOR": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "llmslim.cli", "--help"],
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert [name for name, _ in _listed_commands(result.stdout)] == EXPECTED_COMMANDS
