"""Command-line interface for llmslim.

Usage:
    llmslim input.txt -r 0.5 -o compressed.txt --stats
    cat prompt.txt | llmslim --ratio 0.4 --cost gpt-5
"""

from __future__ import annotations

import argparse
import sys

from .core import compress
from .cost import estimate_cost_savings, list_supported_models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmslim",
        description="Compress text/prompts to reduce LLM token usage by 40-70%.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to an input text file. Reads from stdin if omitted.",
    )
    parser.add_argument(
        "-r",
        "--ratio",
        type=float,
        default=0.5,
        help="Target fraction of tokens to keep, e.g. 0.5 = 50%% reduction (default: 0.5).",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default=None,
        help="Optional query for relevance-aware compression (RAG use case).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write compressed text to this file instead of stdout.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print compression statistics to stderr.",
    )
    parser.add_argument(
        "--cost",
        type=str,
        default=None,
        metavar="MODEL",
        help=f"Print a cost-savings estimate for MODEL. Options: {', '.join(list_supported_models())}",
    )
    parser.add_argument(
        "--requests-per-day",
        type=int,
        default=1000,
        help="Request volume used for --cost estimates (default: 1000).",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    result = compress(text, target_ratio=args.ratio, query=args.query)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.compressed_text)
    else:
        print(result.compressed_text)

    if args.stats:
        print("\n--- Compression Stats ---", file=sys.stderr)
        print(result.summary(), file=sys.stderr)

    if args.cost:
        print("\n--- Cost Savings Estimate ---", file=sys.stderr)
        estimate = estimate_cost_savings(
            result.original_tokens,
            result.compressed_tokens,
            model=args.cost,
            requests_per_day=args.requests_per_day,
        )
        print(estimate.summary(), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
