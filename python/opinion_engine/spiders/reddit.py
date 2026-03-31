"""Reddit spider implementation backed by PRAW."""

from __future__ import annotations

import asyncio
import os
from typing import Sequence

import praw
from praw.models import Submission
from prawcore.exceptions import ResponseException

from ..config import get_optional_env, get_required_env, load_env_file
from ..models import OpinionRecord, SpiderRequest
from .base import BaseSpider


class RedditSpider(BaseSpider[Submission]):
    """Collects Reddit posts for a keyword and returns normalized records."""

    source_name = "reddit"

    def __init__(self, subreddit_name: str = "all") -> None:
        """Create a Reddit spider using readonly credentials from environment variables."""
        load_env_file()
        app_type = get_optional_env("REDDIT_APP_TYPE", "script")
        client_id = get_required_env("REDDIT_CLIENT_ID")
        user_agent = os.getenv(
            "REDDIT_USER_AGENT",
            "windows:opinion-analysis:v1.0 (by /u/unknown)",
        )

        self._validate_credentials(client_id=client_id, app_type=app_type)

        client_secret: str | None
        if app_type == "installed":
            client_secret = None
        else:
            client_secret = get_required_env("REDDIT_CLIENT_SECRET")

        self._subreddit_name = subreddit_name
        self._reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self._reddit.read_only = True

    async def fetch(self, request: SpiderRequest) -> list[OpinionRecord]:
        """Fetch Reddit submissions asynchronously via a thread offload."""
        time_filter = str(request.extra_params.get("time_filter", "day"))
        raw_data: list[Submission] = await asyncio.to_thread(
            self._search_submissions,
            request.keyword,
            request.limit,
            time_filter,
        )
        cleaned_records = self.clean_data(raw_data)
        for record in cleaned_records:
            record["keyword"] = request.keyword
        return cleaned_records

    def clean_data(self, raw_data: Sequence[Submission]) -> list[OpinionRecord]:
        """Normalize PRAW submission objects into opinion records."""
        cleaned_records: list[OpinionRecord] = []
        for submission in raw_data:
            title: str = submission.title.strip()
            self_text: str = submission.selftext.strip()
            content: str = f"{title}\n\n{self_text}".strip()
            cleaned_records.append(
                {
                    "source": self.source_name,
                    "content": content or title,
                    "author": str(submission.author) if submission.author else None,
                    "original_link": f"https://www.reddit.com{submission.permalink}",
                    "metadata": {
                        "id": submission.id,
                        "score": submission.score,
                        "subreddit": submission.subreddit.display_name,
                        "created_utc": submission.created_utc,
                        "external_url": submission.url,
                    },
                }
            )
        return cleaned_records

    def _search_submissions(self, keyword: str, limit: int, time_filter: str) -> list[Submission]:
        """Execute the blocking Reddit search call."""
        try:
            subreddit = self._reddit.subreddit(self._subreddit_name)
            return list(
                subreddit.search(
                    query=keyword,
                    limit=limit,
                    sort="new",
                    time_filter=time_filter,
                )
            )
        except ResponseException as exc:
            raise RuntimeError(
                "Reddit authentication failed with HTTP 401. "
                "Verify REDDIT_APP_TYPE, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_USER_AGENT. "
                "REDDIT_CLIENT_ID must be the short app id shown under the Reddit app name, not your username. "
                "For REDDIT_APP_TYPE=script or web, REDDIT_CLIENT_SECRET must be the app's secret. "
                "For REDDIT_APP_TYPE=installed, leave REDDIT_CLIENT_SECRET unset."
            ) from exc

    @staticmethod
    def _validate_credentials(client_id: str, app_type: str | None) -> None:
        """Fail fast on obviously invalid Reddit credential values."""
        normalized_app_type = (app_type or "script").strip().lower()
        if normalized_app_type not in {"script", "web", "installed"}:
            raise ValueError("REDDIT_APP_TYPE must be one of: script, web, installed.")
        if client_id.startswith("u/") or client_id.startswith("/u/"):
            raise ValueError(
                "REDDIT_CLIENT_ID looks like a Reddit username. "
                "It must be the short app id shown under your Reddit app name."
            )
        if "reddit.com" in client_id.lower():
            raise ValueError(
                "REDDIT_CLIENT_ID looks like a URL. "
                "It must be the short app id shown under your Reddit app name."
            )
