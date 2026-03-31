"""Debug YouTube search results and transcript availability."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine.cleaning import clean_opinion_records
from opinion_engine.config import get_database_url
from opinion_engine.models import SpiderRequest
from opinion_engine.spiders.youtube import YouTubeTranscriptSpider
from opinion_engine.storage import OpinionStorage


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for YouTube-only debugging."""
    parser = argparse.ArgumentParser(
        description="Debug YouTube search ranking and transcript availability.",
    )
    parser.add_argument("keyword", type=str, help='Keyword to collect, e.g. "DeepSeek".')
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        choices=["en", "zh"],
        help="Language code for search relevance.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum YouTube videos to inspect.",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Persist cleaned YouTube transcript records into the local database.",
    )
    return parser.parse_args()


async def _run(keyword: str, language: str, limit: int, store: bool) -> dict[str, object]:
    """Execute the YouTube-only debug flow."""
    spider = YouTubeTranscriptSpider()
    request = SpiderRequest(
        keyword=keyword,
        limit=limit,
        extra_params={
            "language": language,
            "strict_captions_only": False,
        },
    )
    debug_result = await spider.debug_collect(request)
    if not store:
        return debug_result

    records = await spider.fetch(request)
    clean_result = clean_opinion_records(records)
    storage = OpinionStorage()
    await asyncio.to_thread(storage.initialize)
    run_id = await asyncio.to_thread(storage.create_run, keyword, language)
    stored_count = await asyncio.to_thread(
        storage.save_cleaned_records,
        run_id=run_id,
        records=clean_result.records,
    )
    await asyncio.to_thread(
        storage.mark_run_collected,
        run_id=run_id,
        retained_count=stored_count,
        discarded_count=clean_result.discarded_count,
        source_breakdown={"youtube": stored_count},
        source_errors={},
    )
    debug_result["storage"] = {
        "database_url": get_database_url(),
        "database_path": _resolve_sqlite_path(get_database_url()),
        "run_id": run_id,
        "prepared_record_count": len(records),
        "stored_record_count": stored_count,
        "discarded_record_count": clean_result.discarded_count,
    }
    return debug_result


def _resolve_sqlite_path(database_url: str) -> str | None:
    """Extract a local SQLite file path from a SQLAlchemy database URL when possible."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return database_url.removeprefix(prefix).replace("/", "\\")


def main() -> None:
    """Run the YouTube-only debug flow and print JSON output."""
    args = parse_args()
    result = asyncio.run(_run(args.keyword, args.language, args.limit, args.store))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
