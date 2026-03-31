"""Abstract spider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Sequence, TypeVar

from ..models import OpinionRecord, SpiderRequest

RawItemT = TypeVar("RawItemT")


class BaseSpider(ABC, Generic[RawItemT]):
    """Abstract base class for all source spiders."""

    source_name: str

    @abstractmethod
    async def fetch(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Fetch and normalize records for the given request."""

    @abstractmethod
    def clean_data(self, raw_data: Sequence[RawItemT]) -> list[OpinionRecord]:
        """Normalize raw source records into the shared output format."""
