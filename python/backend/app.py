"""FastAPI application exposing keyword analysis endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from opinion_engine import analyze_keyword, collect_and_store_keyword
from opinion_engine.models import SpiderRequest
from opinion_engine.spiders.youtube import YouTubeTranscriptSpider


class AnalyzeKeywordRequest(BaseModel):
    """Request payload for keyword-driven opinion analysis."""

    keyword: str = Field(min_length=1, max_length=100)
    language: str = Field(default="en", pattern="^(en|zh)$")
    limit_per_source: int = Field(default=30, ge=1, le=50)
    sources: list[str] = Field(default_factory=lambda: ["youtube"])


class CollectKeywordRequest(BaseModel):
    """Request payload for collection-only backend debugging."""

    keyword: str = Field(min_length=1, max_length=100)
    language: str = Field(default="en", pattern="^(en|zh)$")
    limit_per_source: int = Field(default=50, ge=1, le=100)
    sources: list[str] = Field(default_factory=lambda: ["youtube"])


app = FastAPI(title="TrendPulse API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a health check response."""
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(payload: AnalyzeKeywordRequest) -> dict[str, object]:
    """Run multi-source collection and AI analysis for a keyword."""
    try:
        return await analyze_keyword(
            payload.keyword,
            limit_per_source=payload.limit_per_source,
            sources=payload.sources,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/debug/collect")
async def debug_collect(payload: CollectKeywordRequest) -> dict[str, object]:
    """Collect, clean, and store records without calling the LLM."""
    try:
        return await collect_and_store_keyword(
            payload.keyword,
            language=payload.language,
            limit_per_source=payload.limit_per_source,
            sources=payload.sources,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/debug/youtube")
async def debug_youtube(payload: CollectKeywordRequest) -> dict[str, object]:
    """Debug YouTube search and transcript fetching without storage or LLM."""
    try:
        spider = YouTubeTranscriptSpider()
        request = SpiderRequest(
            keyword=payload.keyword,
            limit=payload.limit_per_source,
            extra_params={
                "language": payload.language,
                "strict_captions_only": False,
            },
        )
        return await spider.debug_collect(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
