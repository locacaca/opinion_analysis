"""YouTube transcript spider implementation with keyword search."""

from __future__ import annotations

import asyncio
from datetime import datetime
import random
import re
import time
from typing import Any, Sequence

import aiohttp
from pytube import YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from ..config import get_optional_env, get_required_env, load_env_file
from ..models import OpinionRecord, SpiderRequest
from .base import BaseSpider


class YouTubeTranscriptSpider(BaseSpider[dict[str, Any]]):
    """Collects YouTube transcripts for videos discovered by keyword or explicit IDs."""

    source_name = "youtube"

    def __init__(self) -> None:
        """Initialize retry and pacing settings for YouTube collection."""
        self._api_max_retries = _get_int_env("YOUTUBE_API_MAX_RETRIES", default=2)
        self._metadata_max_retries = _get_int_env(
            "YOUTUBE_METADATA_MAX_RETRIES",
            default=2,
        )
        self._transcript_max_retries = _get_int_env(
            "YOUTUBE_TRANSCRIPT_MAX_RETRIES",
            default=3,
        )
        self._enable_pytube_fallback = _get_bool_env(
            "YOUTUBE_ENABLE_PYTUBE_FALLBACK",
            default=True,
        )
        self._skip_shorts = _get_bool_env("YOUTUBE_SKIP_SHORTS", default=False)
        self._user_agent = _get_validated_user_agent()

    async def fetch(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Fetch transcripts asynchronously from the YouTube transcript API."""
        video_details, raw_data = await self._collect_video_details_and_transcripts(request)
        if not video_details:
            raise RuntimeError(
                "YouTube search returned zero videos. "
                "Try a broader keyword or disable strict time/caption filters."
            )
        records = _build_opinion_records_from_youtube_items(
            keyword=request.keyword,
            video_details=video_details,
            transcript_items=raw_data,
        )
        if not records:
            failure_details = [
                {
                    "video_id": item.get("video_id"),
                    "title": item.get("title"),
                    "error": item.get("transcript_error", "unknown transcript error"),
                }
                for item in video_details[:5]
            ]
            raise RuntimeError(
                "YouTube search returned videos, but no usable records were built. "
                f"sample_failures={failure_details}"
            )
        return records

    async def debug_collect(self, request: SpiderRequest) -> dict[str, Any]:
        """Return detailed search and transcript debug information for YouTube only."""
        video_details, raw_data = await self._collect_video_details_and_transcripts(request)
        transcript_map = {
            str(item.get("video_id")): item
            for item in raw_data
            if isinstance(item, dict) and item.get("video_id")
        }
        transcript_failures = [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "author": item.get("channel_title"),
                "error": item.get("transcript_error"),
                "transcript_debug": item.get("transcript_debug"),
            }
            for item in video_details
            if item.get("transcript_error")
        ]
        metadata_failures = [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "author": item.get("channel_title"),
                "error": item.get("metadata_warning"),
            }
            for item in video_details
            if item.get("metadata_warning") and not _has_sufficient_metadata(item)
        ]
        metadata_warnings = [
            {
                "video_id": item.get("video_id"),
                "title": item.get("title"),
                "author": item.get("channel_title"),
                "error": item.get("metadata_warning"),
                "metadata_source": item.get("metadata_source"),
            }
            for item in video_details
            if item.get("metadata_warning")
        ]
        return {
            "search_result_count": len(video_details),
            "transcript_success_count": len(raw_data),
            "videos": [
                {
                    "video_id": item.get("video_id"),
                    "video_url": item.get("video_url")
                    or f"https://www.youtube.com/watch?v={item.get('video_id')}",
                    "has_transcript": str(item.get("video_id")) in transcript_map,
                    "transcript_text": transcript_map.get(str(item.get("video_id")), {}).get(
                        "content"
                    ),
                    "transcript_language": transcript_map.get(
                        str(item.get("video_id")),
                        {},
                    ).get("language"),
                    "transcript_segment_count": transcript_map.get(
                        str(item.get("video_id")),
                        {},
                    ).get("segment_count"),
                    "title": item.get("title"),
                    "author": item.get("channel_title"),
                    "description": item.get("description"),
                    "publish_date": item.get("publish_date"),
                    "views": item.get("views"),
                    "length_seconds": item.get("length_seconds"),
                    "thumbnail_url": item.get("thumbnail_url"),
                    "metadata_source": item.get("metadata_source"),
                    "metadata_warning": item.get("metadata_warning"),
                    "transcript_debug": item.get("transcript_debug"),
                }
                for item in video_details
            ],
            "transcript_failures": transcript_failures,
            "metadata_failures": metadata_failures,
            "metadata_warnings": metadata_warnings,
        }

    async def _collect_video_details_and_transcripts(
        self,
        request: SpiderRequest,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect YouTube video metadata and transcripts for a request."""
        video_ids = request.extra_params.get("video_ids", [])
        strict_captions_only = bool(request.extra_params.get("strict_captions_only", False))
        if video_ids and not isinstance(video_ids, list):
            raise TypeError("request.extra_params['video_ids'] must be a list[str].")

        if video_ids:
            video_details = [
                {
                    "video_id": str(video_id),
                    "title": "",
                    "channel_title": "",
                    "keyword": request.keyword,
                    "requested_language": str(request.extra_params.get("language", "en")),
                }
                for video_id in video_ids[: request.limit]
            ]
        else:
            video_details = await self._search_videos(
                keyword=request.keyword,
                limit=request.limit,
                published_after=str(request.extra_params.get("published_after", "")),
                language=str(request.extra_params.get("language", "")),
                strict_captions_only=strict_captions_only,
            )

        video_details = await asyncio.to_thread(self._enrich_video_details, video_details)
        raw_data: list[dict[str, Any]] = await asyncio.to_thread(
            self._fetch_transcripts,
            video_details,
        )
        return video_details, raw_data

    def clean_data(self, raw_data: Sequence[dict[str, Any]]) -> list[OpinionRecord]:
        """Normalize transcript payloads into opinion records."""
        return [
            _build_single_opinion_record_from_youtube_item(item)
            for item in raw_data
        ]

    async def _search_videos(
        self,
        *,
        keyword: str,
        limit: int,
        published_after: str,
        language: str,
        strict_captions_only: bool,
    ) -> list[dict[str, Any]]:
        """Search YouTube videos for a keyword using the YouTube Data API."""
        load_env_file()
        api_key = get_required_env("YOUTUBE_DATA_API_KEY")
        proxy_url = _get_proxy_url()
        search_results: list[dict[str, Any]] = []
        seen_video_ids: set[str] = set()
        next_page_token = ""
        page_count = 0
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            while len(search_results) < limit:
                page_count += 1
                params = {
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "order": "relevance",
                    "maxResults": str(max(1, min(50, limit - len(search_results)))),
                    "key": api_key,
                }
                if strict_captions_only:
                    params["videoCaption"] = "closedCaption"
                if published_after:
                    params["publishedAfter"] = published_after
                if language:
                    params["relevanceLanguage"] = language
                if next_page_token:
                    params["pageToken"] = next_page_token

                payload = await self._request_json_with_retries(
                    session=session,
                    url="https://www.googleapis.com/youtube/v3/search",
                    params=params,
                    proxy_url=proxy_url,
                    stage="api",
                    max_retries=self._api_max_retries,
                )

                items = payload.get("items", [])
                if not isinstance(items, list) or not items:
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    snippet = item.get("snippet", {})
                    resource_id = item.get("id", {})
                    video_id = resource_id.get("videoId")
                    if not isinstance(video_id, str) or not video_id:
                        continue
                    if video_id in seen_video_ids:
                        continue
                    seen_video_ids.add(video_id)
                    search_results.append(
                        {
                            "video_id": video_id,
                            "video_url": f"https://www.youtube.com/watch?v={video_id}",
                            "title": str(snippet.get("title", "")),
                            "channel_title": str(snippet.get("channelTitle", "")),
                            "keyword": keyword,
                            "requested_language": language or "en",
                            "description": str(snippet.get("description", "")),
                            "publish_date": snippet.get("publishedAt"),
                            "views": None,
                            "length_seconds": None,
                            "thumbnail_url": _extract_thumbnail_url(
                                snippet.get("thumbnails", {})
                            ),
                            "metadata_source": "youtube_search_api",
                        }
                    )
                    if len(search_results) >= limit:
                        break

                next_page_token = str(payload.get("nextPageToken", "")).strip()
                if not next_page_token or page_count >= 5:
                    break

        results = search_results[:limit]
        if results:
            if self._skip_shorts:
                results = [item for item in results if not _looks_like_short(item)]
            video_metadata: dict[str, dict[str, Any]] = {}
            for batch_start in range(0, len(results), 50):
                batch_ids = [
                    str(item["video_id"])
                    for item in results[batch_start : batch_start + 50]
                ]
                video_metadata.update(
                    await self._fetch_video_metadata_batch(
                        api_key=api_key,
                        video_ids=batch_ids,
                        proxy_url=proxy_url,
                    )
                )
            for item in results:
                metadata = video_metadata.get(str(item["video_id"]), {})
                if not metadata:
                    continue
                item["title"] = str(metadata.get("title") or item.get("title", ""))
                item["channel_title"] = str(
                    metadata.get("channel_title") or item.get("channel_title", "")
                )
                item["description"] = str(
                    metadata.get("description") or item.get("description", "")
                )
                item["publish_date"] = metadata.get("publish_date") or item.get(
                    "publish_date"
                )
                item["views"] = metadata.get("views", item.get("views"))
                item["length_seconds"] = metadata.get(
                    "length_seconds",
                    item.get("length_seconds"),
                )
                item["thumbnail_url"] = str(
                    metadata.get("thumbnail_url") or item.get("thumbnail_url", "")
                )
                item["metadata_source"] = "youtube_videos_api"
        return results

    async def _fetch_video_metadata_batch(
        self,
        *,
        api_key: str,
        video_ids: list[str],
        proxy_url: str,
    ) -> dict[str, dict[str, Any]]:
        """Fetch video metadata in batch using the YouTube Data API videos endpoint."""
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = await self._request_json_with_retries(
                session=session,
                url="https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(video_ids),
                    "key": api_key,
                    "maxResults": str(len(video_ids)),
                },
                proxy_url=proxy_url,
                stage="api",
                max_retries=self._api_max_retries,
            )

        metadata_map: dict[str, dict[str, Any]] = {}
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("id", "")).strip()
            if not video_id:
                continue
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})
            metadata_map[video_id] = {
                "title": str(snippet.get("title", "")),
                "channel_title": str(snippet.get("channelTitle", "")),
                "description": str(snippet.get("description", "")),
                "publish_date": snippet.get("publishedAt"),
                "views": _parse_view_count(statistics.get("viewCount")),
                "length_seconds": _parse_iso8601_duration(
                    str(content_details.get("duration", ""))
                ),
                "thumbnail_url": _extract_thumbnail_url(snippet.get("thumbnails", {})),
            }
        return metadata_map

    def _enrich_video_details(self, video_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enrich search results with pytube metadata."""
        proxies = _build_proxy_dict()
        enriched: list[dict[str, Any]] = []
        for item in video_details:
            enriched_item = dict(item)
            video_url = str(item.get("video_url") or f"https://www.youtube.com/watch?v={item['video_id']}")
            enriched_item["video_url"] = video_url
            if _has_sufficient_metadata(enriched_item):
                enriched.append(enriched_item)
                continue
            if not self._enable_pytube_fallback:
                enriched.append(enriched_item)
                continue
            try:
                video, _ = self._call_with_retries(
                    max_retries=self._metadata_max_retries,
                    operation=lambda: YouTube(video_url, proxies=proxies),
                )
                enriched_item["title"] = video.title or item.get("title", "")
                enriched_item["description"] = video.description or ""
                enriched_item["channel_title"] = video.author or item.get("channel_title", "")
                enriched_item["publish_date"] = (
                    video.publish_date.isoformat()
                    if isinstance(video.publish_date, datetime)
                    else str(video.publish_date) if video.publish_date else None
                )
                enriched_item["views"] = video.views
                enriched_item["length_seconds"] = video.length
                enriched_item["thumbnail_url"] = video.thumbnail_url or ""
                enriched_item["metadata_source"] = "pytube"
            except Exception as exc:
                enriched_item["metadata_warning"] = str(exc)
            enriched.append(enriched_item)
        return enriched

    def _fetch_transcripts(self, video_details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute the blocking transcript fetch calls."""
        collected: list[dict[str, Any]] = []
        for item in video_details:
            video_id = item["video_id"]
            if self._skip_shorts and _looks_like_short(item):
                item["transcript_error"] = "Skipped likely short-form video to reduce rate-limit risk."
                continue
            try:
                _sleep_before_transcript_request()
                transcript_payload = self._fetch_transcript_payload(
                    video_id=video_id,
                    requested_language=str(item.get("requested_language", "en")),
                )
            except Exception as exc:
                item["transcript_error"] = str(exc)
                continue

            item["transcript_debug"] = {
                "selected_language": transcript_payload["selected_language"],
                "is_generated": transcript_payload["is_generated"],
                "available_transcript_languages": transcript_payload[
                    "available_transcript_languages"
                ],
                "attempt_count": transcript_payload["attempt_count"],
            }

            transcript_text = transcript_payload["content"]
            title = str(item.get("title", "")).strip()
            description = str(item.get("description", "")).strip()
            content = (
                f"{title}\n\n{description}\n\n{transcript_text}".strip()
                if (title or description) and transcript_text
                else transcript_text or title or description
            )
            if not content:
                item["transcript_error"] = "Transcript fetched but content was empty."
                continue
            collected.append(
                {
                    "video_id": video_id,
                    "video_url": item.get("video_url")
                    or f"https://www.youtube.com/watch?v={video_id}",
                    "keyword": item["keyword"],
                    "author": item.get("channel_title"),
                    "title": item.get("title"),
                    "language": transcript_payload["language"],
                    "segment_count": transcript_payload["segment_count"],
                    "content": content,
                    "transcript_text": transcript_text,
                    "transcript_origin": transcript_payload["origin"],
                    "selected_language": transcript_payload["selected_language"],
                    "is_generated": transcript_payload["is_generated"],
                    "available_transcript_languages": transcript_payload[
                        "available_transcript_languages"
                    ],
                    "description": description,
                    "publish_date": item.get("publish_date"),
                    "views": item.get("views"),
                    "length_seconds": item.get("length_seconds"),
                    "thumbnail_url": item.get("thumbnail_url"),
                }
            )
        return collected

    def _fetch_transcript_payload(
        self,
        *,
        video_id: str,
        requested_language: str,
    ) -> dict[str, Any]:
        """Fetch transcript text using the direct get_transcript helper."""
        preferred_languages = _preferred_transcript_languages(requested_language)

        try:
            fetched, attempt_count = self._call_with_retries(
                max_retries=self._transcript_max_retries,
                operation=lambda: YouTubeTranscriptApi.get_transcript(
                    video_id,
                    languages=preferred_languages,
                    proxies=_build_proxy_dict(),
                    preserve_formatting=False,
                ),
            )
        except NoTranscriptFound as exc:
            raise RuntimeError(
                f"No usable transcript was found for video {video_id}."
            ) from exc
        except TranscriptsDisabled as exc:
            raise RuntimeError(f"Transcripts are disabled for video {video_id}.") from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch transcript for video {video_id}: {exc}"
            ) from exc

        if not fetched:
            raise RuntimeError(
                f"Transcript request succeeded but returned no entries for video {video_id}."
            )

        return _build_transcript_payload(
            fetched,
            origin="get_transcript",
            selected_language=requested_language,
            is_generated=None,
            available_transcript_languages=preferred_languages,
            attempt_count=attempt_count,
        )

    async def _request_json_with_retries(
        self,
        *,
        session: aiohttp.ClientSession,
        url: str,
        params: dict[str, str],
        proxy_url: str,
        stage: str,
        max_retries: int,
    ) -> dict[str, Any]:
        """Fetch JSON from YouTube APIs with bounded retries and no forced base sleep."""
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 2):
            try:
                async with session.get(
                    url,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": self._user_agent,
                    },
                    proxy=proxy_url,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
                return dict(payload)
            except Exception as exc:
                last_error = exc
                if attempt > max_retries or not _is_retryable_error(exc):
                    raise
                _sleep_after_retryable_failure(exc, attempt=attempt, stage=stage)
        raise RuntimeError(f"Failed to fetch JSON from {url}: {last_error}")

    def _call_with_retries(
        self,
        *,
        max_retries: int,
        operation: Any,
    ) -> tuple[Any, int]:
        """Run a blocking operation with bounded retries and retry-only backoff."""
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 2):
            try:
                result = operation()
                return result, attempt
            except Exception as exc:
                last_error = exc
                if attempt > max_retries or not _is_retryable_error(exc):
                    raise
                _sleep_after_retryable_failure(exc, attempt=attempt, stage="blocking")
        raise RuntimeError(f"blocking request failed: {last_error}")


def _preferred_transcript_languages(requested_language: str) -> list[str]:
    """Build a prioritized transcript language list."""
    if requested_language == "zh":
        return ["zh-Hans", "zh-Hant", "zh", "en"]
    return ["en", "en-US", "en-GB", "zh", "zh-Hans"]


def _build_transcript_payload(
    fetched: Any,
    *,
    origin: str,
    selected_language: str | None,
    is_generated: bool | None,
    available_transcript_languages: list[str],
    attempt_count: int,
) -> dict[str, Any]:
    """Convert a fetched transcript object into normalized text payload."""
    snippets = [
        str(snippet.get("text", "")).strip()
        for snippet in fetched
        if isinstance(snippet, dict) and str(snippet.get("text", "")).strip()
    ]
    return {
        "language": selected_language,
        "segment_count": len(fetched),
        "content": " ".join(snippets).strip(),
        "origin": origin,
        "selected_language": selected_language,
        "is_generated": is_generated,
        "available_transcript_languages": available_transcript_languages,
        "attempt_count": attempt_count,
    }


def _build_opinion_records_from_youtube_items(
    *,
    keyword: str,
    video_details: list[dict[str, Any]],
    transcript_items: list[dict[str, Any]],
) -> list[OpinionRecord]:
    """Build one normalized opinion record per YouTube video, with transcript fallback."""
    transcript_map = {
        str(item.get("video_id")): item
        for item in transcript_items
        if isinstance(item, dict) and item.get("video_id")
    }
    records: list[OpinionRecord] = []
    for item in video_details:
        if not isinstance(item, dict):
            continue
        transcript_item = transcript_map.get(str(item.get("video_id")))
        records.append(
            _build_single_opinion_record_from_youtube_video(
                keyword=keyword,
                video_item=item,
                transcript_item=transcript_item,
            )
        )
    return records


def _build_single_opinion_record_from_youtube_video(
    *,
    keyword: str,
    video_item: dict[str, Any],
    transcript_item: dict[str, Any] | None,
) -> OpinionRecord:
    """Build a normalized opinion record from video metadata plus optional transcript."""
    video_id = str(video_item.get("video_id") or "").strip()
    video_url = str(video_item.get("video_url") or f"https://www.youtube.com/watch?v={video_id}")
    title = str(video_item.get("title") or "").strip()
    description = str(video_item.get("description") or "").strip()
    transcript_text = (
        str(transcript_item.get("transcript_text") or transcript_item.get("content") or "").strip()
        if transcript_item
        else ""
    )
    content = "\n\n".join(
        part for part in (title, transcript_text, description) if part
    ).strip()
    if not content:
        content = title or description or video_id or "youtube_video"

    transcript_language = transcript_item.get("language") if transcript_item else None
    transcript_segment_count = transcript_item.get("segment_count") if transcript_item else None
    transcript_origin = transcript_item.get("transcript_origin") if transcript_item else None
    selected_language = transcript_item.get("selected_language") if transcript_item else None
    is_generated = transcript_item.get("is_generated") if transcript_item else None
    available_languages = (
        transcript_item.get("available_transcript_languages") if transcript_item else None
    )

    return {
        "source": "youtube",
        "keyword": keyword,
        "content": content,
        "author": str(video_item.get("channel_title")) if video_item.get("channel_title") else None,
        "original_link": video_url,
        "metadata": {
            "keyword": keyword,
            "publish_date": video_item.get("publish_date"),
            "video_id": video_id,
            "video_url": video_url,
            "has_transcript": bool(transcript_text),
            "title": video_item.get("title"),
            "description_text": video_item.get("description"),
            "transcript_text": transcript_text or None,
            "description": video_item.get("description"),
            "language": transcript_language,
            "segment_count": transcript_segment_count,
            "views": video_item.get("views"),
            "length_seconds": video_item.get("length_seconds"),
            "thumbnail_url": video_item.get("thumbnail_url"),
            "metadata_source": video_item.get("metadata_source"),
            "transcript_origin": transcript_origin,
            "selected_language": selected_language,
            "is_generated": is_generated,
            "available_transcript_languages": available_languages,
            "transcript_missing": not bool(transcript_text),
        },
    }


def _build_single_opinion_record_from_youtube_item(item: dict[str, Any]) -> OpinionRecord:
    """Build a normalized opinion record from a transcript-bearing YouTube item."""
    return _build_single_opinion_record_from_youtube_video(
        keyword=str(item.get("keyword", "")),
        video_item=item,
        transcript_item=item,
    )


def _extract_thumbnail_url(thumbnails: Any) -> str:
    """Extract the best available thumbnail URL from a YouTube API thumbnails payload."""
    if not isinstance(thumbnails, dict):
        return ""
    for key in ("maxres", "standard", "high", "medium", "default"):
        candidate = thumbnails.get(key, {})
        if isinstance(candidate, dict):
            url = str(candidate.get("url", "")).strip()
            if url:
                return url
    return ""


def _parse_view_count(value: Any) -> int | None:
    """Parse the YouTube view count field into an integer."""
    if value is None:
        return None
    string_value = str(value).strip()
    return int(string_value) if string_value.isdigit() else None


def _parse_iso8601_duration(value: str) -> int | None:
    """Convert YouTube ISO-8601 duration strings like PT1H2M3S to seconds."""
    match = re.fullmatch(
        r"PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        value.strip(),
    )
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def _has_sufficient_metadata(item: dict[str, Any]) -> bool:
    """Return whether the record already has enough metadata to skip pytube enrichment."""
    return bool(
        str(item.get("title", "")).strip()
        and str(item.get("channel_title", "")).strip()
        and str(item.get("description", "")).strip()
        and item.get("publish_date")
        and item.get("views") is not None
        and item.get("length_seconds") is not None
        and str(item.get("thumbnail_url", "")).strip()
    )


def _looks_like_short(item: dict[str, Any]) -> bool:
    """Return whether a YouTube result is likely a short-form video."""
    title = str(item.get("title", "")).casefold()
    description = str(item.get("description", "")).casefold()
    length_seconds = item.get("length_seconds")
    return "#shorts" in title or "#shorts" in description or (
        isinstance(length_seconds, int) and length_seconds <= 90
    )


def _get_proxy_url() -> str:
    """Return the configured proxy URL for YouTube-related requests."""
    load_env_file()
    return str(
        get_optional_env("YOUTUBE_PROXY_URL")
        or get_optional_env("HTTPS_PROXY")
        or get_optional_env("HTTP_PROXY")
        or "http://127.0.0.1:7890"
    )


def _build_proxy_dict() -> dict[str, str]:
    """Build a proxies mapping for libraries that expect requests-style proxies."""
    proxy_url = _get_proxy_url()
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def _get_validated_user_agent() -> str:
    """Return a validated desktop browser user agent string."""
    configured = (get_optional_env("YOUTUBE_USER_AGENT") or "").strip()
    if _is_valid_user_agent(configured):
        return configured
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )


def _is_valid_user_agent(value: str) -> bool:
    """Apply a minimal sanity check to a configured user agent string."""
    if len(value) < 40:
        return False
    required_tokens = ("Mozilla/5.0", "AppleWebKit", "Safari")
    if not all(token in value for token in required_tokens):
        return False
    blocked_tokens = ("python-requests", "aiohttp", "curl/", "wget/")
    return not any(token.casefold() in value.casefold() for token in blocked_tokens)


def _get_int_env(name: str, *, default: int) -> int:
    """Read an integer environment variable with fallback."""
    value = get_optional_env(name)
    if value is None:
        return default
    try:
        return max(0, int(value))
    except ValueError:
        return default


def _get_bool_env(name: str, *, default: bool) -> bool:
    """Read a boolean environment variable with fallback."""
    value = get_optional_env(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _is_retryable_error(exc: Exception) -> bool:
    """Return whether an error looks transient and worth retrying."""
    message = str(exc).casefold()
    retryable_signals = (
        "429",
        "too many requests",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "remote end closed connection",
        "server disconnected",
        "bad gateway",
        "service unavailable",
        "internal server error",
        "http error 403",
        "forbidden",
    )
    return any(signal in message for signal in retryable_signals)


def _sleep_before_transcript_request() -> None:
    """Add a short random pause only before transcript requests."""
    time.sleep(random.uniform(0.8, 1.8))


def _sleep_after_retryable_failure(exc: Exception, *, attempt: int, stage: str) -> None:
    """Sleep briefly after retryable failures, with a larger pause for 429s."""
    message = str(exc).casefold()
    if "429" in message or "too many requests" in message:
        base_delay = min(12.0, 2.5 * attempt)
    elif "403" in message or "forbidden" in message:
        base_delay = min(6.0, 1.5 * attempt)
    else:
        base_delay = min(4.0, 0.8 * attempt)
    jitter = random.uniform(0.2, 0.9)
    time.sleep(base_delay + jitter)
