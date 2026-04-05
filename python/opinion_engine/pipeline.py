"""Keyword-driven orchestration for collection and analysis."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
import time
from typing import Callable
from typing import Any, Iterable

from .analysis import OpinionAnalyzer
from .cleaning import clean_opinion_records
from .config import get_optional_env, load_env_file
from .models import OpinionRecord, SpiderRequest
from .spiders import BaseSpider, RedditSearchSpider, XSearchSpider, YouTubeTranscriptSpider
from .storage import OpinionStorage, StoredOpinionRecord


async def analyze_keyword(
    keyword: str,
    *,
    limit_per_source: int = 30,
    total_limit: int | None = None,
    sources: list[str] | None = None,
    source_weights: dict[str, str] | None = None,
    language: str = "en",
    output_language: str = "en",
    youtube_mode: str = "official_api",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Collect multi-source records for a keyword and return dashboard-ready JSON."""
    monitor = _create_monitor(
        keyword=keyword,
        language=language,
        mode="analyze",
        progress_callback=progress_callback,
    )
    _append_monitor_stage(monitor, "request_received", keyword=keyword)
    storage = OpinionStorage()
    await asyncio.to_thread(storage.initialize)
    _append_monitor_stage(monitor, "storage_initialized")
    run_id = await asyncio.to_thread(storage.create_run, keyword, language)
    _append_monitor_stage(monitor, "run_created", run_id=run_id)
    source_errors: dict[str, str] = {}
    discarded_count = 0

    try:
        normalized_sources = _normalize_sources(sources)
        normalized_youtube_mode = _normalize_youtube_mode(youtube_mode)
        _append_monitor_stage(monitor, "sources_selected", sources=normalized_sources)
        source_limits = _resolve_source_limits(
            sources=normalized_sources,
            total_limit=total_limit,
            fallback_limit_per_source=limit_per_source,
            source_weights=source_weights or {},
        )
        _append_monitor_stage(monitor, "source_limits_resolved", source_limits=source_limits)
        spiders = _build_spiders(normalized_sources)
        _append_monitor_stage(
            monitor,
            "collector_plan_ready",
            source_count=len(spiders),
            youtube_mode=normalized_youtube_mode if "youtube" in normalized_sources else None,
        )

        batches = await asyncio.gather(
            *[
                _collect_from_spider(
                    spider,
                    SpiderRequest(
                        keyword=keyword,
                        limit=source_limits.get(spider.source_name, 0),
                        extra_params={
                            **_build_recent_window_params(
                                language=language,
                                recent_only=True,
                                strict_captions_only=False,
                            ),
                            "youtube_mode": normalized_youtube_mode,
                        },
                    ),
                )
                for spider in spiders
                if source_limits.get(spider.source_name, 0) > 0
            ]
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
            retained_count_by_source=clean_result.retained_count_by_source,
            discarded_count_by_source=clean_result.discarded_count_by_source,
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
        llm_model = str(
            getattr(
                getattr(getattr(analyzer, "_client", None), "_config", None),
                "model",
                "unknown",
            )
            or "unknown"
        )
        _append_monitor_stage(
            monitor,
            "llm_analysis_started",
            llm_record_count=len(stored_records),
            llm_mode="single_pass_round_analysis",
            llm_model=llm_model,
        )
        analysis_result = await analyzer.analyze_records(
            keyword=keyword,
            records=stored_records,
            output_language=_normalize_language(output_language),
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

        _append_monitor_stage(
            monitor,
            "score_computation_started",
            stored_record_count=len(stored_records),
        )
        heat_score = _compute_heat_score(
            records=stored_records,
            record_sentiments=analysis_result.get("record_sentiments", []),
        )
        source_breakdown = _build_source_breakdown(stored_records)
        _append_monitor_stage(
            monitor,
            "score_computation_completed",
            heat_score=heat_score,
            source_breakdown=source_breakdown,
        )
        _append_monitor_stage(
            monitor,
            "run_finalization_started",
            run_id=run_id,
        )
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
            "output_language": _normalize_language(output_language),
            "selected_sources": normalized_sources,
            "youtube_mode": normalized_youtube_mode,
            "llm_model": llm_model,
            "requested_total_limit": sum(source_limits.values()),
            "source_limits": source_limits,
            "raw_count_by_source": raw_count_by_source,
            "retained_count_by_source": clean_result.retained_count_by_source,
            "discarded_count_by_source": clean_result.discarded_count_by_source,
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
    total_limit: int | None = None,
    sources: list[str] | None = None,
    source_weights: dict[str, str] | None = None,
    youtube_mode: str = "official_api",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Collect source data, clean it, and store it without calling the LLM."""
    normalized_language = _normalize_language(language)
    normalized_sources = _normalize_sources(sources)
    normalized_youtube_mode = _normalize_youtube_mode(youtube_mode)
    monitor = _create_monitor(
        keyword=keyword,
        language=normalized_language,
        mode="collect_only",
        progress_callback=progress_callback,
    )
    _append_monitor_stage(monitor, "request_received", keyword=keyword)

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
        source_limits = _resolve_source_limits(
            sources=normalized_sources,
            total_limit=total_limit,
            fallback_limit_per_source=limit_per_source,
            source_weights=source_weights or {},
        )
        _append_monitor_stage(monitor, "source_limits_resolved", source_limits=source_limits)
        batches = await asyncio.gather(
            *[
                _collect_from_spider(
                    spider,
                    SpiderRequest(
                        keyword=keyword,
                        limit=source_limits.get(spider.source_name, 0),
                        extra_params=_build_recent_window_params(
                            language=normalized_language,
                            recent_only=False,
                            strict_captions_only=False,
                        )
                        | {"youtube_mode": normalized_youtube_mode},
                    ),
                )
                for spider in spiders
                if source_limits.get(spider.source_name, 0) > 0
            ]
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
            retained_count_by_source=clean_result.retained_count_by_source,
            discarded_count_by_source=clean_result.discarded_count_by_source,
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
            "youtube_mode": normalized_youtube_mode,
            "requested_total_limit": sum(source_limits.values()),
            "source_limits": source_limits,
            "raw_record_count": len(raw_records),
            "stored_record_count": stored_count,
            "discarded_record_count": discarded_count,
            "raw_count_by_source": raw_count_by_source,
            "retained_count_by_source": clean_result.retained_count_by_source,
            "discarded_count_by_source": clean_result.discarded_count_by_source,
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


def _compute_heat_score(
    *,
    records: Sequence[OpinionRecord | StoredOpinionRecord],
    record_sentiments: Sequence[dict[str, Any]],
) -> int:
    """Compute heat from relevance and recency."""
    if not records:
        return 0

    relevance_by_link = {
        str(item.get("original_link", "")): _safe_int(item.get("relevance_score"))
        for item in record_sentiments
    }
    total_score = 0.0
    for record in records:
        link = _get_record_link(record)
        relevance = relevance_by_link.get(link, 50)
        recency_weight = _compute_recency_weight(_get_record_publish_date(record))
        total_score += (relevance / 100.0) * recency_weight

    return max(0, min(100, round(total_score * 10)))


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


def _resolve_source_limits(
    *,
    sources: list[str],
    total_limit: int | None,
    fallback_limit_per_source: int,
    source_weights: dict[str, str],
) -> dict[str, int]:
    """Allocate a total crawl budget across selected sources by weight."""
    if not sources:
        return {}

    if total_limit is None:
        per_source = max(1, min(fallback_limit_per_source, 50))
        return {source: per_source for source in sources}

    normalized_total = max(len(sources), min(total_limit, 50))
    weight_values = {
        source: _normalize_source_weight_value(source_weights.get(source))
        for source in sources
    }
    total_weight = sum(weight_values.values())
    if total_weight <= 0:
        equal_share = normalized_total // len(sources)
        remainder = normalized_total % len(sources)
        return {
            source: equal_share + (1 if index < remainder else 0)
            for index, source in enumerate(sources)
        }

    base_allocations: dict[str, int] = {}
    remainders: list[tuple[str, float]] = []
    assigned = 0
    for source in sources:
        raw_share = normalized_total * weight_values[source] / total_weight
        base_share = int(raw_share)
        base_allocations[source] = base_share
        assigned += base_share
        remainders.append((source, raw_share - base_share))

    missing = normalized_total - assigned
    for source, _ in sorted(
        remainders,
        key=lambda item: (-item[1], -weight_values[item[0]], sources.index(item[0])),
    ):
        if missing <= 0:
            break
        base_allocations[source] += 1
        missing -= 1

    for source in sources:
        if base_allocations[source] <= 0:
            donor = max(
                sources,
                key=lambda item: (base_allocations[item], weight_values[item]),
            )
            if donor != source and base_allocations[donor] > 1:
                base_allocations[donor] -= 1
                base_allocations[source] += 1

    return base_allocations


def _normalize_source_weight_value(value: str | None) -> int:
    """Map frontend weight labels into integer allocation weights."""
    lowered = (value or "").strip().lower()
    if lowered == "low":
        return 1
    if lowered == "high":
        return 3
    return 2


def _normalize_language(language: str) -> str:
    """Normalize supported language codes for collection debugging."""
    lowered = language.strip().lower()
    if lowered not in {"en", "zh"}:
        raise ValueError("language must be either 'en' or 'zh'.")
    return lowered


def _normalize_youtube_mode(value: str) -> str:
    """Normalize supported YouTube collection modes."""
    lowered = value.strip().lower()
    if lowered in {"official_api", "api"}:
        return "official_api"
    if lowered in {"headless_browser", "browser", "headless"}:
        return "headless_browser"
    raise ValueError("youtube_mode must be either 'official_api' or 'headless_browser'.")


def _safe_collection_deadline_seconds(value: str | None, *, default: int) -> int:
    """Parse a bounded collection deadline."""
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(15, min(parsed, 300))


def _build_spiders(sources: list[str]) -> list[BaseSpider[Any]]:
    """Instantiate spiders only for the selected sources."""
    load_env_file()
    spiders: list[BaseSpider[Any]] = []
    for source in sources:
        if source == "reddit":
            spiders.append(
                RedditSearchSpider(
                    proxy=get_optional_env("REDDIT_PROXY")
                    or get_optional_env("HTTPS_PROXY")
                    or get_optional_env("HTTP_PROXY"),
                    headless=_get_bool_env("REDDIT_HEADLESS", default=True),
                    slow_mode=_get_bool_env("REDDIT_SLOW_MODE", default=True),
                )
            )
        elif source == "youtube":
            spiders.append(YouTubeTranscriptSpider())
        elif source == "x":
            spiders.append(XSearchSpider())
    return spiders


def _get_bool_env(name: str, *, default: bool) -> bool:
    """Read a boolean environment variable with a conservative fallback."""
    value = get_optional_env(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


def _create_monitor(
    *,
    keyword: str,
    language: str,
    mode: str,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Create a backend monitor payload for one pipeline run."""
    started_at = datetime.now(timezone.utc)
    monitor = {
        "mode": mode,
        "keyword": keyword,
        "language": language,
        "status": "running",
        "started_at": started_at.isoformat(),
        "duration_ms": 0,
        "_started_perf": time.perf_counter(),
        "_progress_callback": progress_callback,
        "stages": [],
    }
    _emit_monitor_progress(monitor)
    return monitor


def _append_monitor_stage(
    monitor: dict[str, Any],
    stage: str,
    **details: Any,
) -> None:
    """Append one timestamped monitor stage."""
    stages = monitor.setdefault("stages", [])
    stage_index = len(stages) + 1 if isinstance(stages, list) else 1
    stage_text = _describe_monitor_stage(stage=stage, details=details)
    print(
        f"[TrendPulse][{monitor.get('mode', 'pipeline')}][{stage_index:02d}] "
        f"{stage} | {stage_text} | details={details}"
    )
    if isinstance(stages, list):
        stages.append(
            {
                "stage": stage,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details,
            }
        )
    _emit_monitor_progress(monitor)


def _finalize_monitor(monitor: dict[str, Any], *, status: str) -> None:
    """Finalize monitor timing fields before returning the response."""
    started_perf = monitor.get("_started_perf")
    duration_ms = 0
    if isinstance(started_perf, (int, float)):
        duration_ms = round((time.perf_counter() - float(started_perf)) * 1000)
    monitor["status"] = status
    monitor["duration_ms"] = duration_ms
    monitor["finished_at"] = datetime.now(timezone.utc).isoformat()
    _emit_monitor_progress(monitor)
    monitor.pop("_started_perf", None)
    monitor.pop("_progress_callback", None)


def _emit_monitor_progress(monitor: dict[str, Any]) -> None:
    """Push a sanitized monitor snapshot to an optional progress callback."""
    callback = monitor.get("_progress_callback")
    if not callable(callback):
        return
    callback(_public_monitor_snapshot(monitor))


def _public_monitor_snapshot(monitor: dict[str, Any]) -> dict[str, Any]:
    """Return a serialization-safe monitor payload."""
    return {
        key: copy.deepcopy(value)
        for key, value in monitor.items()
        if not str(key).startswith("_")
    }


def _describe_monitor_stage(*, stage: str, details: dict[str, Any]) -> str:
    """Return a concise human-readable description for console progress output."""
    source = str(details.get("source", "") or "").strip()
    if stage == "request_received":
        return "received analysis request"
    if stage == "storage_initialized":
        return "local database ready"
    if stage == "run_created":
        return f"created collection run #{details.get('run_id')}"
    if stage == "sources_selected":
        return f"selected sources: {details.get('sources')}"
    if stage == "source_limits_resolved":
        return "resolved crawl limit per source"
    if stage == "collector_plan_ready":
        return "collector plan prepared"
    if stage == "source_collection_started":
        return f"starting collection for {source}"
    if stage == "collection_completed":
        return "all selected sources finished collection"
    if stage == "records_collected":
        return "all source records collected"
    if stage == "records_cleaned":
        return "basic record cleaning finished"
    if stage == "records_stored":
        return "cleaned records stored and loaded from database"
    if stage == "llm_analysis_started":
        return "sending collected records to the model"
    if stage == "llm_analysis_completed":
        return "model returned sentiment and controversy analysis"
    if stage == "score_computation_started":
        return "computing heat and dashboard metrics"
    if stage == "score_computation_completed":
        return "heat and source breakdown ready"
    if stage == "run_finalization_started":
        return "writing final summary back into database"
    if stage == "response_ready":
        return "dashboard payload ready for frontend"
    if stage == "failed":
        return "pipeline failed"
    return stage.replace("_", " ")


def _get_record_link(record: OpinionRecord | StoredOpinionRecord) -> str:
    """Return the record link from either transient or stored records."""
    if isinstance(record, StoredOpinionRecord):
        return record.original_link
    return str(record.get("original_link", ""))


def _get_record_publish_date(record: OpinionRecord | StoredOpinionRecord) -> str:
    """Return the publish date from either transient or stored records."""
    metadata: dict[str, Any]
    if isinstance(record, StoredOpinionRecord):
        metadata = dict(record.metadata or {})
    else:
        metadata = dict(record.get("metadata", {}) or {})
    return str(metadata.get("publish_date", "") or "")


def _compute_recency_weight(publish_date: str) -> float:
    """Compute a recency weight where newer records contribute more heat."""
    parsed = _parse_publish_date(publish_date)
    if parsed is None:
        return 0.4
    age = datetime.now(timezone.utc) - parsed
    age_days = max(0.0, age.total_seconds() / 86400.0)
    if age_days <= 1:
        return 1.0
    if age_days <= 3:
        return 0.85
    if age_days <= 7:
        return 0.7
    if age_days <= 30:
        return 0.45
    return 0.2


def _parse_publish_date(value: str) -> datetime | None:
    """Parse an ISO-like publish date string into a UTC datetime."""
    normalized = value.strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
