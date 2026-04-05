"""Shared cleaning utilities for collected opinion records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .models import OpinionRecord

MAX_CONTENT_LENGTH = 4000


@dataclass(slots=True, frozen=True)
class CleanedOpinionRecord:
    """Represents a normalized record ready for persistence and analysis."""

    keyword: str
    source: str
    content: str
    author: str | None
    original_link: str
    metadata: dict[str, object]


@dataclass(slots=True, frozen=True)
class CleanRecordsResult:
    """Contains cleaned records plus discard metrics."""

    records: list[CleanedOpinionRecord]
    discarded_count: int
    retained_count_by_source: dict[str, int]
    discarded_count_by_source: dict[str, int]


def clean_comment_text(comment: str) -> str:
    """Normalize whitespace and strip control-like clutter from a comment."""
    return re.sub(r"\s+", " ", comment).strip()


def looks_like_noise(comment: str) -> bool:
    """Only treat obviously garbled text as noise."""
    return _looks_like_mojibake(comment)


def clean_opinion_records(records: Sequence[OpinionRecord]) -> CleanRecordsResult:
    """Normalize and filter collected records before they are stored."""
    cleaned_records: list[CleanedOpinionRecord] = []
    discarded_count = 0
    retained_count_by_source: dict[str, int] = {}
    discarded_count_by_source: dict[str, int] = {}

    for record in records:
        source = str(record.get("source", "unknown"))
        content = clean_comment_text(str(record.get("content", "")))
        if not content or looks_like_noise(content):
            discarded_count += 1
            discarded_count_by_source[source] = (
                discarded_count_by_source.get(source, 0) + 1
            )
            continue

        retained_count_by_source[source] = retained_count_by_source.get(source, 0) + 1
        cleaned_records.append(
            CleanedOpinionRecord(
                keyword=str(record.get("keyword", "")),
                source=source,
                content=content[:MAX_CONTENT_LENGTH],
                author=str(record.get("author")) if record.get("author") else None,
                original_link=str(record.get("original_link", "")),
                metadata=dict(record.get("metadata", {})),
            )
        )

    return CleanRecordsResult(
        records=cleaned_records,
        discarded_count=discarded_count,
        retained_count_by_source=retained_count_by_source,
        discarded_count_by_source=discarded_count_by_source,
    )


def _looks_like_mojibake(text: str) -> bool:
    """Heuristically detect obviously garbled text only."""
    normalized = text.strip()
    if not normalized:
        return False
    if "\ufffd" in normalized:
        return True

    suspicious_fragments = (
        "Ã",
        "Â",
        "â€",
        "ðŸ",
        "ï¿½",
        "锟",
        "脙",
        "脗",
    )
    if any(fragment in normalized for fragment in suspicious_fragments):
        return True

    garbled_symbol_count = sum(
        1 for character in normalized if character in {"�", "�", "�"}
    )
    return garbled_symbol_count >= 2
