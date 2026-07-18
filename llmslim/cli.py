"""Command-line interface for llmslim.

Usage:
    llmslim input.txt -r 0.5 -o compressed.txt --stats
    llmslim input.txt --detect --mode quality
    llmslim input.txt --analyze
    cat prompt.txt | llmslim --ratio 0.4 --cost gpt-5
"""

from __future__ import annotations

import argparse
import sys

from .analysis import analyze as run_analysis
from .core import compress
from .cost import estimate_cost_savings, list_supported_models
from .modes import list_modes


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
        "-m",
        "--mode",
        type=str,
        default=None,
        help=f"Optimisation mode. Options: 'auto', {', '.join(list_modes())}",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Auto-detect input content type and populate detailed telemetry.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run content analysis only and print the profile (does not perform compression).",
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
        "-s",
        "--strategy",
        type=str,
        default="extractive",
        choices=["extractive", "rewrite", "hybrid"],
        help="Optimization strategy: 'extractive' (default), 'rewrite', or 'hybrid'.",
    )
    parser.add_argument(
        "-b",
        "--backend",
        type=str,
        default="tfidf",
        help="Embedding backend for semantic ranking: 'tfidf' (fast, default) or 'semantic'/'sentence-transformers'.",
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

    if args.analyze:
        profile = run_analysis(text)
        print("--- Content Analysis Profile ---")
        print(f"Content Type     : {profile.content_type.value}")
        print(f"Confidence       : {profile.confidence:.0%}")
        print(f"Secondary Types  : {', '.join(s.value for s in profile.secondary_types) or 'None'}")
        print(f"Has Structure    : {profile.has_structure}")
        print(f"Estimated Tokens : {profile.estimated_tokens}")
        print(f"Language Hint    : {profile.language_hint or 'None'}")
        print(f"Structure Depth  : {profile.structure_depth}")
        print(f"Instruction Dens.: {profile.instruction_density:.2f}")
        print(f"Entity Density   : {profile.entity_density:.2f}")
        return 0

    result = compress(
        text,
        target_ratio=args.ratio,
        query=args.query,
        mode=args.mode,
        detect_content=args.detect,
        strategy=args.strategy,
        embedding_backend=args.backend,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.compressed_text)
    else:
        print(result.compressed_text)

    if args.stats:
        print("\n--- Compression Stats ---", file=sys.stderr)
        if result.mode is not None or result.content_type is not None:
            print(result.detailed_summary(), file=sys.stderr)
        else:
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
