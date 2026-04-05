"""Single-pass opinion analysis for stored source records."""

from __future__ import annotations

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

MAX_COMMENT_LENGTH = 800
MAX_RECORD_TEXT_LENGTH = 900
MAX_TITLE_LENGTH = 160
MAX_DESCRIPTION_LENGTH = 280
MAX_COMMENTS_LENGTH = 500


@dataclass(slots=True)
class CleanTextResult:
    """Stores preprocessed comments before they enter the LLM pipeline."""

    retained_comments: list[str]
    discarded_count: int


class OpinionAnalyzer:
    """Analyzes source records with one LLM request per collection round."""

    def __init__(self, client: OpenAICompatibleLLMClient | None = None) -> None:
        """Initialize the analyzer with a configurable async LLM client."""
        self._client = client or OpenAICompatibleLLMClient()

    async def analyze(self, comments: Sequence[str]) -> OpinionAnalysisResult:
        """Analyze plain comments with the legacy text-only path."""
        clean_result = self._clean_comments(comments)
        if not clean_result.retained_comments:
            return _empty_analysis_result(
                summary="No reliable opinion text remained after filtering spam, ads, and gibberish.",
                discarded_count=clean_result.discarded_count,
            )

        comment_records = [
            {
                "record_index": index,
                "source": "text",
                "title": f"Comment {index}",
                "description": "",
                "transcript_text": "",
                "content": comment,
                "original_link": "",
                "publish_date": "",
            }
            for index, comment in enumerate(clean_result.retained_comments, start=1)
        ]
        raw_result = await self._analyze_all_records(comment_records)
        record_sentiments = _normalize_record_sentiments(
            raw_value=raw_result.get("record_sentiments"),
            records=comment_records,
        )
        weighted_sentiment = _compute_weighted_sentiment(record_sentiments)
        return {
            "sentiment_score": weighted_sentiment,
            "summary": _ensure_summary(
                existing_summary=_safe_text(raw_result.get("summary"), fallback=""),
                keyword="the collected topic",
                sentiment_score=weighted_sentiment,
                record_count=len(comment_records),
            ),
            "controversy_points": _ensure_controversy_points(
                existing_points=_normalize_controversy_points(
                    raw_result.get("controversy_points"),
                    limit=3,
                ),
                records=comment_records,
            ),
            "retained_comment_count": len(comment_records),
            "discarded_comment_count": clean_result.discarded_count,
            "chunk_summaries": _record_sentiments_to_chunk_results(record_sentiments),
            "record_sentiments": record_sentiments,
        }

    async def analyze_records(
        self,
        *,
        keyword: str,
        records: Sequence[StoredOpinionRecord],
        output_language: str = "en",
    ) -> OpinionAnalysisResult:
        """Analyze all stored source records in one LLM request."""
        normalized_records = _prepare_record_inputs(keyword=keyword, records=records)
        if not normalized_records:
            return _empty_analysis_result(
                summary="No reliable source records were available for analysis.",
                discarded_count=0,
            )

        raw_result = await self._analyze_all_records(
            normalized_records,
            output_language=output_language,
        )
        record_sentiments = _normalize_record_sentiments(
            raw_value=raw_result.get("record_sentiments"),
            records=normalized_records,
        )
        weighted_sentiment = _compute_weighted_sentiment(record_sentiments)
        summary = _ensure_summary(
            existing_summary=_safe_text(raw_result.get("summary"), fallback=""),
            keyword=keyword,
            sentiment_score=weighted_sentiment,
            record_count=len(normalized_records),
        )
        controversy_points = _ensure_controversy_points(
            existing_points=_normalize_controversy_points(
                raw_result.get("controversy_points"),
                limit=3,
            ),
            records=normalized_records,
        )

        return {
            "sentiment_score": weighted_sentiment,
            "summary": summary,
            "controversy_points": controversy_points,
            "retained_comment_count": len(normalized_records),
            "discarded_comment_count": 0,
            "chunk_summaries": _record_sentiments_to_chunk_results(record_sentiments),
            "record_sentiments": record_sentiments,
        }

    def _clean_comments(self, comments: Sequence[str]) -> CleanTextResult:
        """Remove ads, bots, gibberish, duplicates, and empty text."""
        retained_comments: list[str] = []
        discarded_count = 0
        seen_normalized: set[str] = set()
        for comment in comments:
            normalized = clean_comment_text(comment)
            if not normalized:
                discarded_count += 1
                continue
            dedupe_key = normalized.casefold()
            if dedupe_key in seen_normalized:
                discarded_count += 1
                continue
            if looks_like_noise(normalized):
                discarded_count += 1
                continue
            seen_normalized.add(dedupe_key)
            retained_comments.append(normalized[:MAX_COMMENT_LENGTH])
        return CleanTextResult(
            retained_comments=retained_comments,
            discarded_count=discarded_count,
        )

    async def _analyze_all_records(
        self,
        records: Sequence[dict[str, str]],
        *,
        output_language: str = "en",
    ) -> dict[str, object]:
        """Request one JSON analysis covering all collected records."""
        normalized_output_language = "Chinese" if output_language == "zh" else "English"
        system_prompt = (
            "You are a public-opinion analysis engine. "
            "You must return strict JSON only. "
            "Analyze the full current collection round in one pass. "
            "Return exactly this JSON shape: "
            '{"summary": "", "controversy_points": [{"title": "", "summary": ""}], '
            '"record_sentiments": [{"record_index": 1, "sentiment_score": 50, "relevance_score": 50, '
            '"sentiment_label": "", "reasoning": ""}]}'
        )
        user_prompt = (
            "Analyze the following collected source records about the target keyword.\n"
            "Requirements:\n"
            f"1. Keep all generated text in {normalized_output_language}.\n"
            "2. For every record, output one sentiment_score from 0 to 100.\n"
            "3. For every record, output one relevance_score from 0 to 100 describing how directly it discusses the target keyword.\n"
            "4. For every record, output a short sentiment_label and one concise reasoning sentence.\n"
            "5. Produce one overall summary for the current collection round.\n"
            "6. Produce exactly 3 major discussion points synthesized from the full set of records, not from one record only.\n"
            "7. Do not include URLs, source names, or video identifiers inside controversy_points.\n\n"
            f"Collected records:\n{json.dumps(list(records), ensure_ascii=False, separators=(',', ':'))}"
        )
        return await self._client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


async def analyze_opinions(comments: Sequence[str]) -> OpinionAnalysisResult:
    """Convenience function for running single-pass opinion analysis."""
    analyzer = OpinionAnalyzer()
    return await analyzer.analyze(comments)


def _empty_analysis_result(
    *,
    summary: str,
    discarded_count: int,
) -> OpinionAnalysisResult:
    """Return an empty analysis result."""
    return {
        "sentiment_score": 50,
        "summary": summary,
        "controversy_points": [],
        "retained_comment_count": 0,
        "discarded_comment_count": discarded_count,
        "chunk_summaries": [],
        "record_sentiments": [],
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
        if not title and not summary:
            continue
        normalized.append({"title": title, "summary": summary})
    return normalized


def _normalize_record_sentiments(
    *,
    raw_value: object,
    records: Sequence[dict[str, str]],
) -> list[RecordAnalysisResult]:
    """Normalize per-record sentiment rows and preserve original links."""
    if not isinstance(raw_value, list):
        raw_value = []

    raw_map: dict[int, dict[str, object]] = {}
    for item in raw_value:
        if not isinstance(item, dict):
            continue
        record_index = _safe_int(item.get("record_index"), default=0)
        if record_index <= 0:
            continue
        raw_map[record_index] = item

    normalized: list[RecordAnalysisResult] = []
    for index, record in enumerate(records, start=1):
        item = raw_map.get(index, {})
        normalized.append(
            {
                "record_index": index,
                "source": record["source"],
                "title": record["title"],
                "original_link": record["original_link"],
                "sentiment_score": _clamp_score(item.get("sentiment_score")),
                "relevance_score": _clamp_score(item.get("relevance_score")),
                "sentiment_label": _safe_text(
                    item.get("sentiment_label"),
                    fallback="Neutral",
                ),
                "reasoning": _safe_text(item.get("reasoning"), fallback=""),
            }
        )
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
        source = record.source
        title = _safe_text(metadata.get("title"), fallback="")
        description = _safe_text(
            metadata.get("description_text") or metadata.get("description"),
            fallback="",
        )
        transcript_text = _safe_text(metadata.get("transcript_text"), fallback="")
        comments_text = _safe_text(metadata.get("comments_text"), fallback="")
        content = _safe_text(record.content, fallback="")
        compact_content = _build_compact_record_content(
            source=source,
            title=title,
            content=content,
            transcript_text=transcript_text,
            comments_text=comments_text,
        )
        prepared.append(
            {
                "keyword": keyword,
                "source": source,
                "title": (title or content[:120])[:MAX_TITLE_LENGTH],
                "description": description[:MAX_DESCRIPTION_LENGTH],
                "transcript_text": _build_transcript_input(
                    source=source,
                    transcript_text=transcript_text,
                    content=content,
                ),
                "comments_text": comments_text[:MAX_COMMENTS_LENGTH],
                "content": compact_content,
                "original_link": record.original_link,
                "publish_date": _safe_text(metadata.get("publish_date"), fallback=""),
            }
        )
    return prepared


def _build_compact_record_content(
    *,
    source: str,
    title: str,
    content: str,
    transcript_text: str,
    comments_text: str,
) -> str:
    """Build a compact, non-duplicated content field for LLM analysis."""
    normalized_source = source.strip().lower()
    normalized_content = content.strip()
    normalized_title = title.strip()
    normalized_transcript = transcript_text.strip()
    normalized_comments = comments_text.strip()

    if normalized_source == "youtube" and normalized_transcript:
        if normalized_content and normalized_content.casefold() == normalized_title.casefold():
            return normalized_content[:MAX_RECORD_TEXT_LENGTH]
        if normalized_content and normalized_transcript.casefold() in normalized_content.casefold():
            return normalized_content[:MAX_DESCRIPTION_LENGTH]
        return normalized_content[:MAX_DESCRIPTION_LENGTH]

    if normalized_source == "reddit":
        parts: list[str] = []
        if normalized_content:
            parts.append(normalized_content[:MAX_RECORD_TEXT_LENGTH])
        if normalized_comments:
            parts.append(f"Top comments:\n{normalized_comments[:MAX_COMMENTS_LENGTH]}")
        return "\n\n".join(parts).strip()

    return normalized_content[:MAX_RECORD_TEXT_LENGTH]


def _build_transcript_input(
    *,
    source: str,
    transcript_text: str,
    content: str,
) -> str:
    """Avoid sending duplicate transcript text when content already embeds it."""
    normalized_source = source.strip().lower()
    normalized_transcript = transcript_text.strip()
    normalized_content = content.strip()
    if normalized_source != "youtube":
        return normalized_transcript[:MAX_RECORD_TEXT_LENGTH]
    if not normalized_transcript:
        return ""
    if normalized_content and normalized_transcript.casefold() in normalized_content.casefold():
        return ""
    return normalized_transcript[:MAX_RECORD_TEXT_LENGTH]


def _compute_weighted_sentiment(
    record_sentiments: Sequence[RecordAnalysisResult],
) -> int:
    """Compute a relevance-weighted sentiment score."""
    if not record_sentiments:
        return 50
    weighted_total = 0.0
    total_weight = 0.0
    for item in record_sentiments:
        weight = max(1, item["relevance_score"])
        weighted_total += item["sentiment_score"] * weight
        total_weight += weight
    return round(weighted_total / total_weight) if total_weight else 50


def _ensure_summary(
    *,
    existing_summary: str,
    keyword: str,
    sentiment_score: int,
    record_count: int,
) -> str:
    """Provide a deterministic fallback summary when the LLM omits one."""
    if existing_summary.strip():
        return existing_summary.strip()
    tone = (
        "mostly positive"
        if sentiment_score >= 60
        else "mixed"
        if sentiment_score >= 40
        else "mostly negative"
    )
    return (
        f"Collected {record_count} source records about {keyword}. "
        f"Overall discussion appears {tone}, with a weighted sentiment score of {sentiment_score}/100."
    )


def _ensure_controversy_points(
    *,
    existing_points: Sequence[ControversyPoint],
    records: Sequence[dict[str, str]],
) -> list[ControversyPoint]:
    """Guarantee three synthesized discussion points."""
    normalized = list(existing_points[:3])
    if len(normalized) >= 3:
        return normalized

    fallback_summaries = _collect_round_level_notes(records)
    while len(normalized) < 3:
        index = len(normalized)
        summary = (
            fallback_summaries[index]
            if index < len(fallback_summaries)
            else "Synthesized from the full current collection round."
        )
        normalized.append(
            {
                "title": f"Core Theme {index + 1}",
                "summary": summary[:240],
            }
        )
    return normalized


def _collect_round_level_notes(records: Sequence[dict[str, str]]) -> list[str]:
    """Collect distinct notes across the full current round."""
    notes: list[str] = []
    seen: set[str] = set()
    for record in records:
        for raw_note in (
            _safe_text(record.get("title"), fallback=""),
            _safe_text(record.get("description"), fallback=""),
        ):
            normalized = raw_note.strip()
            if len(normalized) < 16:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            notes.append(normalized)
            if len(notes) >= 3:
                return notes
    return notes


def _record_sentiments_to_chunk_results(
    record_sentiments: Sequence[RecordAnalysisResult],
) -> list[AnalysisChunkResult]:
    """Expose per-record sentiment judgments in the existing chunk summary field."""
    return [
        {
            "chunk_index": item["record_index"],
            "sentiment_score": item["sentiment_score"],
            "summary": item["reasoning"],
            "controversy_points": [],
            "retained_count": 1,
        }
        for item in record_sentiments
    ]


def _clamp_score(raw_value: object) -> int:
    """Clamp a raw score into the required 0-100 range."""
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
