"""Keyword-driven orchestration for collection and analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Iterable

from .analysis import OpinionAnalyzer
from .cleaning import clean_opinion_records
from .config import get_optional_env, load_env_file
from .models import OpinionRecord, SpiderRequest
from .spiders import BaseSpider, RedditSpider, XSearchSpider, YouTubeTranscriptSpider
from .storage import OpinionStorage, StoredOpinionRecord


async def analyze_keyword(
    keyword: str,
    *,
    limit_per_source: int = 15,
    sources: list[str] | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Collect multi-source records for a keyword and return dashboard-ready JSON."""
    monitor = _create_monitor(keyword=keyword, language=language, mode="analyze")
    storage = OpinionStorage()
    await asyncio.to_thread(storage.initialize)
    _append_monitor_stage(monitor, "storage_initialized")
    run_id = await asyncio.to_thread(storage.create_run, keyword, language)
    _append_monitor_stage(monitor, "run_created", run_id=run_id)
    source_errors: dict[str, str] = {}
    discarded_count = 0

    try:
        normalized_sources = _normalize_sources(sources)
        _append_monitor_stage(monitor, "sources_selected", sources=normalized_sources)
        spiders = _build_spiders(normalized_sources)

        request = SpiderRequest(
            keyword=keyword,
            limit=limit_per_source,
            extra_params=_build_recent_window_params(
                language=language,
                recent_only=True,
                strict_captions_only=False,
            ),
        )
        batches = await asyncio.gather(
            *[_collect_from_spider(spider, request) for spider in spiders]
        )
        _append_monitor_stage(monitor, "collection_completed")

        all_records: list[OpinionRecord] = []
        raw_count_by_source: dict[str, int] = {}
        for source_name, records, error in batches:
            all_records.extend(records)
            raw_count_by_source[source_name] = len(records)
            if error:
                source_errors[source_name] = error
        _append_monitor_stage(
            monitor,
            "records_collected",
            raw_record_count=len(all_records),
            raw_count_by_source=raw_count_by_source,
            source_errors=source_errors,
        )

        clean_result = clean_opinion_records(all_records)
        discarded_count = clean_result.discarded_count
        _append_monitor_stage(
            monitor,
            "records_cleaned",
            retained_record_count=len(clean_result.records),
            discarded_record_count=discarded_count,
        )

        stored_count = await asyncio.to_thread(
            storage.save_cleaned_records,
            run_id=run_id,
            records=clean_result.records,
        )
        stored_records = await asyncio.to_thread(storage.load_run_records, run_id)
        _append_monitor_stage(
            monitor,
            "records_stored",
            stored_record_count=stored_count,
            database_read_count=len(stored_records),
        )

        analyzer = OpinionAnalyzer()
        _append_monitor_stage(
            monitor,
            "llm_analysis_started",
            llm_record_count=len(stored_records),
        )
        analysis_result = await analyzer.analyze_records(
            keyword=keyword,
            records=stored_records,
        )
        _append_monitor_stage(
            monitor,
            "llm_analysis_completed",
            sentiment_score=analysis_result["sentiment_score"],
            controversy_point_count=len(analysis_result["controversy_points"]),
            record_sentiment_count=len(analysis_result.get("record_sentiments", [])),
        )

        posts = [_to_post_payload(record) for record in stored_records]
        controversy_points = analysis_result["controversy_points"]
        for index, point in enumerate(controversy_points):
            if "link" not in point and index < len(posts):
                point["link"] = posts[index]["original_link"]

        heat_score = _compute_heat_score(stored_records)
        source_breakdown = _build_source_breakdown(stored_records)
        await asyncio.to_thread(
            storage.complete_run,
            run_id=run_id,
            sentiment_score=analysis_result["sentiment_score"],
            heat_score=heat_score,
            summary=analysis_result["summary"],
            retained_count=stored_count,
            discarded_count=discarded_count,
            source_breakdown=source_breakdown,
            source_errors=source_errors,
        )
        _append_monitor_stage(
            monitor,
            "response_ready",
            heat_score=heat_score,
            post_count=len(posts),
            source_breakdown=source_breakdown,
        )
        _finalize_monitor(monitor, status="completed")

        return {
            "run_id": run_id,
            "keyword": keyword,
            "language": language,
            "selected_sources": normalized_sources,
            "sentiment_score": analysis_result["sentiment_score"],
            "heat_score": heat_score,
            "summary": analysis_result["summary"],
            "controversy_points": controversy_points,
            "posts": posts,
            "retained_comment_count": stored_count,
            "discarded_comment_count": discarded_count,
            "source_breakdown": source_breakdown,
            "source_errors": source_errors,
            "chunk_summaries": analysis_result["chunk_summaries"],
            "record_sentiments": analysis_result.get("record_sentiments", []),
            "monitor": monitor,
        }
    except Exception as exc:
        await asyncio.to_thread(
            storage.fail_run,
            run_id=run_id,
            source_errors=source_errors,
            failure_reason=str(exc),
            discarded_count=discarded_count,
        )
        _append_monitor_stage(
            monitor,
            "failed",
            error=str(exc),
            source_errors=source_errors,
        )
        _finalize_monitor(monitor, status="failed")
        raise


async def collect_and_store_keyword(
    keyword: str,
    *,
    language: str = "en",
    limit_per_source: int = 50,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Collect source data, clean it, and store it without calling the LLM."""
    normalized_language = _normalize_language(language)
    normalized_sources = _normalize_sources(sources)
    monitor = _create_monitor(
        keyword=keyword,
        language=normalized_language,
        mode="collect_only",
    )

    storage = OpinionStorage()
    await asyncio.to_thread(storage.initialize)
    _append_monitor_stage(monitor, "storage_initialized")
    run_id = await asyncio.to_thread(storage.create_run, keyword, normalized_language)
    _append_monitor_stage(monitor, "run_created", run_id=run_id)
    source_errors: dict[str, str] = {}
    discarded_count = 0

    try:
        spiders = _build_spiders(normalized_sources)
        _append_monitor_stage(monitor, "sources_selected", sources=normalized_sources)
        request = SpiderRequest(
            keyword=keyword,
            limit=limit_per_source,
            extra_params=_build_recent_window_params(
                language=normalized_language,
                recent_only=False,
                strict_captions_only=False,
            ),
        )
        batches = await asyncio.gather(
            *[_collect_from_spider(spider, request) for spider in spiders]
        )
        _append_monitor_stage(monitor, "collection_completed")

        raw_records: list[OpinionRecord] = []
        raw_count_by_source: dict[str, int] = {}
        for source_name, records, error in batches:
            raw_records.extend(records)
            raw_count_by_source[source_name] = len(records)
            if error:
                source_errors[source_name] = error
        _append_monitor_stage(
            monitor,
            "records_collected",
            raw_record_count=len(raw_records),
            raw_count_by_source=raw_count_by_source,
            source_errors=source_errors,
        )

        clean_result = clean_opinion_records(raw_records)
        discarded_count = clean_result.discarded_count
        _append_monitor_stage(
            monitor,
            "records_cleaned",
            retained_record_count=len(clean_result.records),
            discarded_record_count=discarded_count,
        )

        stored_count = await asyncio.to_thread(
            storage.save_cleaned_records,
            run_id=run_id,
            records=clean_result.records,
        )
        stored_records = await asyncio.to_thread(storage.load_run_records, run_id)
        source_breakdown = _build_source_breakdown(stored_records)
        _append_monitor_stage(
            monitor,
            "records_stored",
            stored_record_count=stored_count,
            source_breakdown=source_breakdown,
        )

        await asyncio.to_thread(
            storage.mark_run_collected,
            run_id=run_id,
            retained_count=stored_count,
            discarded_count=discarded_count,
            source_breakdown=source_breakdown,
            source_errors=source_errors,
        )
        _append_monitor_stage(monitor, "response_ready", record_count=len(stored_records))
        _finalize_monitor(monitor, status="completed")

        return {
            "run_id": run_id,
            "keyword": keyword,
            "language": normalized_language,
            "selected_sources": normalized_sources,
            "raw_record_count": len(raw_records),
            "stored_record_count": stored_count,
            "discarded_record_count": discarded_count,
            "raw_count_by_source": raw_count_by_source,
            "stored_count_by_source": source_breakdown,
            "source_errors": source_errors,
            "records": [_to_post_payload(record) for record in stored_records],
            "monitor": monitor,
        }
    except Exception as exc:
        await asyncio.to_thread(
            storage.fail_run,
            run_id=run_id,
            source_errors=source_errors,
            failure_reason=str(exc),
            discarded_count=discarded_count,
        )
        _append_monitor_stage(
            monitor,
            "failed",
            error=str(exc),
            source_errors=source_errors,
        )
        _finalize_monitor(monitor, status="failed")
        raise


async def _collect_from_spider(
    spider: BaseSpider[Any],
    request: SpiderRequest,
) -> tuple[str, list[OpinionRecord], str | None]:
    """Collect source records without letting one source failure abort the whole pipeline."""
    try:
        records = await spider.fetch(request)
        return spider.source_name, records, None
    except Exception as exc:
        return spider.source_name, [], str(exc)


def _compute_heat_score(records: Iterable[OpinionRecord | StoredOpinionRecord]) -> int:
    """Compute a heat score from record volume, source diversity, and interaction signals."""
    items = list(records)
    volume_score = min(len(items) * 10, 60)
    diversity_score = min(
        len({_get_record_source(item) for item in items}) * 10,
        20,
    )
    interaction_total = sum(_get_record_interaction_count(item) for item in items)
    interaction_score = min(_log_scaled(interaction_total) * 4, 20)
    return max(0, min(100, round(volume_score + diversity_score + interaction_score)))


def _build_source_breakdown(
    records: Iterable[OpinionRecord | StoredOpinionRecord],
) -> dict[str, int]:
    """Count normalized records by source for frontend display."""
    breakdown: dict[str, int] = {}
    for record in records:
        source = _get_record_source(record)
        breakdown[source] = breakdown.get(source, 0) + 1
    return breakdown


def _to_post_payload(record: StoredOpinionRecord) -> dict[str, str]:
    """Convert a stored record into the frontend post payload."""
    title = str(record.metadata.get("title", "")).strip() if record.metadata else ""
    return {
        "source": record.source,
        "title": title or _truncate(record.content, limit=120),
        "content": _truncate(record.content, limit=240),
        "author": record.author or "Unknown",
        "original_link": record.original_link,
    }


def _get_record_source(record: OpinionRecord | StoredOpinionRecord) -> str:
    """Return a normalized source name from either transient or stored records."""
    if isinstance(record, StoredOpinionRecord):
        return record.source
    return str(record.get("source", "unknown"))


def _get_record_interaction_count(record: OpinionRecord | StoredOpinionRecord) -> int:
    """Estimate interaction volume from stored metadata fields such as views."""
    metadata: dict[str, Any]
    if isinstance(record, StoredOpinionRecord):
        metadata = dict(record.metadata or {})
    else:
        metadata = dict(record.get("metadata", {}) or {})
    return _safe_int(metadata.get("views"))


def _safe_int(value: object) -> int:
    """Parse a non-negative integer from loosely typed metadata."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _log_scaled(value: int) -> int:
    """Map large interaction counts into a compact display-oriented score."""
    if value <= 0:
        return 0
    magnitude = len(str(value))
    return min(5, max(1, magnitude))


def _truncate(value: str, *, limit: int) -> str:
    """Trim long strings for frontend list presentation."""
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 3].rstrip()}..."


def _build_recent_window_params(
    *,
    language: str,
    recent_only: bool,
    strict_captions_only: bool,
) -> dict[str, str | bool]:
    """Build source filters for either recent-only analysis or broader debug collection."""
    params: dict[str, str | bool] = {
        "language": _normalize_language(language),
        "strict_captions_only": strict_captions_only,
    }
    if recent_only:
        load_env_file()
        lookback_days = _safe_recent_window_days(
            get_optional_env("YOUTUBE_LOOKBACK_DAYS"),
            default=7,
        )
        published_after = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
        params["time_filter"] = "week" if lookback_days > 1 else "day"
        params["published_after"] = published_after
    return params


def _safe_recent_window_days(value: str | None, *, default: int) -> int:
    """Parse a bounded recent-window size in days."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(1, min(parsed, 30))


def _normalize_sources(sources: list[str] | None) -> list[str]:
    """Normalize requested source names and apply defaults."""
    if not sources:
        return ["youtube"]

    allowed = {"reddit", "youtube", "x"}
    normalized = []
    seen: set[str] = set()
    for source in sources:
        lowered = source.strip().lower()
        if lowered in allowed and lowered not in seen:
            seen.add(lowered)
            normalized.append(lowered)
    if not normalized:
        raise ValueError("At least one source must be selected.")
    return normalized


def _normalize_language(language: str) -> str:
    """Normalize supported language codes for collection debugging."""
    lowered = language.strip().lower()
    if lowered not in {"en", "zh"}:
        raise ValueError("language must be either 'en' or 'zh'.")
    return lowered


def _build_spiders(sources: list[str]) -> list[BaseSpider[Any]]:
    """Instantiate spiders only for the selected sources."""
    spiders: list[BaseSpider[Any]] = []
    for source in sources:
        if source == "reddit":
            spiders.append(RedditSpider())
        elif source == "youtube":
            spiders.append(YouTubeTranscriptSpider())
        elif source == "x":
            spiders.append(XSearchSpider())
    return spiders


def _create_monitor(*, keyword: str, language: str, mode: str) -> dict[str, Any]:
    """Create a backend monitor payload for one pipeline run."""
    started_at = datetime.now(timezone.utc)
    return {
        "mode": mode,
        "keyword": keyword,
        "language": language,
        "status": "running",
        "started_at": started_at.isoformat(),
        "duration_ms": 0,
        "_started_perf": time.perf_counter(),
        "stages": [],
    }


def _append_monitor_stage(
    monitor: dict[str, Any],
    stage: str,
    **details: Any,
) -> None:
    """Append one timestamped monitor stage."""
    print(f"[TrendPulse][{monitor.get('mode', 'pipeline')}] {stage}: {details}")
    stages = monitor.setdefault("stages", [])
    if isinstance(stages, list):
        stages.append(
            {
                "stage": stage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details,
            }
        )


def _finalize_monitor(monitor: dict[str, Any], *, status: str) -> None:
    """Finalize monitor timing fields before returning the response."""
    started_perf = monitor.pop("_started_perf", None)
    duration_ms = 0
    if isinstance(started_perf, (int, float)):
        duration_ms = round((time.perf_counter() - float(started_perf)) * 1000)
    monitor["status"] = status
    monitor["duration_ms"] = duration_ms
    monitor["finished_at"] = datetime.now(timezone.utc).isoformat()
