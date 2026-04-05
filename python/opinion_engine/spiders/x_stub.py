"""X/Twitter search spider using a Nitter mirror plus Playwright."""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Sequence
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Page, async_playwright

from ..models import OpinionRecord, SpiderRequest
from .base import BaseSpider

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
]


class XSearchSpider(BaseSpider[dict[str, Any]]):
    """Collect X/Twitter posts through a public Nitter search mirror."""

    source_name = "x"

    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        slow_mode: bool = True,
        base_url: str | None = None,
    ) -> None:
        """Configure the browser-backed Nitter search spider."""
        self.base_url = (
            base_url
            or os.getenv("NITTER_BASE_URL")
            or "https://nitter.net"
        ).rstrip("/")
        self.proxy = (
            proxy
            or os.getenv("X_PROXY")
            or os.getenv("NITTER_PROXY")
            or os.getenv("HTTPS_PROXY")
        )
        self.headless = headless
        self.slow_mode = slow_mode

    async def fetch(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Fetch X posts by traversing paginated Nitter search result pages."""
        callback = request.extra_params.get("record_callback")
        deadline_epoch = float(request.extra_params.get("collection_deadline_epoch", 0) or 0)
        raw_items, _, _ = await self._collect_search_results(
            keyword=request.keyword,
            limit=request.limit,
            language=str(request.extra_params.get("language", "en")),
            debug_artifact_dir=None,
            raise_on_page_error=True,
            collection_deadline_epoch=deadline_epoch,
        )
        records = self.clean_data(raw_items)
        if callable(callback):
            for record in records:
                callback(record)
        return records

    def clean_data(self, raw_data: Sequence[dict[str, Any]]) -> list[OpinionRecord]:
        """Normalize raw Nitter result rows into shared opinion records."""
        cleaned_records: list[OpinionRecord] = []
        for item in raw_data:
            content = str(item.get("content", "")).strip()
            tweet_url = str(item.get("tweet_url", "")).strip()
            username = _clean_optional_text(item.get("username"))
            if not content or not tweet_url:
                continue
            cleaned_records.append(
                {
                    "source": "x",
                    "keyword": str(item.get("keyword", "")).strip(),
                    "content": content,
                    "author": username,
                    "original_link": tweet_url,
                    "metadata": {
                        "title": _build_title_from_content(content),
                        "tweet_id": _clean_optional_text(item.get("tweet_id")),
                        "tweet_url": tweet_url,
                        "username": username,
                        "display_name": _clean_optional_text(item.get("display_name")),
                        "publish_date": _clean_optional_text(item.get("publish_date")),
                        "language": _clean_optional_text(item.get("language")),
                        "reply_count": item.get("reply_count"),
                        "retweet_count": item.get("retweet_count"),
                        "like_count": item.get("like_count"),
                        "quote_count": item.get("quote_count"),
                        "view_count": item.get("view_count"),
                        "fetch_error": _clean_optional_text(item.get("fetch_error")),
                    },
                }
            )
        return cleaned_records

    async def debug_collect(self, request: SpiderRequest) -> dict[str, Any]:
        """Return debug JSON for a Nitter keyword search with pagination."""
        debug_artifact_dir = request.extra_params.get("debug_artifact_dir")
        raw_items, search_pages, collection_error = await self._collect_search_results(
            keyword=request.keyword,
            limit=request.limit,
            language=str(request.extra_params.get("language", "en")),
            debug_artifact_dir=str(debug_artifact_dir) if debug_artifact_dir else None,
            raise_on_page_error=False,
            collection_deadline_epoch=0.0,
        )
        return {
            "search_result_count": len(raw_items),
            "search_url": self._build_search_url(
                keyword=request.keyword,
                language=str(request.extra_params.get("language", "en")),
            ),
            "search_pages": search_pages,
            "tweets": raw_items,
            "collection_error": collection_error,
        }

    async def _collect_search_results(
        self,
        *,
        keyword: str,
        limit: int,
        language: str,
        debug_artifact_dir: str | None,
        raise_on_page_error: bool,
        collection_deadline_epoch: float,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], str | None]:
        """Walk paginated Nitter search result pages until enough posts are collected."""
        browser_proxy = {"server": self.proxy} if self.proxy else None
        initial_url = self._build_search_url(keyword=keyword, language=language)
        collected: list[dict[str, Any]] = []
        search_pages: list[dict[str, str]] = []
        seen_links: set[str] = set()
        collection_error: str | None = None

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                proxy=browser_proxy,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1440,1024",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1440, "height": 1024},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            page = await context.new_page()

            try:
                next_url = initial_url
                page_index = 0
                while next_url and len(collected) < limit:
                    if collection_deadline_epoch and time.time() >= collection_deadline_epoch:
                        collection_error = (
                            "X collection stopped because the shared collection deadline was reached."
                        )
                        break

                    page_index += 1
                    await page.goto(next_url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(_human_delay_ms(self.slow_mode, 1000, 1800))

                    page_error = await self._extract_page_error(page)
                    result_count_on_page = await page.locator("div.timeline-item").count()
                    next_page_candidate = await self._extract_next_page_url(page) or ""
                    if debug_artifact_dir:
                        page_artifact = await self._save_search_page_artifacts(
                            page=page,
                            artifact_dir=debug_artifact_dir,
                            page_index=page_index,
                            page_url=next_url,
                            page_error=page_error,
                            result_count_on_page=result_count_on_page,
                            next_page_url=next_page_candidate,
                        )
                        search_pages.append(page_artifact)
                    if page_error:
                        collection_error = f"Nitter search page returned an error state: {page_error}"
                        if raise_on_page_error:
                            raise RuntimeError(collection_error)
                        break

                    page_items = await self._extract_result_page(
                        page=page,
                        keyword=keyword,
                    )
                    for item in page_items:
                        link = str(item.get("tweet_url", "")).strip()
                        if not link or link in seen_links:
                            continue
                        seen_links.add(link)
                        collected.append(item)
                        if len(collected) >= limit:
                            break

                    if len(collected) >= limit:
                        break

                    next_url = next_page_candidate
                    await page.wait_for_timeout(_human_delay_ms(self.slow_mode, 1400, 2600))
            finally:
                await context.close()
                await browser.close()

        return collected[:limit], search_pages, collection_error

    def _build_search_url(self, *, keyword: str, language: str) -> str:
        """Build a stable Nitter search URL."""
        normalized_keyword = " ".join(part for part in keyword.strip().split() if part)
        encoded_keyword = quote_plus(normalized_keyword or keyword)
        if language.strip().lower() in {"en", "zh"}:
            return f"{self.base_url}/search?f=tweets&q={encoded_keyword}&lang={language.strip().lower()}"
        return f"{self.base_url}/search?f=tweets&q={encoded_keyword}"

    async def _extract_page_error(self, page: Page) -> str | None:
        """Detect explicit Nitter error states."""
        page_text = (await page.locator("body").inner_text()).strip().lower()
        error_signals = (
            "failed to fetch tweets",
            "this page is unavailable",
            "rate limited",
            "temporarily unavailable",
            "could not connect to twitter",
        )
        for signal in error_signals:
            if signal in page_text:
                return signal
        return None

    async def _extract_result_page(
        self,
        *,
        page: Page,
        keyword: str,
    ) -> list[dict[str, Any]]:
        """Extract tweet summaries from one Nitter result page."""
        results: list[dict[str, Any]] = []
        rows = page.locator("div.timeline-item")
        row_count = await rows.count()
        for index in range(row_count):
            row = rows.nth(index)
            content = await _safe_inner_text(row.locator("div.tweet-content").first)
            display_name = await _safe_inner_text(row.locator("a.fullname").first)
            username = await _safe_inner_text(row.locator("a.username").first)
            date_link = row.locator("span.tweet-date a").first
            tweet_path = await _safe_attribute(date_link, "href")
            publish_date = await _safe_attribute(date_link, "title")
            if not publish_date:
                publish_date = await _safe_attribute(date_link, "aria-label")

            stats = await row.locator("span.tweet-stat").all_inner_texts()
            reply_count, retweet_count, like_count = _parse_stat_triplet(stats)

            if not content or not tweet_path:
                continue
            if _looks_like_ad_or_noise(content):
                continue
            if not _matches_keyword(keyword=keyword, content=content):
                continue

            normalized_path = tweet_path.strip()
            if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
                tweet_url = normalized_path
            else:
                tweet_url = urljoin(f"{self.base_url}/", normalized_path)

            normalized_username = username.replace("@", "").strip()
            tweet_id = _extract_tweet_id(tweet_url)

            results.append(
                {
                    "keyword": keyword,
                    "tweet_id": tweet_id,
                    "tweet_url": tweet_url,
                    "username": normalized_username or None,
                    "display_name": display_name or None,
                    "content": content[:4000],
                    "publish_date": publish_date or None,
                    "language": None,
                    "reply_count": reply_count,
                    "retweet_count": retweet_count,
                    "like_count": like_count,
                    "quote_count": None,
                    "view_count": None,
                    "fetch_error": None,
                }
            )
        return results

    async def _extract_next_page_url(self, page: Page) -> str | None:
        """Extract the next result-page URL from Nitter pagination."""
        href = await _safe_attribute(page.locator("div.show-more a").first, "href")
        if not href:
            return None
        return urljoin(f"{self.base_url}/", href)

    async def _save_search_page_artifacts(
        self,
        *,
        page: Page,
        artifact_dir: str,
        page_index: int,
        page_url: str,
        page_error: str | None,
        result_count_on_page: int,
        next_page_url: str,
    ) -> dict[str, str]:
        """Persist one Nitter search-result page as screenshot and HTML for inspection."""
        os.makedirs(artifact_dir, exist_ok=True)
        screenshot_path = os.path.join(artifact_dir, f"x_search_page_{page_index:02d}.png")
        html_path = os.path.join(artifact_dir, f"x_search_page_{page_index:02d}.html")
        await page.screenshot(path=screenshot_path, full_page=True)
        html = await page.content()
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html)
        return {
            "page_index": str(page_index),
            "page_url": page_url,
            "result_count_on_page": str(result_count_on_page),
            "next_page_url": next_page_url,
            "screenshot_path": screenshot_path,
            "html_path": html_path,
            "page_error": page_error or "",
        }


async def _safe_inner_text(locator: Any) -> str:
    """Read inner text and tolerate missing nodes."""
    try:
        if await locator.count() == 0:
            return ""
        return (await locator.inner_text()).strip()
    except Exception:
        return ""


async def _safe_attribute(locator: Any, name: str) -> str:
    """Read an attribute and tolerate missing nodes."""
    try:
        if await locator.count() == 0:
            return ""
        value = await locator.get_attribute(name)
        return value.strip() if isinstance(value, str) else ""
    except Exception:
        return ""


def _parse_stat_triplet(values: list[str]) -> tuple[int | None, int | None, int | None]:
    """Parse reply/retweet/like counts from Nitter stat labels."""
    numeric_values = [_extract_first_int(item) for item in values[:3]]
    padded = numeric_values + [None] * (3 - len(numeric_values))
    return padded[0], padded[1], padded[2]


def _extract_first_int(text: str) -> int | None:
    """Extract a numeric-like value from a short label."""
    normalized = text.strip().replace(",", "")
    if not normalized:
        return None
    multiplier = 1
    lowered = normalized.casefold()
    if lowered.endswith("k"):
        multiplier = 1000
        normalized = normalized[:-1]
    elif lowered.endswith("m"):
        multiplier = 1000000
        normalized = normalized[:-1]
    digits = "".join(character if character.isdigit() or character == "." else "" for character in normalized)
    if not digits:
        return None
    try:
        return int(float(digits) * multiplier)
    except ValueError:
        return None


def _matches_keyword(*, keyword: str, content: str) -> bool:
    """Require a strong keyword hit on the tweet content."""
    normalized_keyword = " ".join(part.casefold() for part in keyword.split() if part)
    normalized_content = content.casefold()
    if not normalized_keyword:
        return True
    if normalized_keyword in normalized_content:
        return True
    keyword_tokens = [token.casefold() for token in keyword.split() if len(token.strip()) >= 2]
    if not keyword_tokens:
        return False
    return all(token in normalized_content for token in keyword_tokens)


def _looks_like_ad_or_noise(content: str) -> bool:
    """Filter out obvious spam or ad-like tweet text."""
    lowered = content.casefold()
    spam_signals = (
        "buy now",
        "discount",
        "promo code",
        "free shipping",
        "click here",
        "telegram",
        "whatsapp",
        "airdrop",
        "giveaway",
    )
    return any(signal in lowered for signal in spam_signals)


def _extract_tweet_id(tweet_url: str) -> str | None:
    """Extract the tweet identifier from a canonical status URL."""
    parts = [part for part in tweet_url.strip("/").split("/") if part]
    if not parts:
        return None
    try:
        status_index = parts.index("status")
    except ValueError:
        return None
    if status_index + 1 >= len(parts):
        return None
    return parts[status_index + 1]


def _build_title_from_content(content: str) -> str:
    """Create a compact title-like field from tweet content for frontend lists."""
    first_line = " ".join(content.strip().splitlines())
    return first_line[:120].strip()


def _human_delay_ms(slow_mode: bool, minimum: int, maximum: int) -> int:
    """Return a short randomized delay in milliseconds."""
    if not slow_mode:
        return 250
    return random.randint(minimum, maximum)


def _clean_optional_text(value: Any) -> str | None:
    """Normalize empty string values to None."""
    text = str(value).strip() if value is not None else ""
    return text or None
