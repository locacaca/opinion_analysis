"""Spider implementations for the opinion collection engine."""

from .base import BaseSpider
from .reddit import RedditSpider
from .x_stub import XSearchSpider
from .youtube import YouTubeTranscriptSpider

__all__ = ["BaseSpider", "RedditSpider", "YouTubeTranscriptSpider", "XSearchSpider"]
