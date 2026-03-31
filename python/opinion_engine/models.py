"""Shared models for opinion collection spiders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TypedDict


class OpinionRecord(TypedDict, total=False):
    """Normalized record emitted by a spider."""

    source: str
    keyword: str
    content: str
    author: str | None
    original_link: str
    metadata: dict[str, Any]


@dataclass(slots=True, frozen=True)
class SpiderRequest:
    """Represents a unified spider request."""

    keyword: str
    limit: int = 10
    extra_params: Mapping[str, Any] = field(default_factory=dict)
