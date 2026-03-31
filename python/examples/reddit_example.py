"""Executable example for collecting Reddit opinion data."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine.models import SpiderRequest
from opinion_engine.spiders.reddit import RedditSpider


async def run(keyword: str, limit: int) -> list[dict[str, object]]:
    """Collect Reddit posts for a keyword and return normalized dictionaries."""
    spider = RedditSpider()
    request = SpiderRequest(keyword=keyword, limit=limit)
    return await spider.fetch(request)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the Reddit example."""
    parser = argparse.ArgumentParser(description="Run the Reddit spider example.")
    parser.add_argument("keyword", type=str, help="Keyword to search on Reddit.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of Reddit posts to return.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the example script and print normalized JSON output."""
    args = parse_args()
    records = asyncio.run(run(keyword=args.keyword, limit=args.limit))
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
