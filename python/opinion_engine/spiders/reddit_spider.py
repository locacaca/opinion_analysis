"""Reddit search spider using old.reddit.com pagination."""

from __future__ import annotations

import asyncio
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Page, async_playwright

from ..cleaning import looks_like_noise
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


class RedditSearchSpider(BaseSpider[dict[str, Any]]):
    """Collect Reddit posts through old.reddit.com result pagination."""

    source_name = "reddit"

    def __init__(
        self,
        proxy: str | None = None,
        headless: bool = True,
        slow_mode: bool = True,
    ) -> None:
        """Configure the browser-backed Reddit search spider."""
        self.base_url = "https://old.reddit.com"
        self.proxy = proxy or os.getenv("REDDIT_PROXY") or os.getenv("HTTPS_PROXY")
        self.headless = headless
        self.slow_mode = slow_mode

    async def fetch(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Fetch Reddit posts by traversing paginated search result pages."""
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
        """Normalize paginated old Reddit search results."""
        cleaned: list[OpinionRecord] = []
        for item in raw_data:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            cleaned.append(
                {
                    "source": "reddit",
                    "keyword": str(item.get("keyword", "")).strip(),
                    "content": content,
                    "author": _clean_optional_text(item.get("author")),
                    "original_link": str(item.get("original_link", "")).strip(),
                    "metadata": {
                        "title": _clean_optional_text(item.get("title")),
                        "subreddit": _clean_optional_text(item.get("subreddit")),
                        "publish_date": _clean_optional_text(item.get("publish_date")),
                        "score": item.get("score"),
                        "num_comments": item.get("num_comments"),
                        "comments_text": _clean_optional_text(item.get("comments_text")),
                        "fetch_error": _clean_optional_text(item.get("fetch_error")),
                    },
                }
            )
        return cleaned

    async def debug_collect(self, request: SpiderRequest) -> dict[str, Any]:
        """Return debug JSON for a keyword search using paginated results."""
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
            "posts": raw_items,
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
        """Walk old Reddit search result pages until enough posts are collected."""
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
            context, page = await self._create_context_and_page(browser)

            try:
                next_url = initial_url
                page_index = 0
                max_page_error_retries = 3
                while next_url and len(collected) < limit:
                    if collection_deadline_epoch and time.time() >= collection_deadline_epoch:
                        collection_error = (
                            "Reddit collection stopped because the shared collection "
                            "deadline was reached."
                        )
                        break
                    page_index += 1
                    attempt = 0
                    page_error: str | None = None
                    navigation_error: str | None = None
                    final_url = ""
                    response_status: int | None = None
                    result_count_on_page = 0
                    next_page_candidate = ""
                    load_elapsed_ms = 0
                    while True:
                        attempt += 1
                        navigation_error = None
                        started_at = time.perf_counter()
                        try:
                            response = await page.goto(
                                next_url,
                                wait_until="domcontentloaded",
                                timeout=45000,
                            )
                            await page.wait_for_timeout(
                                _human_delay_ms(self.slow_mode, 1200, 2200)
                            )
                        except Exception as exc:
                            response_status = None
                            final_url = page.url
                            navigation_error = str(exc)
                            page_error = f"navigation failed: {exc}"
                        else:
                            response_status = response.status if response is not None else None
                            final_url = page.url
                            page_error = await self._extract_page_error(page)
                        load_elapsed_ms = int((time.perf_counter() - started_at) * 1000)

                        if not page_error:
                            rows = page.locator("div.search-result")
                            result_count_on_page = await rows.count()
                            next_page_candidate = await self._extract_next_page_url(page) or ""
                        else:
                            result_count_on_page = 0
                            next_page_candidate = ""

                        if debug_artifact_dir:
                            page_artifact = await self._save_search_page_artifacts(
                                page=page,
                                artifact_dir=debug_artifact_dir,
                                page_index=page_index,
                                page_url=next_url,
                                page_error=page_error,
                                retry_attempt=attempt,
                                final_url=final_url,
                                response_status=response_status,
                                navigation_error=navigation_error,
                                result_count_on_page=result_count_on_page,
                                next_page_url=next_page_candidate,
                                load_elapsed_ms=load_elapsed_ms,
                            )
                            search_pages.append(page_artifact)

                        if not page_error:
                            break
                        if attempt >= max_page_error_retries:
                            collection_error = (
                                "Reddit search page returned an error state after "
                                f"{attempt} attempts: {page_error}"
                            )
                            if raise_on_page_error:
                                raise RuntimeError(collection_error)
                            next_url = None
                            break

                        await page.close()
                        await context.close()
                        await asyncio.sleep(random.uniform(3.0, 6.0))
                        context, page = await self._create_context_and_page(browser)

                    if collection_error:
                        break

                    page_items = await self._extract_result_page(
                        page=page,
                        keyword=keyword,
                    )
                    for item in page_items:
                        link = str(item.get("original_link", "")).strip()
                        if not link or link in seen_links:
                            continue
                        seen_links.add(link)
                        collected.append(item)
                        if len(collected) >= limit:
                            break

                    if len(collected) >= limit:
                        break

                    next_url = next_page_candidate or await self._extract_next_page_url(page)
                    await page.wait_for_timeout(_human_delay_ms(self.slow_mode, 1600, 3200))

            finally:
                await context.close()
                await browser.close()

        return collected[:limit], search_pages, collection_error

    async def _create_context_and_page(self, browser: Any) -> tuple[Any, Page]:
        """Create a fresh browser context and page for one Reddit search session."""
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1440, "height": 1024},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await context.add_cookies(
            [
                {
                    "name": "over18",
                    "value": "1",
                    "domain": ".reddit.com",
                    "path": "/",
                }
            ]
        )
        page = await context.new_page()
        return context, page

    def _build_search_url(self, *, keyword: str, language: str) -> str:
        """Build the stable old.reddit search URL."""
        normalized_keyword = " ".join(part for part in keyword.strip().split() if part)
        encoded_keyword = quote_plus(normalized_keyword or keyword)
        return (
            f"{self.base_url}/search?q={encoded_keyword}"
            "&restrict_sr=&sort=hot&t=all"
        )

    async def _extract_page_error(self, page: Page) -> str | None:
        """Detect explicit old Reddit error states."""
        page_text = (await page.locator("body").inner_text()).strip().lower()
        error_signals = (
            "server error",
            "try again later",
            "you've been blocked",
            "whoa there, pardner",
            "our cdn was unable to reach our servers",
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
        """Extract post summaries from one old Reddit result page."""
        results: list[dict[str, Any]] = []
        rows = page.locator("div.search-result")
        row_count = await rows.count()
        for index in range(row_count):
            row = rows.nth(index)
            title = await _safe_inner_text(row.locator("a.search-title").first)
            snippet = await _safe_inner_text(row.locator("div.search-result-body").first)
            original_link = await _safe_attribute(
                row.locator("a.search-comments").first,
                "href",
            )
            subreddit = await _safe_inner_text(row.locator("a.search-subreddit-link").first)
            author = await _safe_inner_text(row.locator("a.author").first)
            publish_date = await _safe_attribute(
                row.locator("time").first,
                "datetime",
            )
            score_text = await _safe_inner_text(row.locator("span.search-score").first)
            comments_text = await _safe_inner_text(
                row.locator("a.search-comments").first,
            )
            body = await _safe_inner_text(row.locator("div.search-expando div.md").first)
            if not body:
                body = snippet

            if not original_link:
                continue
            if _looks_like_promoted_result(
                title=title,
                snippet=snippet,
                author=author,
                subreddit=subreddit,
            ):
                continue
            if not _matches_keyword_on_search_result(
                keyword=keyword,
                title=title,
                snippet=snippet,
                subreddit=subreddit,
            ):
                continue

            normalized_link = self._normalize_reddit_url(original_link)
            detail_content = await self._fetch_post_detail(
                page=page,
                url=normalized_link,
                fallback_title=title,
                fallback_body=body or snippet,
            )
            content = str(detail_content.get("content") or body or snippet or title).strip()
            if not _matches_keyword_strict(
                keyword=keyword,
                title=title,
                snippet=snippet,
                content=content,
                subreddit=subreddit,
            ):
                continue

            results.append(
                {
                    "keyword": keyword,
                    "title": title,
                    "author": author,
                    "subreddit": subreddit,
                    "publish_date": publish_date,
                    "score": _extract_first_int(score_text),
                    "num_comments": _extract_first_int(comments_text),
                    "original_link": normalized_link,
                    "content": content[:4000],
                    "comments_text": str(detail_content.get("comments_text") or "")[:2000],
                    "fetch_error": detail_content["fetch_error"],
                }
            )
        return results

    async def _extract_next_page_url(self, page: Page) -> str | None:
        """Extract the next result-page URL from old Reddit pagination."""
        href = await _safe_attribute(page.locator("span.next-button a").first, "href")
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
        retry_attempt: int,
        final_url: str,
        response_status: int | None,
        navigation_error: str | None,
        result_count_on_page: int,
        next_page_url: str,
        load_elapsed_ms: int,
    ) -> dict[str, str]:
        """Persist one search-result page as screenshot and HTML for inspection."""
        os.makedirs(artifact_dir, exist_ok=True)
        suffix = f"_retry_{retry_attempt}" if retry_attempt > 1 else ""
        screenshot_path = os.path.join(
            artifact_dir,
            f"search_page_{page_index:02d}{suffix}.png",
        )
        html_path = os.path.join(
            artifact_dir,
            f"search_page_{page_index:02d}{suffix}.html",
        )
        await page.screenshot(path=screenshot_path, full_page=True)
        html = await page.content()
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html)
        return {
            "page_index": str(page_index),
            "retry_attempt": str(retry_attempt),
            "page_url": page_url,
            "final_url": final_url,
            "response_status": str(response_status) if response_status is not None else "",
            "navigation_error": navigation_error or "",
            "load_elapsed_ms": str(load_elapsed_ms),
            "result_count_on_page": str(result_count_on_page),
            "next_page_url": next_page_url,
            "screenshot_path": screenshot_path,
            "html_path": html_path,
            "page_error": page_error or "",
        }

    async def _fetch_post_detail(
        self,
        *,
        page: Page,
        url: str,
        fallback_title: str,
        fallback_body: str,
    ) -> dict[str, str | None]:
        """Visit one old Reddit comments page and extract post body plus comments."""
        fetch_error: str | None = None
        content = ""
        comments_text = ""
        try:
            detail_page = await page.context.new_page()
            try:
                await detail_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await detail_page.wait_for_timeout(_human_delay_ms(self.slow_mode, 1000, 1800))
                page_error = await self._extract_page_error(detail_page)
                if page_error:
                    return {
                        "content": fallback_body or fallback_title,
                        "comments_text": None,
                        "fetch_error": page_error,
                    }

                text_candidates = [
                    "div.thing.link div.expando div.usertext-body div.md",
                    "div.thing.link div.usertext-body div.md",
                    "div.entry div.usertext-body div.md",
                    "div.top-matter + div.usertext-body div.md",
                ]
                for selector in text_candidates:
                    locator = detail_page.locator(selector).first
                    candidate = await _safe_inner_text(locator)
                    if candidate:
                        content = candidate
                        break
                comments_text = await self._extract_comment_snippets(detail_page)
            finally:
                await detail_page.close()
        except Exception as exc:
            fetch_error = str(exc)

        return {
            "content": content.strip() or fallback_body.strip() or fallback_title.strip(),
            "comments_text": comments_text.strip() or None,
            "fetch_error": fetch_error,
        }

    async def _extract_comment_snippets(self, page: Page) -> str:
        """Collect a short excerpt of useful top comments from a Reddit thread."""
        comment_bodies = page.locator("div.commentarea div.thing.comment div.usertext-body div.md")
        count = await comment_bodies.count()
        snippets: list[str] = []
        char_budget = 1400
        line_budget = 100
        max_comments = 5
        for index in range(count):
            if len(snippets) >= max_comments or char_budget <= 0 or line_budget <= 0:
                break
            text = await _safe_inner_text(comment_bodies.nth(index))
            normalized = _clean_optional_text(text)
            if not normalized:
                continue
            lowered = normalized.casefold()
            if lowered in {"[deleted]", "[removed]"}:
                continue
            if looks_like_noise(normalized):
                continue
            clipped = normalized[: min(len(normalized), char_budget)]
            line_count = max(1, len([line for line in clipped.splitlines() if line.strip()]))
            if line_count > line_budget:
                clipped_lines = [line for line in clipped.splitlines() if line.strip()]
                clipped = "\n".join(clipped_lines[:line_budget]).strip()
                line_count = max(
                    1,
                    len([line for line in clipped.splitlines() if line.strip()]),
                )
            if not clipped:
                continue
            snippets.append(clipped)
            char_budget -= len(clipped)
            line_budget -= line_count
        return "\n\n".join(snippets)

    def _normalize_reddit_url(self, value: str) -> str:
        """Normalize to old Reddit post URLs for stable detail fetches."""
        normalized = value.strip()
        normalized = normalized.replace("https://www.reddit.com", self.base_url)
        normalized = normalized.replace("https://reddit.com", self.base_url)
        normalized = normalized.replace("https://old.reddit.com", self.base_url)
        if normalized.startswith("/"):
            normalized = f"{self.base_url}{normalized}"
        return normalized


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


def _extract_first_int(text: str) -> int | None:
    """Extract the first integer-like value from a short UI label."""
    digits = "".join(character if character.isdigit() else " " for character in text)
    parts = [part for part in digits.split() if part]
    if not parts:
        return None
    try:
        return int(parts[0])
    except ValueError:
        return None


def _matches_keyword_on_search_result(
    *,
    keyword: str,
    title: str,
    snippet: str,
    subreddit: str,
) -> bool:
    """Require a strong keyword hit on the search-result page before detail fetch."""
    normalized_keyword = " ".join(part.casefold() for part in keyword.split() if part)
    if not normalized_keyword:
        return True

    haystacks = [
        title.casefold(),
        snippet.casefold(),
        subreddit.casefold(),
    ]
    if any(normalized_keyword in haystack for haystack in haystacks):
        return True

    keyword_tokens = [token.casefold() for token in keyword.split() if len(token.strip()) >= 2]
    if not keyword_tokens:
        return False

    token_hits = sum(
        1
        for token in keyword_tokens
        if any(token in haystack for haystack in haystacks)
    )
    return token_hits == len(keyword_tokens)


def _matches_keyword_strict(
    *,
    keyword: str,
    title: str,
    snippet: str,
    content: str,
    subreddit: str,
) -> bool:
    """Apply a strict final keyword gate after detail fetch."""
    normalized_keyword = " ".join(part.casefold() for part in keyword.split() if part)
    if not normalized_keyword:
        return True

    title_lower = title.casefold()
    snippet_lower = snippet.casefold()
    content_lower = content.casefold()
    subreddit_lower = subreddit.casefold()
    if normalized_keyword in title_lower or normalized_keyword in snippet_lower:
        return True

    keyword_tokens = [token.casefold() for token in keyword.split() if len(token.strip()) >= 2]
    if not keyword_tokens:
        return False

    title_hits = sum(1 for token in keyword_tokens if token in title_lower)
    snippet_hits = sum(1 for token in keyword_tokens if token in snippet_lower)
    content_hits = sum(1 for token in keyword_tokens if token in content_lower)
    subreddit_hits = sum(1 for token in keyword_tokens if token in subreddit_lower)

    return (
        title_hits == len(keyword_tokens)
        or snippet_hits == len(keyword_tokens)
        or (title_hits + snippet_hits) >= len(keyword_tokens)
        or (content_hits == len(keyword_tokens) and title_hits >= 1)
        or (subreddit_hits == len(keyword_tokens) and title_hits >= 1)
    )


def _looks_like_promoted_result(
    *,
    title: str,
    snippet: str,
    author: str,
    subreddit: str,
) -> bool:
    """Filter out obvious promoted/ad-like Reddit search results."""
    joined = " ".join(
        part.casefold()
        for part in (title, snippet, author, subreddit)
        if part.strip()
    )
    spam_signals = (
        "promoted",
        "sponsored",
        "udemy free courses",
        "free courses",
        "coupon",
        "discount",
        "sale",
        "deal",
        "buy now",
        "telegram",
        "whatsapp",
    )
    return any(signal in joined for signal in spam_signals)


def _human_delay_ms(slow_mode: bool, minimum: int, maximum: int) -> int:
    """Return a short randomized delay in milliseconds."""
    if not slow_mode:
        return 250
    return random.randint(minimum, maximum)


def _clean_optional_text(value: Any) -> str | None:
    """Normalize empty string values to None."""
    text = str(value).strip() if value is not None else ""
    return text or None
