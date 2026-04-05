"""Spider implementations for the opinion collection engine."""

from .base import BaseSpider
from .reddit_spider import RedditSearchSpider
from .x_stub import XSearchSpider
from .youtube import YouTubeTranscriptSpider

__all__ = ["BaseSpider", "RedditSearchSpider", "YouTubeTranscriptSpider", "XSearchSpider"]
