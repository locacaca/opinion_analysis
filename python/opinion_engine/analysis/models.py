"""Typed models for LLM opinion analysis results."""

from __future__ import annotations

from typing import TypedDict


class ControversyPoint(TypedDict):
    """Represents a major controversy point extracted from comments."""

    title: str
    summary: str


class AnalysisChunkResult(TypedDict):
    """Represents the intermediate map-stage result for a chunk of comments."""

    chunk_index: int
    sentiment_score: int
    summary: str
    controversy_points: list[ControversyPoint]
    retained_count: int


class RecordAnalysisResult(TypedDict):
    """Represents one source record analyzed by the LLM."""

    record_index: int
    source: str
    title: str
    original_link: str
    sentiment_score: int
    relevance_score: int
    sentiment_label: str
    reasoning: str


class OpinionAnalysisResult(TypedDict):
    """Represents the final reduce-stage result consumed by the frontend."""

    sentiment_score: int
    summary: str
    controversy_points: list[ControversyPoint]
    retained_comment_count: int
    discarded_comment_count: int
    chunk_summaries: list[AnalysisChunkResult]
    record_sentiments: list[RecordAnalysisResult]
