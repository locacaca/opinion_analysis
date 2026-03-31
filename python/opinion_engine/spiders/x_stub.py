"""X/Twitter spider interface stub."""

from __future__ import annotations

from typing import Sequence

from ..models import OpinionRecord, SpiderRequest
from .base import BaseSpider


class XSearchSpider(BaseSpider[dict[str, str]]):
    """Placeholder spider for X/Twitter integration."""

    source_name = "x"

    async def fetch(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Return an empty result until the X/Twitter source is implemented."""
        return self.clean_data([])

    def clean_data(self, raw_data: Sequence[dict[str, str]]) -> list[OpinionRecord]:
        """Return a normalized empty result for the unimplemented X source."""
        return []
