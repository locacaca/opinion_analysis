"""Debug YouTube search with Playwright-based transcript fetching."""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import random
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Error, Page, async_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine.cleaning import clean_opinion_records
from opinion_engine.config import get_database_url, get_optional_env, load_env_file
from opinion_engine.spiders.youtube import (
    YouTubeTranscriptSpider,
    _build_opinion_records_from_youtube_items,
    _get_proxy_url,
)
from opinion_engine.storage import OpinionStorage


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for headless YouTube debugging."""
    parser = argparse.ArgumentParser(
        description="Debug YouTube search and browser-based transcript extraction.",
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
        help="Run Chromium in headless mode (default: true).",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run Chromium with a visible window.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=str,
        default="python/debug_outputs/youtube_headless",
        help="Directory for saved screenshots and HTML on failures.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a readable preview before the final JSON output.",
    )
    return parser.parse_args()


async def _run(
    *,
    keyword: str,
    language: str,
    limit: int,
    store: bool,
    proxy: str | None,
    headless: bool,
    artifact_dir: str,
    verbose: bool,
) -> dict[str, object]:
    """Execute the YouTube-only debug flow using browser transcript fetching."""
    collection_result = await collect_youtube_headless_records(
        keyword=keyword,
        language=language,
        limit=limit,
        proxy=proxy,
        headless=headless,
        artifact_dir=artifact_dir,
        record_callback=None,
    )
    raw_video_details = collection_result["raw_video_details"]
    video_details = collection_result["video_details"]
    skipped_videos = collection_result["skipped_videos"]
    transcript_items = collection_result["transcript_items"]
    browser_debug = collection_result["browser_debug"]

    transcript_map = {
        str(item.get("video_id")): item
        for item in transcript_items
        if isinstance(item, dict) and item.get("video_id")
    }
    for item in video_details:
        transcript_item = transcript_map.get(str(item.get("video_id")))
        if transcript_item:
            item["transcript_debug"] = transcript_item.get("transcript_debug")
            item["transcript_error"] = transcript_item.get("fetch_error")
        else:
            item["transcript_error"] = item.get("transcript_error") or "Browser transcript fetch returned no record."

    debug_result: dict[str, object] = {
        "raw_search_result_count": len(raw_video_details),
        "search_result_count": len(video_details),
        "skipped_short_count": len(skipped_videos),
        "transcript_success_count": len(
            [
                item
                for item in transcript_items
                if str(item.get("transcript_text", "")).strip()
            ]
        ),
        "videos": [
            {
                "video_id": item.get("video_id"),
                "video_url": item.get("video_url")
                or f"https://www.youtube.com/watch?v={item.get('video_id')}",
                "has_transcript": bool(
                    transcript_map.get(str(item.get("video_id")), {}).get("transcript_text")
                ),
                "transcript_status": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("transcript_status"),
                "analysis_text_source": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("analysis_text_source"),
                "transcript_text": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("transcript_text"),
                "transcript_language": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("language"),
                "transcript_segment_count": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("segment_count"),
                "comments_count": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("comments_count"),
                "comments_text": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("comments_text"),
                "title": item.get("title"),
                "author": item.get("channel_title"),
                "description": item.get("description"),
                "publish_date": item.get("publish_date"),
                "views": item.get("views"),
                "length_seconds": item.get("length_seconds"),
                "thumbnail_url": item.get("thumbnail_url"),
                "metadata_source": item.get("metadata_source"),
                "metadata_warning": item.get("metadata_warning"),
                "transcript_debug": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("transcript_debug"),
                "transcript_error": item.get("transcript_error"),
            }
            for item in video_details
        ],
        "transcript_failures": [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "author": item.get("channel_title"),
                "error": item.get("transcript_error"),
                "transcript_debug": transcript_map.get(
                    str(item.get("video_id")),
                    {},
                ).get("transcript_debug"),
            }
            for item in video_details
            if item.get("transcript_error")
        ],
        "skipped_videos": skipped_videos,
        "coverage": _build_coverage_summary(transcript_items),
        "browser_debug": browser_debug,
    }

    if verbose:
        _print_verbose_preview(debug_result)

    if not store:
        return debug_result

    records = _build_opinion_records_from_youtube_items(
        keyword=keyword,
        video_details=video_details,
        transcript_items=transcript_items,
    )
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


async def collect_youtube_headless_records(
    *,
    keyword: str,
    language: str,
    limit: int,
    proxy: str | None,
    headless: bool,
    artifact_dir: str,
    record_callback: Any | None,
) -> dict[str, Any]:
    """Collect YouTube metadata and transcript-oriented records with Playwright."""
    load_env_file()
    spider = YouTubeTranscriptSpider()

    search_limit = min(max(limit + 6, int(limit * 1.5)), 30)
    raw_video_details = await spider._search_videos(
        keyword=keyword,
        limit=search_limit,
        published_after="",
        language=language,
        strict_captions_only=False,
    )
    raw_video_details = await asyncio.to_thread(spider._enrich_video_details, raw_video_details)
    video_details, skipped_videos = _filter_preferred_videos(
        video_details=raw_video_details,
        limit=limit,
    )
    transcript_items, browser_debug = await _fetch_transcripts_with_browser(
        video_details=video_details,
        requested_language=language,
        proxy=proxy or _get_proxy_url(),
        headless=headless,
        artifact_dir=artifact_dir,
    )

    records = _build_opinion_records_from_youtube_items(
        keyword=keyword,
        video_details=video_details,
        transcript_items=transcript_items,
    )
    if callable(record_callback):
        for record in records:
            record_callback(record)

    return {
        "raw_video_details": raw_video_details,
        "video_details": video_details,
        "skipped_videos": skipped_videos,
        "transcript_items": transcript_items,
        "browser_debug": browser_debug,
        "records": records,
    }


async def _fetch_transcripts_with_browser(
    *,
    video_details: list[dict[str, Any]],
    requested_language: str,
    proxy: str,
    headless: bool,
    artifact_dir: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch transcripts through a real browser session instead of direct HTTP calls."""
    proxy_config = {"server": proxy} if proxy else None
    browser_debug: dict[str, Any] = {
        "headless": headless,
        "proxy": proxy,
        "artifact_dir": artifact_dir,
        "attempted_video_count": len(video_details),
        "browser_failures": [],
        "strategy": "transcript_panel_only",
    }
    transcript_items: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            proxy=proxy_config,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=1440,1024",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent=_browser_user_agent(),
            viewport={"width": 1440, "height": 1024},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()

        try:
            for index, item in enumerate(video_details, start=1):
                result = await _fetch_single_video_transcript(
                    context=context,
                    page=page,
                    video_item=item,
                    requested_language=requested_language,
                    artifact_dir=artifact_dir,
                    page_index=index,
                )
                transcript_items.append(result)
        finally:
            await context.close()
            await browser.close()

    browser_debug["success_count"] = len(
        [item for item in transcript_items if str(item.get("transcript_text", "")).strip()]
    )
    browser_debug["comment_fallback_count"] = len(
        [
            item
            for item in transcript_items
            if not str(item.get("transcript_text", "")).strip()
            and str(item.get("comments_text", "")).strip()
        ]
    )
    browser_debug["metadata_only_count"] = len(
        [
            item
            for item in transcript_items
            if not str(item.get("transcript_text", "")).strip()
            and not str(item.get("comments_text", "")).strip()
        ]
    )
    return transcript_items, browser_debug


async def _fetch_single_video_transcript(
    *,
    context: BrowserContext,
    page: Page,
    video_item: dict[str, Any],
    requested_language: str,
    artifact_dir: str,
    page_index: int,
) -> dict[str, Any]:
    """Fetch one video transcript using transcript-panel network responses first."""
    video_id = str(video_item.get("video_id") or "").strip()
    video_url = str(
        video_item.get("video_url") or f"https://www.youtube.com/watch?v={video_id}"
    ).strip()
    title = str(video_item.get("title") or "").strip()
    description = str(video_item.get("description") or "").strip()
    await page.goto(video_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(random.randint(2600, 4200))
    try:
        await page.wait_for_load_state("networkidle", timeout=7000)
    except Error:
        pass
    ad_debug = await _ensure_main_video_ready(page)

    page_state, player_state_attempts = await _read_player_state_with_retries(
        page=page,
        requested_language=requested_language,
    )

    captions = list(page_state.get("captions") or [])
    selected_track = _choose_caption_track(captions, requested_language=requested_language)
    transcript_text = ""
    fetch_error: str | None = _infer_transcript_panel_failure(page_state=page_state)
    response_status: int | None = None
    fetch_mode = "transcript_panel_pending"
    response_text_length = 0
    response_text_preview = ""
    requested_caption_urls: list[str] = []
    final_caption_url = ""
    ui_fallback_attempted = False
    ui_fallback_opened = False
    fetch_attempts: list[dict[str, Any]] = []
    ui_debug: dict[str, Any] = {}
    comments_text = ""
    comments_count = 0
    comments_debug: dict[str, Any] = {}
    downgrade_reason: str | None = None

    has_caption_tracks = bool(captions)
    if not has_caption_tracks:
        downgrade_reason = "no_caption_tracks"

    if not transcript_text and has_caption_tracks:
        ui_fallback_attempted = True
        transcript_panel_text, ui_fallback_opened, ui_debug = await _extract_transcript_from_ui(page)
        if transcript_panel_text:
            transcript_text = transcript_panel_text
            fetch_error = None
            fetch_mode = "youtube_transcript_panel_dom"
        else:
            fetch_mode = "transcript_panel_only"
            fetch_error = fetch_error or "Transcript panel did not yield usable transcript text."
    elif not has_caption_tracks:
        fetch_mode = "captionless_early_downgrade"

    if not transcript_text:
        comments_text, comments_count, comments_debug = await _extract_top_comments(
            page=page,
            max_comments=5,
            max_total_length=1800,
        )

    analysis_text_source = "transcript"
    transcript_status = "verified"
    if not transcript_text and comments_text:
        analysis_text_source = "comments_fallback"
        transcript_status = "missing_comments_fallback"
    elif not transcript_text:
        analysis_text_source = "metadata_only"
        transcript_status = "missing"

    content_parts = [title]
    if transcript_text:
        content_parts.append(transcript_text)
    elif comments_text:
        content_parts.append(comments_text)
    if description:
        content_parts.append(description)
    content = "\n\n".join(part for part in content_parts if part).strip()

    return {
        "video_id": video_id,
        "video_url": video_url,
        "keyword": video_item.get("keyword"),
        "author": video_item.get("channel_title"),
        "title": title,
        "language": str(selected_track.get("languageCode") or requested_language) if selected_track else requested_language,
        "segment_count": transcript_text.count(" ") + 1 if transcript_text else 0,
        "content": content,
        "transcript_text": transcript_text,
        "comments_text": comments_text,
        "comments_count": comments_count,
        "transcript_status": transcript_status,
        "analysis_text_source": analysis_text_source,
        "transcript_origin": "playwright_caption_track_fetch",
        "selected_language": str(selected_track.get("languageCode") or requested_language) if selected_track else requested_language,
        "is_generated": bool(str(selected_track.get("kind") or "").strip() == "asr") if selected_track else None,
        "available_transcript_languages": [
            str(track.get("languageCode") or "").strip()
            for track in captions
            if str(track.get("languageCode") or "").strip()
        ],
        "description": description,
        "publish_date": video_item.get("publish_date"),
        "views": video_item.get("views"),
        "length_seconds": video_item.get("length_seconds"),
        "thumbnail_url": video_item.get("thumbnail_url"),
        "fetch_error": fetch_error,
        "transcript_debug": {
            "selected_language": str(selected_track.get("languageCode") or requested_language) if selected_track else requested_language,
            "available_transcript_languages": [
                str(track.get("languageCode") or "").strip()
                for track in captions
                if str(track.get("languageCode") or "").strip()
            ],
            "player_state_attempts": player_state_attempts,
            "caption_track_count": len(captions),
            "response_status": response_status,
            "requested_caption_urls": requested_caption_urls,
            "final_caption_url": final_caption_url,
            "response_text_length": response_text_length,
            "response_text_preview": response_text_preview,
            "player_url": page_state.get("currentUrl"),
            "page_title": page_state.get("title"),
            "challenge_excerpt": str(page_state.get("challengeText") or "")[:240],
            "ad_debug": ad_debug,
            "downgrade_reason": downgrade_reason,
            "fetch_mode": fetch_mode,
            "fetch_attempts": fetch_attempts,
            "ui_fallback_attempted": ui_fallback_attempted,
            "ui_fallback_opened": ui_fallback_opened,
            "ui_debug": ui_debug,
            "comments_debug": comments_debug,
        },
    }


async def _read_player_state_with_retries(
    *,
    page: Page,
    requested_language: str,
) -> tuple[dict[str, Any], int]:
    """Poll the watch page until caption tracks appear or retries are exhausted."""
    last_state: dict[str, Any] = {}
    for attempt in range(1, 5):
        state = await page.evaluate(
            """() => {
                const response = window.ytInitialPlayerResponse || null;
                const captions =
                  response?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
                return {
                  currentUrl: window.location.href,
                  title: document.title,
                  challengeText: document.body?.innerText?.slice(0, 1200) || "",
                  captions: captions.map(track => ({
                    baseUrl: track.baseUrl || "",
                    languageCode: track.languageCode || "",
                    name: track.name?.simpleText || "",
                    kind: track.kind || "",
                    vssId: track.vssId || ""
                  }))
                };
            }"""
        )
        last_state = state
        captions = list(state.get("captions") or [])
        selected_track = _choose_caption_track(captions, requested_language=requested_language)
        if selected_track and str(selected_track.get("baseUrl") or "").strip():
            return state, attempt
        if attempt < 4:
            await page.wait_for_timeout(random.randint(900, 1800))
    return last_state, 4


async def _ensure_main_video_ready(page: Page) -> dict[str, Any]:
    """Detect and lightly handle pre-roll ads before transcript extraction starts."""
    debug: dict[str, Any] = {
        "ad_detected": False,
        "skip_clicked": False,
        "waited_for_ad_ms": 0,
        "final_ad_state": False,
    }
    try:
        initial_ad_state = await _is_ad_showing(page)
    except Error:
        initial_ad_state = False
    debug["ad_detected"] = initial_ad_state
    if not initial_ad_state:
        debug["final_ad_state"] = False
        return debug

    waited_ms = 0
    for _ in range(5):
        if await _click_skip_ad_if_present(page):
            debug["skip_clicked"] = True
            await page.wait_for_timeout(800)
            break
        await page.wait_for_timeout(1200)
        waited_ms += 1200
        try:
            if not await _is_ad_showing(page):
                break
        except Error:
            break

    debug["waited_for_ad_ms"] = waited_ms
    try:
        debug["final_ad_state"] = await _is_ad_showing(page)
    except Error:
        debug["final_ad_state"] = False
    return debug


async def _is_ad_showing(page: Page) -> bool:
    """Return whether the YouTube watch page appears to be in ad playback mode."""
    return bool(
        await page.evaluate(
            """() => {
                const player = document.querySelector('#movie_player');
                if (!player) {
                    return false;
                }
                const className = player.className || '';
                const text = document.body?.innerText?.slice(0, 400) || '';
                return (
                    className.includes('ad-showing') ||
                    className.includes('ad-interrupting') ||
                    text.includes('Skip Ads') ||
                    text.includes('Skip Ad') ||
                    text.includes('Advertisement')
                );
            }"""
        )
    )


async def _click_skip_ad_if_present(page: Page) -> bool:
    """Click YouTube skip-ad controls when they are visible."""
    return await _click_first_visible(
        page,
        selectors=[
            "button.ytp-skip-ad-button",
            "button.ytp-skip-ad-button-modern",
            ".ytp-ad-skip-button-modern",
            ".ytp-ad-skip-button",
            "button:has-text('Skip Ads')",
            "button:has-text('Skip Ad')",
        ],
    )


def _choose_caption_track(
    tracks: list[dict[str, Any]],
    *,
    requested_language: str,
) -> dict[str, Any] | None:
    """Pick the best caption track from the browser-visible caption list."""
    if not tracks:
        return None
    if requested_language == "zh":
        preferred = ["zh-Hans", "zh-Hant", "zh", "en"]
    else:
        preferred = ["en", "en-US", "en-GB", "zh", "zh-Hans"]
    for language_code in preferred:
        for track in tracks:
            if str(track.get("languageCode") or "").strip() == language_code:
                return track
    return tracks[0]


def _parse_timedtext_xml(raw_xml: str) -> str:
    """Parse YouTube timedtext XML into plain transcript text."""
    normalized = raw_xml.strip()
    if not normalized:
        return ""
    try:
        root = ET.fromstring(normalized)
    except ET.ParseError:
        return ""
    snippets: list[str] = []
    for element in root.findall(".//text"):
        value = "".join(element.itertext()).strip()
        if not value:
            continue
        decoded = html.unescape(value).replace("\n", " ").strip()
        if decoded:
            snippets.append(decoded)
    return " ".join(snippets).strip()


def _parse_caption_payload(raw_payload: str) -> str:
    """Parse either XML timedtext or JSON3 caption payload into plain text."""
    normalized = raw_payload.strip()
    if not normalized:
        return ""
    if normalized.startswith("{"):
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            payload = {}
        events = payload.get("events", []) if isinstance(payload, dict) else []
        snippets: list[str] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            segments = event.get("segs", [])
            if not isinstance(segments, list):
                continue
            text = "".join(
                str(segment.get("utf8", ""))
                for segment in segments
                if isinstance(segment, dict)
            ).strip()
            decoded = html.unescape(text).replace("\n", " ").strip()
            if decoded:
                snippets.append(decoded)
        return " ".join(snippets).strip()
    return _parse_timedtext_xml(normalized)


def _infer_caption_failure(*, page_state: dict[str, Any]) -> str:
    """Generate a clearer error when no caption track could be used."""
    captions = list(page_state.get("captions") or [])
    if captions:
        return "Caption tracks were found, but no usable caption URL was selected."
    challenge_text = str(page_state.get("challengeText") or "").casefold()
    if "sign in to confirm you're not a bot" in challenge_text:
        return "YouTube presented an anti-bot challenge page."
    if "unusual traffic" in challenge_text:
        return "YouTube reported unusual traffic for this browser session."
    return "No caption tracks were exposed in ytInitialPlayerResponse."


def _infer_transcript_panel_failure(*, page_state: dict[str, Any]) -> str:
    """Generate a clearer error for the transcript-panel-first strategy."""
    captions = list(page_state.get("captions") or [])
    if captions:
        return "Caption tracks exist, but transcript panel extraction has not yielded text yet."
    challenge_text = str(page_state.get("challengeText") or "").casefold()
    if "sign in to confirm you're not a bot" in challenge_text:
        return "YouTube presented an anti-bot challenge page."
    if "unusual traffic" in challenge_text:
        return "YouTube reported unusual traffic for this browser session."
    return "No caption tracks were exposed in ytInitialPlayerResponse."


async def _extract_transcript_from_ui(page: Page) -> tuple[str, bool, dict[str, Any]]:
    """Open the transcript panel from the watch page and extract visible transcript text."""
    captured_responses: list[Any] = []

    def _response_listener(response: Any) -> None:
        if _looks_like_transcript_network_response(response):
            captured_responses.append(response)

    page.on("response", _response_listener)
    await _expand_description_if_needed(page)
    try:
        if await _click_first_visible(
            page,
            selectors=[
                "button[aria-label*='Show transcript']",
                "button[aria-label*='Transcript']",
                "button:has-text('Show transcript')",
                "button:has-text('Transcript')",
            ],
        ):
            await page.wait_for_timeout(1200)
            opened = True
        else:
            opened_menu = await _click_first_visible(
                page,
                selectors=[
                    "button[aria-label*='More actions']",
                    "button[aria-label*='Action menu']",
                    "ytd-menu-renderer yt-button-shape button",
                    "#top-level-buttons-computed button[aria-label]",
                    "ytd-menu-renderer button",
                ],
            )
            if not opened_menu:
                return "", False, {"menu_opened": False}
            await page.wait_for_timeout(1200)
            clicked_item = await _click_first_visible(
                page,
                selectors=[
                    "tp-yt-paper-item:has-text('Show transcript')",
                    "ytd-menu-service-item-renderer:has-text('Show transcript')",
                    "button:has-text('Show transcript')",
                    "tp-yt-paper-item:has-text('Transcript')",
                    "ytd-menu-service-item-renderer:has-text('Transcript')",
                ],
            )
            if not clicked_item:
                return "", False, {"menu_opened": True, "transcript_menu_item_clicked": False}
            await page.wait_for_timeout(1600)
            opened = True

        transcript_selectors = [
            "ytd-transcript-segment-renderer",
            "ytd-transcript-search-panel-renderer",
            "ytd-transcript-segment-list-renderer",
            "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-searchable-transcript']",
        ]
        selector_hits: dict[str, int] = {}
        api_transcript_text = ""
        api_response_debug: list[dict[str, Any]] = []
        normalized_segments: list[str] = []
        transcript_panel_preview = ""
        max_attempts = 1
        for attempt in range(1, max_attempts + 1):
            for selector in transcript_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3500)
                except Error:
                    pass
                try:
                    selector_hits[selector] = await page.locator(selector).count()
                except Error:
                    selector_hits[selector] = 0

            try:
                transcript_panel = page.locator(
                    "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-searchable-transcript']"
                ).first
                if await transcript_panel.count():
                    await transcript_panel.hover(timeout=1500)
                    await page.mouse.wheel(0, 500)
                    await page.wait_for_timeout(900)
                    await page.mouse.wheel(0, -300)
                    await page.wait_for_timeout(700)
            except Error:
                pass

            api_transcript_text, api_response_debug = await _extract_transcript_from_captured_responses(
                responses=captured_responses
            )
            if api_transcript_text:
                break

            segments = await page.locator(
                "ytd-transcript-segment-renderer .segment-text, "
                "ytd-transcript-segment-renderer yt-formatted-string.segment-text, "
                "ytd-transcript-segment-renderer [class*='segment-text'], "
                "ytd-transcript-segment-list-renderer .segment-text"
            ).all_inner_texts()
            normalized_segments = [
                " ".join(segment.split())
                for segment in segments
                if " ".join(segment.split())
            ]
            if normalized_segments:
                break

            await page.wait_for_timeout(900)

        try:
            transcript_panel_preview = str(
                await page.locator(
                    "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-searchable-transcript']"
                ).first.inner_text(timeout=3000)
            )[:600]
        except Error:
            transcript_panel_preview = ""
        debug = {
            "selector_hits": selector_hits,
            "segment_count": len(normalized_segments),
            "panel_preview": transcript_panel_preview,
            "captured_response_count": len(captured_responses),
            "api_transcript_text_length": len(api_transcript_text),
            "api_response_debug": api_response_debug,
            "attempt_count": max_attempts,
        }
        if api_transcript_text:
            debug["extraction_mode"] = "panel_network_response"
            return api_transcript_text, opened, debug
        if normalized_segments:
            debug["extraction_mode"] = "panel_dom_segments"
            return " ".join(normalized_segments).strip(), opened, debug
        preview_transcript_text = _extract_transcript_from_panel_preview(transcript_panel_preview)
        if preview_transcript_text:
            debug["extraction_mode"] = "panel_preview_text"
            return preview_transcript_text, opened, debug
        return "", opened, debug
    finally:
        page.remove_listener("response", _response_listener)


def _looks_like_transcript_network_response(response: Any) -> bool:
    """Return whether a network response is likely to contain transcript data."""
    try:
        url = str(response.url or "").lower()
        if "get_transcript" in url or "transcript" in url:
            return True
        request = response.request
        post_data = str(request.post_data or "").lower()
        if "transcript" in post_data or "engagement-panel-searchable-transcript" in post_data:
            return True
        if "/youtubei/v1/next" in url and "engagement-panel-searchable-transcript" in post_data:
            return True
    except Exception:
        return False
    return False


async def _extract_transcript_from_captured_responses(
    *,
    responses: list[Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Parse transcript text from captured YouTube network responses."""
    candidates: list[str] = []
    response_debug: list[dict[str, Any]] = []
    for response in responses:
        url = ""
        status = None
        try:
            url = str(response.url or "")
            status = getattr(response, "status", None)
            body = await response.text()
        except Error:
            continue
        response_entry: dict[str, Any] = {
            "url": url[:240],
            "status": status,
            "body_length": len(body or ""),
        }
        if not body or not body.strip():
            response_entry["normalized_json"] = False
            response_entry["parsed_text_length"] = 0
            response_debug.append(response_entry)
            continue
        normalized_body = _normalize_json_response_body(body)
        if not normalized_body:
            response_entry["normalized_json"] = False
            response_entry["parsed_text_length"] = 0
            response_entry["body_preview"] = body[:180]
            response_debug.append(response_entry)
            continue
        response_entry["normalized_json"] = True
        try:
            payload = json.loads(normalized_body)
        except json.JSONDecodeError:
            response_entry["parsed_text_length"] = 0
            response_entry["body_preview"] = normalized_body[:180]
            response_debug.append(response_entry)
            continue
        text = _extract_transcript_text_from_json_payload(payload)
        response_entry["parsed_text_length"] = len(text)
        if not text:
            response_entry["body_preview"] = normalized_body[:180]
        response_debug.append(response_entry)
        if text:
            candidates.append(text)
    if not candidates:
        return "", response_debug[:4]
    candidates.sort(key=len, reverse=True)
    return candidates[0], response_debug[:4]


def _extract_transcript_text_from_json_payload(payload: Any) -> str:
    """Recursively extract transcript snippets from a transcript-like JSON payload."""
    snippets: list[str] = []

    def _collect_text(value: Any) -> str:
        if isinstance(value, dict):
            if isinstance(value.get("simpleText"), str):
                return str(value["simpleText"]).strip()
            if isinstance(value.get("text"), str):
                return str(value["text"]).strip()
            runs = value.get("runs")
            if isinstance(runs, list):
                joined = "".join(
                    str(run.get("text", ""))
                    for run in runs
                    if isinstance(run, dict)
                ).strip()
                if joined:
                    return joined
        return ""

    def _looks_like_timestamp(value: str) -> bool:
        return bool(re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", value.strip()))

    def _append_snippet(value: str) -> None:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            return
        if _looks_like_timestamp(normalized):
            return
        if normalized.casefold() in {"transcript", "chapters", "in this video", "timeline"}:
            return
        snippets.append(normalized)

    def _walk(node: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(node, dict):
            if "transcriptSegmentRenderer" in node:
                renderer = node.get("transcriptSegmentRenderer")
                if isinstance(renderer, dict):
                    snippet = _collect_text(renderer.get("snippet"))
                    if snippet:
                        _append_snippet(snippet)
            if "transcriptCueRenderer" in node:
                renderer = node.get("transcriptCueRenderer")
                if isinstance(renderer, dict):
                    cue_text = _collect_text(
                        renderer.get("cue")
                        or renderer.get("simpleText")
                        or renderer.get("formattedCue")
                    )
                    if cue_text:
                        _append_snippet(cue_text)
            if "transcriptCueGroupRenderer" in node:
                renderer = node.get("transcriptCueGroupRenderer")
                if isinstance(renderer, dict):
                    for cue in list(renderer.get("cues") or []):
                        _walk(cue, path + ("transcriptCueGroupRenderer",))
            if "transcriptBodyRenderer" in node:
                renderer = node.get("transcriptBodyRenderer")
                if isinstance(renderer, dict):
                    for cue_group in list(renderer.get("cueGroups") or []):
                        _walk(cue_group, path + ("transcriptBodyRenderer",))
            if "transcriptSearchPanelRenderer" in node:
                renderer = node.get("transcriptSearchPanelRenderer")
                if isinstance(renderer, dict):
                    for body_key in ("body", "footer", "header"):
                        _walk(renderer.get(body_key), path + ("transcriptSearchPanelRenderer", body_key))
            if "cue" in node:
                cue_text = _collect_text(node.get("cue"))
                if cue_text:
                    _append_snippet(cue_text)
            if "snippet" in node:
                snippet_text = _collect_text(node.get("snippet"))
                if snippet_text:
                    _append_snippet(snippet_text)
            if "content" in node:
                content_text = _collect_text(node.get("content"))
                if content_text:
                    _append_snippet(content_text)
            if "contentText" in node:
                content_text = _collect_text(node.get("contentText"))
                if content_text:
                    _append_snippet(content_text)
            for key, value in node.items():
                lowered_key = str(key).casefold()
                if lowered_key in {
                    "accessibility",
                    "accessibilitydata",
                    "trackingparams",
                    "commandmetadata",
                }:
                    continue
                if lowered_key.endswith("runs") and isinstance(value, list):
                    joined_runs = _collect_text({"runs": value})
                    parent_path = " ".join(path).casefold()
                    if joined_runs and (
                        "transcript" in parent_path
                        or "cue" in parent_path
                        or "segment" in parent_path
                        or lowered_key == "runs"
                    ):
                        _append_snippet(joined_runs)
                if isinstance(value, str):
                    parent_path = " ".join(path + (str(key),)).casefold()
                    if (
                        value.strip()
                        and (
                            "transcript" in parent_path
                            or "cue" in parent_path
                            or "segment" in parent_path
                            or "snippet" in parent_path
                            or "contenttext" in parent_path
                        )
                    ):
                        _append_snippet(value)
                _walk(value, path + (str(key),))
        elif isinstance(node, list):
            for item in node:
                _walk(item, path)

    _walk(payload)
    deduped: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        normalized = " ".join(snippet.split()).strip()
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized)
    return " ".join(deduped).strip()


def _normalize_json_response_body(body: str) -> str:
    """Strip common YouTube response prefixes before JSON parsing."""
    normalized = body.strip()
    if not normalized:
        return ""
    if normalized.startswith(")]}'"):
        normalized = normalized[4:].lstrip()
    if normalized.startswith("{") or normalized.startswith("["):
        return normalized
    object_start = normalized.find("{")
    array_start = normalized.find("[")
    starts = [position for position in (object_start, array_start) if position >= 0]
    if not starts:
        return ""
    return normalized[min(starts):].lstrip()


def _extract_transcript_from_panel_preview(panel_preview: str) -> str:
    """Extract transcript-like lines from panel preview text when selectors miss."""
    lines = [line.strip() for line in str(panel_preview or "").splitlines()]
    kept: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.casefold() in {"transcript", "timeline", "chapters", "in this video"}:
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", line):
            continue
        if len(line) < 2:
            continue
        kept.append(line)
    deduped: list[str] = []
    seen: set[str] = set()
    for line in kept:
        lowered = line.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(line)
    return " ".join(deduped).strip()


async def _extract_top_comments(
    *,
    page: Page,
    max_comments: int,
    max_total_length: int,
) -> tuple[str, int, dict[str, Any]]:
    """Extract a small set of top visible comments as transcript fallback text."""
    selector = "ytd-comment-thread-renderer #content-text"
    await page.wait_for_timeout(random.randint(500, 900))
    try:
        await page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight, 1400))")
    except Error:
        pass

    locator = page.locator(selector)
    collected: list[str] = []
    for _ in range(3):
        try:
            raw_comments = await locator.all_inner_texts()
        except Error:
            raw_comments = []
        normalized_comments: list[str] = []
        seen: set[str] = set()
        for raw_comment in raw_comments:
            normalized = " ".join(str(raw_comment).split()).strip()
            if not normalized:
                continue
            lowered = normalized.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized_comments.append(normalized)
        collected = normalized_comments[:max_comments]
        if len(collected) >= max_comments:
            break
        try:
            await page.mouse.wheel(0, 900)
        except Error:
            pass
        await page.wait_for_timeout(random.randint(500, 900))

    trimmed_comments: list[str] = []
    total_length = 0
    for comment in collected:
        if total_length >= max_total_length:
            break
        remaining = max_total_length - total_length
        snippet = comment[:remaining].strip()
        if not snippet:
            continue
        trimmed_comments.append(snippet)
        total_length += len(snippet) + 2

    return (
        "\n".join(trimmed_comments).strip(),
        len(trimmed_comments),
        {
            "selector": selector,
            "visible_comment_count": len(collected),
            "returned_comment_count": len(trimmed_comments),
            "text_length": len("\n".join(trimmed_comments).strip()),
        },
    )


async def _expand_description_if_needed(page: Page) -> None:
    """Expand the description block because transcript actions are sometimes nested nearby."""
    await _click_first_visible(
        page,
        selectors=[
            "tp-yt-paper-button#expand",
            "button[aria-label*='more']",
            "button:has-text('...more')",
            "button:has-text('more')",
        ],
    )
    await page.wait_for_timeout(500)


async def _click_first_visible(page: Page, *, selectors: list[str]) -> bool:
    """Click the first visible selector candidate and return whether it succeeded."""
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() == 0:
                continue
            if not await locator.is_visible():
                continue
            await locator.click(timeout=3000)
            return True
        except Error:
            continue
    return False


def _build_caption_url_candidates(base_url: str) -> list[str]:
    """Build caption URL variants because YouTube may return XML or JSON3 payloads."""
    normalized = base_url.strip()
    if not normalized:
        return []
    candidates = [normalized]
    if "fmt=" not in normalized:
        candidates.append(f"{normalized}&fmt=json3")
        candidates.append(f"{normalized}&fmt=srv3")
    else:
        candidates.append(re.sub(r"fmt=[^&]+", "fmt=json3", normalized))
        candidates.append(re.sub(r"fmt=[^&]+", "fmt=srv3", normalized))
    deduped: list[str] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


async def _fetch_caption_payload_with_retries(
    *,
    context: BrowserContext,
    page: Page,
    caption_urls: list[str],
) -> dict[str, Any]:
    """Fetch caption payloads with a few browser-session strategies and short retries."""
    last_status = 0
    last_text = ""
    last_url = ""
    last_mode = ""
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        for caption_url in caption_urls:
            fetched = await _fetch_caption_payload_via_page_fetch(page=page, caption_url=caption_url)
            attempts.append(
                {
                    "attempt": attempt,
                    "mode": "page_fetch",
                    "url": caption_url,
                    "status": fetched.get("status"),
                    "text_length": len(str(fetched.get("text") or "")),
                    "error": fetched.get("error"),
                }
            )
            last_status = int(fetched.get("status", 0) or 0)
            last_text = str(fetched.get("text") or "")
            last_url = caption_url
            last_mode = "page_fetch"
            if bool(fetched.get("ok")) and last_text.strip():
                return {
                    "ok": True,
                    "status": last_status,
                    "text": last_text,
                    "url": last_url,
                    "mode": last_mode,
                    "attempts": attempts,
                }

            fetched = await _fetch_caption_payload_via_context_request(
                context=context,
                caption_url=caption_url,
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "mode": "context_request",
                    "url": caption_url,
                    "status": fetched.get("status"),
                    "text_length": len(str(fetched.get("text") or "")),
                    "error": fetched.get("error"),
                }
            )
            last_status = int(fetched.get("status", 0) or 0)
            last_text = str(fetched.get("text") or "")
            last_url = caption_url
            last_mode = "context_request"
            if bool(fetched.get("ok")) and last_text.strip():
                return {
                    "ok": True,
                    "status": last_status,
                    "text": last_text,
                    "url": last_url,
                    "mode": last_mode,
                    "attempts": attempts,
                }
        if attempt < 3:
            await page.wait_for_timeout(random.randint(700, 1500))
    return {
        "ok": False,
        "status": last_status,
        "text": last_text,
        "url": last_url,
        "mode": last_mode,
        "attempts": attempts,
    }


async def _fetch_caption_payload_via_page_fetch(
    *,
    page: Page,
    caption_url: str,
) -> dict[str, Any]:
    """Fetch caption payload inside the watch page so cookies and origin match exactly."""
    try:
        result = await page.evaluate(
            """async (targetUrl) => {
                try {
                    const response = await fetch(targetUrl, {
                        method: "GET",
                        credentials: "include",
                        cache: "no-store",
                    });
                    const text = await response.text();
                    return {
                        ok: response.ok,
                        status: response.status,
                        text,
                        headers: {
                            contentType: response.headers.get("content-type") || "",
                            contentLength: response.headers.get("content-length") || "",
                        },
                    };
                } catch (error) {
                    return {
                        ok: false,
                        status: 0,
                        text: "",
                        error: String(error),
                        headers: {
                            contentType: "",
                            contentLength: "",
                        },
                    };
                }
            }""",
            caption_url,
        )
        return {
            "ok": bool(result.get("ok")),
            "status": int(result.get("status", 0) or 0),
            "text": str(result.get("text") or ""),
            "error": str(result.get("error") or ""),
            "headers": dict(result.get("headers") or {}),
        }
    except Error as exc:
        return {
            "ok": False,
            "status": 0,
            "text": "",
            "error": str(exc),
            "headers": {},
        }


async def _fetch_caption_payload_via_context_request(
    *,
    context: BrowserContext,
    caption_url: str,
) -> dict[str, Any]:
    """Fetch caption payload through Playwright's request client as a fallback."""
    try:
        response = await context.request.get(caption_url, fail_on_status_code=False)
        text = await response.text()
        return {
            "ok": bool(response.ok and text and text.strip()),
            "status": response.status,
            "text": text,
            "error": "",
        }
    except Error as exc:
        return {
            "ok": False,
            "status": 0,
            "text": "",
            "error": str(exc),
        }


async def _save_failure_artifacts(
    *,
    page: Page,
    artifact_dir: str,
    page_index: int,
    video_id: str,
) -> None:
    """Persist one failed watch page as screenshot and HTML for inspection."""
    target_dir = Path(artifact_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = target_dir / f"watch_{page_index:02d}_{video_id}.png"
    html_path = target_dir / f"watch_{page_index:02d}_{video_id}.html"
    await page.screenshot(path=str(screenshot_path), full_page=True)
    html_text = await page.content()
    html_path.write_text(html_text, encoding="utf-8")


def _browser_user_agent() -> str:
    """Return a realistic desktop browser user agent for Playwright."""
    configured = (get_optional_env("YOUTUBE_USER_AGENT") or "").strip()
    if configured:
        return configured
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )


def _filter_preferred_videos(
    *,
    video_details: list[dict[str, Any]],
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep standard landscape videos first and skip Shorts-like results."""
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in video_details:
        if len(selected) >= limit:
            break
        if _is_likely_short(item):
            skipped.append(
                {
                    "video_id": item.get("video_id"),
                    "title": item.get("title"),
                    "video_url": item.get("video_url")
                    or f"https://www.youtube.com/watch?v={item.get('video_id')}",
                    "reason": "shorts_filtered",
                    "length_seconds": item.get("length_seconds"),
                }
            )
            continue
        selected.append(item)
    return selected, skipped


def _is_likely_short(video_item: dict[str, Any]) -> bool:
    """Heuristically classify Shorts so the debug flow can skip them."""
    title = str(video_item.get("title") or "").casefold()
    description = str(video_item.get("description") or "").casefold()
    video_url = str(video_item.get("video_url") or "").casefold()
    length_seconds = int(video_item.get("length_seconds") or 0)
    if "/shorts/" in video_url:
        return True
    if "#shorts" in title or "#shorts" in description:
        return True
    if length_seconds and length_seconds <= 60:
        return True
    return False


def _build_coverage_summary(transcript_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize how many videos have transcript text versus comment fallback."""
    total = len(transcript_items)
    transcript_count = len(
        [item for item in transcript_items if str(item.get("transcript_text", "")).strip()]
    )
    comment_fallback_count = len(
        [
            item
            for item in transcript_items
            if not str(item.get("transcript_text", "")).strip()
            and str(item.get("comments_text", "")).strip()
        ]
    )
    metadata_only_count = max(0, total - transcript_count - comment_fallback_count)
    return {
        "total_videos": total,
        "transcript_count": transcript_count,
        "comment_fallback_count": comment_fallback_count,
        "metadata_only_count": metadata_only_count,
        "transcript_coverage_ratio": round((transcript_count / total), 4) if total else 0.0,
        "usable_text_ratio": round(
            ((transcript_count + comment_fallback_count) / total),
            4,
        )
        if total
        else 0.0,
    }


def _print_verbose_preview(debug_result: dict[str, object]) -> None:
    """Print a compact human-readable preview of debug results."""
    print(f"raw_search_result_count={debug_result.get('raw_search_result_count', 0)}")
    print(f"search_result_count={debug_result.get('search_result_count', 0)}")
    print(f"skipped_short_count={debug_result.get('skipped_short_count', 0)}")
    print(f"transcript_success_count={debug_result.get('transcript_success_count', 0)}")
    browser_debug = debug_result.get("browser_debug", {})
    if isinstance(browser_debug, dict):
        print(f"browser_proxy={browser_debug.get('proxy', '')}")
        print(f"artifact_dir={browser_debug.get('artifact_dir', '')}")
    videos = debug_result.get("videos", [])
    if not isinstance(videos, list):
        return
    for index, item in enumerate(videos[:5], start=1):
        if not isinstance(item, dict):
            continue
        print(f"[{index}] {item.get('title', '')}")
        print(f"    video_id={item.get('video_id', '')}")
        print(f"    has_transcript={item.get('has_transcript', False)}")
        print(f"    transcript_status={item.get('transcript_status', '')}")
        print(f"    analysis_text_source={item.get('analysis_text_source', '')}")
        print(f"    comments_count={item.get('comments_count', 0)}")
        print(f"    transcript_error={item.get('transcript_error')}")


def _resolve_sqlite_path(database_url: str) -> str | None:
    """Extract a local SQLite file path from a SQLAlchemy database URL when possible."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    return database_url.removeprefix(prefix).replace("/", "\\")


def main() -> None:
    """Run the YouTube-only debug flow and print JSON output."""
    args = parse_args()
    result = asyncio.run(
        _run(
            keyword=args.keyword,
            language=args.language,
            limit=args.limit,
            store=args.store,
            proxy=args.proxy,
            headless=args.headless,
            artifact_dir=args.artifact_dir,
            verbose=args.verbose,
        )
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
