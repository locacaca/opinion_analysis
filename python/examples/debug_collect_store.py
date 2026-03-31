"""Debug script for collection-cleaning-storage without LLM analysis."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine import collect_and_store_keyword


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for collection-only debugging."""
    parser = argparse.ArgumentParser(
        description="Collect source data, clean it, and store it without using the LLM.",
    )
    parser.add_argument("keyword", type=str, help='Keyword to collect, e.g. "iPhone 16".')
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        choices=["en", "zh"],
        help="Language code for collection hints.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum records per selected source.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["youtube"],
        help="Selected sources: reddit youtube x",
    )
    return parser.parse_args()


def main() -> None:
    """Run the collection-only debug pipeline and print JSON output."""
    args = parse_args()
    result = asyncio.run(
        collect_and_store_keyword(
            args.keyword,
            language=args.language,
            limit_per_source=args.limit,
            sources=args.sources,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
