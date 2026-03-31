"""Map-reduce style opinion analysis for unstructured social media text."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Sequence

from ..cleaning import clean_comment_text, looks_like_noise
from ..storage import StoredOpinionRecord
from .llm_client import OpenAICompatibleLLMClient
from .models import (
    AnalysisChunkResult,
    ControversyPoint,
    OpinionAnalysisResult,
    RecordAnalysisResult,
)

CHUNK_SIZE = 10
MAX_COMMENT_LENGTH = 800


@dataclass(slots=True)
class CleanTextResult:
    """Stores preprocessed comments before they enter the LLM pipeline."""

    retained_comments: list[str]
    discarded_count: int


class OpinionAnalyzer:
    """Analyzes large batches of unstructured comments with a map-reduce pipeline."""

    def __init__(self, client: OpenAICompatibleLLMClient | None = None) -> None:
        """Initialize the analyzer with a configurable async LLM client."""
        self._client = client or OpenAICompatibleLLMClient()

    async def analyze(self, comments: Sequence[str]) -> OpinionAnalysisResult:
        """Clean comments, summarize in chunks, and aggregate the final analysis."""
        clean_result = self._clean_comments(comments)
        if not clean_result.retained_comments:
            return {
                "sentiment_score": 50,
                "summary": "No reliable opinion text remained after filtering spam, ads, and gibberish.",
                "controversy_points": [],
                "retained_comment_count": 0,
                "discarded_comment_count": clean_result.discarded_count,
                "chunk_summaries": [],
                "record_sentiments": [],
            }

        chunks = _chunk_comments(clean_result.retained_comments, CHUNK_SIZE)
        tasks = [
            asyncio.create_task(self._analyze_chunk(chunk_index=index, comments=chunk))
            for index, chunk in enumerate(chunks, start=1)
        ]
        chunk_results = await asyncio.gather(*tasks)
        final_result = await self._reduce_results(
            chunk_results=chunk_results,
            retained_comment_count=len(clean_result.retained_comments),
            discarded_comment_count=clean_result.discarded_count,
        )
        return final_result

    async def analyze_records(
        self,
        *,
        keyword: str,
        records: Sequence[StoredOpinionRecord],
    ) -> OpinionAnalysisResult:
        """Analyze stored source records one by one, then aggregate the final result."""
        normalized_records = _prepare_record_inputs(keyword=keyword, records=records)
        if not normalized_records:
            return {
                "sentiment_score": 50,
                "summary": "No reliable source records were available for analysis.",
                "controversy_points": [],
                "retained_comment_count": 0,
                "discarded_comment_count": 0,
                "chunk_summaries": [],
                "record_sentiments": [],
            }

        record_tasks = [
            asyncio.create_task(
                self._analyze_record(
                    record_index=index,
                    keyword=keyword,
                    record=record,
                )
            )
            for index, record in enumerate(normalized_records, start=1)
        ]
        record_sentiments = await asyncio.gather(*record_tasks)
        chunk_results = _record_sentiments_to_chunk_results(record_sentiments)
        final_result = await self._reduce_record_results(
            keyword=keyword,
            records=normalized_records,
            record_sentiments=record_sentiments,
            chunk_results=chunk_results,
        )
        return final_result

    def _clean_comments(self, comments: Sequence[str]) -> CleanTextResult:
        """Remove ads, bots, gibberish, duplicates, and empty text."""
        retained_comments: list[str] = []
        discarded_count = 0
        seen_normalized: set[str] = set()
        for comment in comments:
            normalized = _normalize_comment(comment)
            if not normalized:
                discarded_count += 1
                continue
            dedupe_key = normalized.casefold()
            if dedupe_key in seen_normalized:
                discarded_count += 1
                continue
            if _looks_like_noise(normalized):
                discarded_count += 1
                continue
            seen_normalized.add(dedupe_key)
            retained_comments.append(normalized[:MAX_COMMENT_LENGTH])
        return CleanTextResult(
            retained_comments=retained_comments,
            discarded_count=discarded_count,
        )

    async def _analyze_chunk(
        self,
        *,
        chunk_index: int,
        comments: Sequence[str],
    ) -> AnalysisChunkResult:
        """Run the map-stage analysis for a single chunk of comments."""
        system_prompt = (
            "You are an opinion analysis engine. "
            "You must return strict JSON only. "
            "Ignore obvious spam, promotions, bot noise, and meaningless text. "
            "Sentiment score must be an integer from 0 to 100 where 0 is highly negative, "
            "50 is neutral, and 100 is highly positive. "
            "Return exactly this JSON shape: "
            '{"sentiment_score": 0, "summary": "", "controversy_points": [{"title": "", "summary": ""}], "retained_count": 0}.'
        )
        comment_lines = "\n".join(
            f"{index}. {comment}" for index, comment in enumerate(comments, start=1)
        )
        user_prompt = (
            f"Analyze chunk #{chunk_index} containing up to {CHUNK_SIZE} social-media comments.\n"
            "Tasks:\n"
            "1. Produce one concise summary.\n"
            "2. Estimate an overall sentiment score from 0 to 100.\n"
            "3. Extract up to 3 controversy points representing the main disagreements.\n"
            "4. Set retained_count to the number of comments that contain meaningful opinions.\n\n"
            f"Comments:\n{comment_lines}"
        )
        raw_result = await self._client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return _normalize_chunk_result(raw_result=raw_result, chunk_index=chunk_index)

    async def _analyze_record(
        self,
        *,
        record_index: int,
        keyword: str,
        record: dict[str, str],
    ) -> RecordAnalysisResult:
        """Analyze one source record and return a strict per-record sentiment result."""
        system_prompt = (
            "You are a public-opinion analyst. "
            "You must return strict JSON only. "
            "Evaluate one source item for sentiment toward the target keyword. "
            "Sentiment score must be an integer from 0 to 100 where 0 is strongly negative, "
            "50 is neutral, and 100 is strongly positive. "
            "Return exactly this JSON shape: "
            '{"sentiment_score": 0, "sentiment_label": "", "reasoning": ""}.'
        )
        user_prompt = (
            f"Target keyword: {keyword}\n"
            f"Source: {record['source']}\n"
            f"Title: {record['title']}\n"
            f"Description: {record['description']}\n"
            f"Transcript: {record['transcript_text']}\n"
            f"Raw content: {record['content']}\n"
            f"Original URL: {record['original_link']}\n\n"
            "Task:\n"
            "1. Judge this single record's sentiment toward the keyword.\n"
            "2. Output one integer sentiment_score from 0 to 100.\n"
            "3. Output a short sentiment_label.\n"
            "4. Output one concise reasoning sentence.\n"
            "5. Focus on the attitude expressed in this record only."
        )
        raw_result = await self._client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return {
            "record_index": record_index,
            "source": record["source"],
            "title": record["title"],
            "original_link": record["original_link"],
            "sentiment_score": _clamp_score(raw_result.get("sentiment_score")),
            "sentiment_label": _safe_text(
                raw_result.get("sentiment_label"),
                fallback="Neutral",
            ),
            "reasoning": _safe_text(raw_result.get("reasoning"), fallback=""),
        }

    async def _reduce_results(
        self,
        *,
        chunk_results: Sequence[AnalysisChunkResult],
        retained_comment_count: int,
        discarded_comment_count: int,
    ) -> OpinionAnalysisResult:
        """Aggregate chunk summaries into a final opinion-analysis result."""
        system_prompt = (
            "You are an opinion aggregation engine. "
            "You must return strict JSON only. "
            "Merge intermediate analysis results into a final result. "
            "Return exactly this JSON shape: "
            '{"sentiment_score": 0, "summary": "", "controversy_points": [{"title": "", "summary": ""}]}.'
        )
        user_prompt = (
            "Aggregate the following intermediate opinion-analysis results.\n"
            "Requirements:\n"
            "1. Output one final sentiment score from 0 to 100.\n"
            "2. Output exactly 3 major controversy points when enough evidence exists, otherwise fewer.\n"
            "3. Remove duplicates and merge semantically similar points.\n"
            "4. Generate a concise summary suitable for a frontend overview card.\n\n"
            f"Intermediate results:\n{json.dumps(list(chunk_results), ensure_ascii=False, indent=2)}"
        )
        raw_result = await self._client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return _normalize_final_result(
            raw_result=raw_result,
            retained_comment_count=retained_comment_count,
            discarded_comment_count=discarded_comment_count,
            chunk_results=list(chunk_results),
            record_sentiments=[],
        )

    async def _reduce_record_results(
        self,
        *,
        keyword: str,
        records: Sequence[dict[str, str]],
        record_sentiments: Sequence[RecordAnalysisResult],
        chunk_results: Sequence[AnalysisChunkResult],
    ) -> OpinionAnalysisResult:
        """Aggregate per-record sentiment results into frontend-ready output."""
        system_prompt = (
            "You are an opinion aggregation engine. "
            "You must return strict JSON only. "
            "Use the provided source records and their per-record sentiment judgments to summarize public debate. "
            "Return exactly this JSON shape: "
            '{"summary": "", "controversy_points": [{"title": "", "summary": "", "link": ""}]}.'
        )
        user_prompt = (
            f"Target keyword: {keyword}\n\n"
            "Summarize the current round of collected source records.\n"
            "Requirements:\n"
            "1. Write one concise overall summary.\n"
            "2. Extract exactly 3 major public controversy points when enough evidence exists.\n"
            "3. Each controversy point must include title, summary, and a supporting link from the provided records.\n"
            "4. Base the summary on the source data and per-record sentiment judgments.\n\n"
            f"Per-record sentiments:\n{json.dumps(list(record_sentiments), ensure_ascii=False, indent=2)}\n\n"
            f"Source records:\n{json.dumps(list(records), ensure_ascii=False, indent=2)}"
        )
        raw_result = await self._client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        average_sentiment = _average_sentiment_score(record_sentiments)
        final_result = _normalize_final_result(
            raw_result=raw_result,
            retained_comment_count=len(records),
            discarded_comment_count=0,
            chunk_results=list(chunk_results),
            record_sentiments=list(record_sentiments),
            sentiment_override=average_sentiment,
        )
        final_result["summary"] = _ensure_summary(
            existing_summary=final_result["summary"],
            keyword=keyword,
            average_sentiment=average_sentiment,
            record_count=len(records),
        )
        final_result["controversy_points"] = _ensure_record_controversy_points(
            existing_points=final_result["controversy_points"],
            records=records,
            record_sentiments=record_sentiments,
        )
        return final_result


async def analyze_opinions(comments: Sequence[str]) -> OpinionAnalysisResult:
    """Convenience function for running map-reduce opinion analysis."""
    analyzer = OpinionAnalyzer()
    return await analyzer.analyze(comments)


def _chunk_comments(comments: Sequence[str], chunk_size: int) -> list[list[str]]:
    """Split comments into fixed-size chunks."""
    return [list(comments[index : index + chunk_size]) for index in range(0, len(comments), chunk_size)]


def _normalize_comment(comment: str) -> str:
    """Normalize whitespace and strip control-like clutter from a comment."""
    return clean_comment_text(comment)


def _looks_like_noise(comment: str) -> bool:
    """Apply simple heuristics to remove spammy, bot-like, or corrupted comments."""
    return looks_like_noise(comment)


def _normalize_chunk_result(
    *,
    raw_result: dict[str, object],
    chunk_index: int,
) -> AnalysisChunkResult:
    """Coerce the chunk-stage model output into a stable JSON contract."""
    return {
        "chunk_index": chunk_index,
        "sentiment_score": _clamp_score(raw_result.get("sentiment_score")),
        "summary": _safe_text(raw_result.get("summary"), fallback=""),
        "controversy_points": _normalize_controversy_points(raw_result.get("controversy_points"), limit=3),
        "retained_count": _safe_int(raw_result.get("retained_count"), default=0),
    }


def _normalize_final_result(
    *,
    raw_result: dict[str, object],
    retained_comment_count: int,
    discarded_comment_count: int,
    chunk_results: list[AnalysisChunkResult],
    record_sentiments: list[RecordAnalysisResult],
    sentiment_override: int | None = None,
) -> OpinionAnalysisResult:
    """Coerce the reduce-stage model output into the final frontend contract."""
    return {
        "sentiment_score": sentiment_override
        if sentiment_override is not None
        else _clamp_score(raw_result.get("sentiment_score")),
        "summary": _safe_text(raw_result.get("summary"), fallback=""),
        "controversy_points": _normalize_controversy_points(raw_result.get("controversy_points"), limit=3),
        "retained_comment_count": retained_comment_count,
        "discarded_comment_count": discarded_comment_count,
        "chunk_summaries": chunk_results,
        "record_sentiments": record_sentiments,
    }


def _normalize_controversy_points(
    raw_value: object,
    *,
    limit: int,
) -> list[ControversyPoint]:
    """Normalize controversy points to a fixed JSON list."""
    if not isinstance(raw_value, list):
        return []
    normalized: list[ControversyPoint] = []
    for item in raw_value[:limit]:
        if not isinstance(item, dict):
            continue
        title = _safe_text(item.get("title"), fallback="")
        summary = _safe_text(item.get("summary"), fallback="")
        link = _safe_text(item.get("link"), fallback="")
        if not title and not summary:
            continue
        normalized.append({"title": title, "summary": summary, "link": link})
    return normalized


def _prepare_record_inputs(
    *,
    keyword: str,
    records: Sequence[StoredOpinionRecord],
) -> list[dict[str, str]]:
    """Build normalized per-record analysis inputs from stored records."""
    prepared: list[dict[str, str]] = []
    for record in records:
        metadata = dict(record.metadata or {})
        title = _safe_text(metadata.get("title"), fallback="")
        description = _safe_text(
            metadata.get("description_text") or metadata.get("description"),
            fallback="",
        )
        transcript_text = _safe_text(metadata.get("transcript_text"), fallback="")
        content = _safe_text(record.content, fallback="")
        if not any((title, description, transcript_text, content)):
            continue
        prepared.append(
            {
                "keyword": keyword,
                "source": record.source,
                "title": title or content[:120],
                "description": description,
                "transcript_text": transcript_text[:4000],
                "content": content[:4000],
                "original_link": record.original_link,
            }
        )
    return prepared


def _average_sentiment_score(record_sentiments: Sequence[RecordAnalysisResult]) -> int:
    """Compute the average sentiment score across all analyzed records."""
    if not record_sentiments:
        return 50
    total = sum(item["sentiment_score"] for item in record_sentiments)
    return round(total / len(record_sentiments))


def _ensure_summary(
    *,
    existing_summary: str,
    keyword: str,
    average_sentiment: int,
    record_count: int,
) -> str:
    """Provide a deterministic fallback summary when the LLM omits one."""
    if existing_summary.strip():
        return existing_summary.strip()
    tone = "mostly positive" if average_sentiment >= 60 else "mixed" if average_sentiment >= 40 else "mostly negative"
    return (
        f"Collected {record_count} source records about {keyword}. "
        f"Overall discussion appears {tone}, with sentiment averaging {average_sentiment}/100."
    )


def _ensure_record_controversy_points(
    *,
    existing_points: Sequence[ControversyPoint],
    records: Sequence[dict[str, str]],
    record_sentiments: Sequence[RecordAnalysisResult],
) -> list[ControversyPoint]:
    """Guarantee up to three frontend-ready controversy cards."""
    normalized_existing = list(existing_points[:3])
    if len(normalized_existing) >= 3:
        return normalized_existing

    seen_keys = {
        f"{item.get('title', '').strip().casefold()}|{item.get('summary', '').strip().casefold()}"
        for item in normalized_existing
    }
    fallback_points: list[ControversyPoint] = []
    records_by_link = {
        record["original_link"]: record for record in records if record.get("original_link")
    }
    ranked_sentiments = sorted(
        record_sentiments,
        key=lambda item: (abs(item["sentiment_score"] - 50), item["record_index"]),
        reverse=True,
    )

    for sentiment in ranked_sentiments:
        if len(normalized_existing) + len(fallback_points) >= 3:
            break
        title = _safe_text(sentiment.get("title"), fallback="")
        reasoning = _safe_text(sentiment.get("reasoning"), fallback="")
        link = _safe_text(sentiment.get("original_link"), fallback="")
        related_record = records_by_link.get(link, {})
        description = _safe_text(related_record.get("description"), fallback="")
        source = _safe_text(sentiment.get("source"), fallback="source")
        summary = reasoning or description or f"Representative {source} discussion item."
        point_title = title or f"{source.title()} discussion"
        dedupe_key = f"{point_title.strip().casefold()}|{summary.strip().casefold()}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        fallback_points.append(
            {
                "title": point_title[:80],
                "summary": summary[:240],
                "link": link,
            }
        )

    return normalized_existing + fallback_points


def _record_sentiments_to_chunk_results(
    record_sentiments: Sequence[RecordAnalysisResult],
) -> list[AnalysisChunkResult]:
    """Expose per-record sentiment judgments in the existing chunk summary field."""
    chunk_results: list[AnalysisChunkResult] = []
    for item in record_sentiments:
        chunk_results.append(
            {
                "chunk_index": item["record_index"],
                "sentiment_score": item["sentiment_score"],
                "summary": item["reasoning"],
                "controversy_points": [],
                "retained_count": 1,
            }
        )
    return chunk_results


def _clamp_score(raw_value: object) -> int:
    """Clamp a raw sentiment score into the required 0-100 range."""
    return max(0, min(100, _safe_int(raw_value, default=50)))


def _safe_int(raw_value: object, *, default: int) -> int:
    """Convert a raw object into an integer with fallback behavior."""
    if isinstance(raw_value, bool):
        return default
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped)
    return default


def _safe_text(raw_value: object, *, fallback: str) -> str:
    """Convert a raw object into a stripped string with fallback behavior."""
    if not isinstance(raw_value, str):
        return fallback
    return raw_value.strip() or fallback
