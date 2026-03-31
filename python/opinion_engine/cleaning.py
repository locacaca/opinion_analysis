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


def clean_comment_text(comment: str) -> str:
    """Normalize whitespace and strip control-like clutter from a comment."""
    return re.sub(r"\s+", " ", comment).strip()


def looks_like_noise(comment: str) -> bool:
    """Apply simple heuristics to remove spammy, bot-like, or corrupted comments."""
    lowered = comment.casefold()
    spam_signals = (
        "buy now",
        "discount",
        "promo code",
        "free shipping",
        "telegram",
        "whatsapp",
        "dm me",
        "click here",
        "http://",
        "https://",
        "www.",
    )
    if len(comment) < 5:
        return True
    if any(signal in lowered for signal in spam_signals):
        return True
    if len(re.findall(r"(.)\1{5,}", comment)) > 0:
        return True
    alpha_count = sum(character.isalpha() for character in comment)
    digit_count = sum(character.isdigit() for character in comment)
    if alpha_count == 0:
        return True
    if digit_count > alpha_count:
        return True
    unique_ratio = len(set(lowered)) / max(len(lowered), 1)
    if len(comment) > 20 and unique_ratio < 0.15:
        return True
    return False


def clean_opinion_records(records: Sequence[OpinionRecord]) -> CleanRecordsResult:
    """Normalize and filter collected records before they are stored."""
    cleaned_records: list[CleanedOpinionRecord] = []
    discarded_count = 0
    seen_keys: set[str] = set()

    for record in records:
        content = clean_comment_text(str(record.get("content", "")))
        if not content or looks_like_noise(content):
            discarded_count += 1
            continue

        original_link = str(record.get("original_link", ""))
        dedupe_key = original_link or content.casefold()
        if dedupe_key in seen_keys:
            discarded_count += 1
            continue

        seen_keys.add(dedupe_key)
        cleaned_records.append(
            CleanedOpinionRecord(
                keyword=str(record.get("keyword", "")),
                source=str(record.get("source", "unknown")),
                content=content[:MAX_CONTENT_LENGTH],
                author=str(record.get("author")) if record.get("author") else None,
                original_link=original_link,
                metadata=dict(record.get("metadata", {})),
            )
        )

    return CleanRecordsResult(
        records=cleaned_records,
        discarded_count=discarded_count,
    )
