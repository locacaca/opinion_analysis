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
    output_language: str = Field(default="en", pattern="^(en|zh)$")
    limit_per_source: int = Field(default=30, ge=1, le=50)
    total_limit: int | None = Field(default=None, ge=1, le=50)
    sources: list[str] = Field(default_factory=lambda: ["youtube"])
    source_weights: dict[str, str] = Field(default_factory=dict)
    youtube_mode: str = Field(default="official_api", pattern="^(official_api|headless_browser)$")


class CollectKeywordRequest(BaseModel):
    """Request payload for collection-only backend debugging."""

    keyword: str = Field(min_length=1, max_length=100)
    language: str = Field(default="en", pattern="^(en|zh)$")
    limit_per_source: int = Field(default=50, ge=1, le=100)
    total_limit: int | None = Field(default=None, ge=1, le=50)
    sources: list[str] = Field(default_factory=lambda: ["youtube"])
    source_weights: dict[str, str] = Field(default_factory=dict)
    youtube_mode: str = Field(default="official_api", pattern="^(official_api|headless_browser)$")


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
            total_limit=payload.total_limit,
            sources=payload.sources,
            source_weights=payload.source_weights,
            language=payload.language,
            output_language=payload.output_language,
            youtube_mode=payload.youtube_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc).strip() or "Backend analysis failed."
        status_code = 504 if "timed out" in message.lower() else 500
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        message = str(exc).strip() or "Backend analysis failed."
        raise HTTPException(status_code=500, detail=message) from exc


@app.post("/api/debug/collect")
async def debug_collect(payload: CollectKeywordRequest) -> dict[str, object]:
    """Collect, clean, and store records without calling the LLM."""
    try:
        return await collect_and_store_keyword(
            payload.keyword,
            language=payload.language,
            limit_per_source=payload.limit_per_source,
            total_limit=payload.total_limit,
            sources=payload.sources,
            source_weights=payload.source_weights,
            youtube_mode=payload.youtube_mode,
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
                "youtube_mode": payload.youtube_mode,
            },
        )
        return await spider.debug_collect(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
