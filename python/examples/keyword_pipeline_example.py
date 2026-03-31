"""Executable example for keyword-driven multi-source opinion analysis."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine import analyze_keyword


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the keyword analysis pipeline."""
    parser = argparse.ArgumentParser(description="Run multi-source keyword opinion analysis.")
    parser.add_argument("keyword", type=str, help="Keyword to analyze.")
    parser.add_argument("--limit", type=int, default=10, help="Max records per source.")
    parser.add_argument(
        "--enable-x",
        action="store_true",
        help="Include the X/Twitter source stub in the pipeline.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the keyword analysis pipeline and print dashboard-ready JSON."""
    args = parse_args()
    result = asyncio.run(
        analyze_keyword(
            args.keyword,
            limit_per_source=args.limit,
            enable_x=args.enable_x,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
