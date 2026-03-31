"""Async orchestration layer for multi-source opinion collection."""

from __future__ import annotations

import asyncio
from typing import Any, Iterable

from .models import OpinionRecord, SpiderRequest
from .spiders.base import BaseSpider


class MultiSourceCollectionEngine:
    """Coordinates multiple spiders in a single async collection workflow."""

    def __init__(self, spiders: Iterable[BaseSpider[Any]]) -> None:
        """Initialize the engine with spider instances."""
        self._spiders = list(spiders)

    async def collect(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Collect normalized records from all configured spiders."""
        tasks: list[asyncio.Task[list[OpinionRecord]]] = [
            asyncio.create_task(spider.fetch(request)) for spider in self._spiders
        ]
        results: list[list[OpinionRecord]] = await asyncio.gather(*tasks)
        return [item for batch in results for item in batch]
