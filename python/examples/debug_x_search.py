"""Debug X/Twitter keyword search on Nitter and optional database storage."""

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
from opinion_engine.spiders.x_stub import XSearchSpider
from opinion_engine.storage import OpinionStorage


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for X-only debugging."""
    parser = argparse.ArgumentParser(
        description="Debug Nitter-based X/Twitter keyword search with paginated collection.",
    )
    parser.add_argument("keyword", type=str, help='Keyword to collect, e.g. "DeepSeek".')
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum X posts to inspect.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        choices=["en", "zh"],
        help="Language hint used in the Nitter search query.",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="Optional browser proxy, e.g. http://127.0.0.1:7890",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run the browser in headless mode (default: true).",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run the browser with a visible window.",
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        default=True,
        help="Keep randomized human-like delays enabled (default: true).",
    )
    parser.add_argument(
        "--no-slow",
        dest="slow",
        action="store_false",
        help="Disable most human-like delays.",
    )
    parser.add_argument(
        "--store",
        action="store_true",
        help="Persist cleaned X search records into the local database.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a readable preview before the final JSON output.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=str,
        default="python/debug_outputs/x_search",
        help="Directory for saved search-page screenshots and HTML.",
    )
    return parser.parse_args()


async def _run(
    *,
    keyword: str,
    limit: int,
    language: str,
    proxy: str | None,
    headless: bool,
    slow_mode: bool,
    store: bool,
    verbose: bool,
    artifact_dir: str,
) -> dict[str, object]:
    """Execute the Nitter-based X debug flow."""
    spider = XSearchSpider(
        proxy=proxy,
        headless=headless,
        slow_mode=slow_mode,
    )
    request = SpiderRequest(
        keyword=keyword,
        limit=limit,
        extra_params={
            "language": language,
            "debug_artifact_dir": artifact_dir,
        },
    )

    debug_result = await spider.debug_collect(request)
    if verbose:
        _print_verbose_preview(debug_result)

    if not store:
        return debug_result

    tweets = debug_result.get("tweets", [])
    if not isinstance(tweets, list):
        tweets = []
    records = spider.clean_data(tweets)
    clean_result = clean_opinion_records(records)
    storage = OpinionStorage()
    await asyncio.to_thread(storage.initialize)
    run_id = await asyncio.to_thread(storage.create_run, keyword, language)
    stored_count = 0
    if clean_result.records:
        stored_count = await asyncio.to_thread(
            storage.save_cleaned_records,
            run_id=run_id,
            records=clean_result.records,
        )
    source_error = debug_result.get("collection_error")
    source_errors = {"x": str(source_error)} if source_error else {}
    await asyncio.to_thread(
        storage.mark_run_collected,
        run_id=run_id,
        retained_count=stored_count,
        discarded_count=clean_result.discarded_count,
        source_breakdown={"x": stored_count},
        source_errors=source_errors,
    )
    debug_result["storage"] = {
        "database_url": get_database_url(),
        "database_path": _resolve_sqlite_path(get_database_url()),
        "run_id": run_id,
        "prepared_record_count": len(records),
        "stored_record_count": stored_count,
        "discarded_record_count": clean_result.discarded_count,
        "source_errors": source_errors,
    }
    return debug_result


def _print_verbose_preview(debug_result: dict[str, object]) -> None:
    """Print a compact human-readable preview of debug results."""
    tweets = debug_result.get("tweets", [])
    if not isinstance(tweets, list):
        return
    print(f"Collected {len(tweets)} X posts")
    print("Search mode: Nitter mirror, paginated collection, local keyword filter=enabled")
    search_pages = debug_result.get("search_pages", [])
    if isinstance(search_pages, list) and search_pages:
        first_page = search_pages[0]
        if isinstance(first_page, dict):
            print(f"Search URL: {debug_result.get('search_url', '')}")
            print(f"First page screenshot: {first_page.get('screenshot_path', '')}")
            print(f"First page HTML: {first_page.get('html_path', '')}")
            print(f"First page result count: {first_page.get('result_count_on_page', '')}")
            print(f"First page next URL: {first_page.get('next_page_url', '')}")
    collection_error = debug_result.get("collection_error")
    if collection_error:
        print(f"Collection error: {collection_error}")
    for index, item in enumerate(tweets, start=1):
        if not isinstance(item, dict):
            continue
        print(f"[{index}] {item.get('display_name', '')} @{item.get('username', '')}")
        print(f"    url={item.get('tweet_url', '')}")
        print(f"    publish_date={item.get('publish_date', '')}")
        print(f"    content={str(item.get('content', ''))[:180]}")


def _resolve_sqlite_path(database_url: str) -> str | None:
    """Extract a local SQLite file path from a SQLAlchemy database URL when possible."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return database_url.removeprefix(prefix).replace("/", "\\")


def main() -> None:
    """Run the X-only debug flow and print JSON output."""
    args = parse_args()
    result = asyncio.run(
        _run(
            keyword=args.keyword,
            limit=args.limit,
            language=args.language,
            proxy=args.proxy,
            headless=args.headless,
            slow_mode=args.slow,
            store=args.store,
            verbose=args.verbose,
            artifact_dir=args.artifact_dir,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
