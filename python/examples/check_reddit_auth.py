"""Diagnostic script for Reddit API credential validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine.config import get_optional_env, get_required_env, load_env_file
from opinion_engine.spiders.reddit import RedditSpider


def _mask(value: str | None) -> str:
    """Mask a credential for safe terminal output."""
    if not value:
        return "<missing>"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def main() -> None:
    """Print sanitized config and perform a minimal Reddit auth check."""
    load_env_file()
    app_type = get_optional_env("REDDIT_APP_TYPE", "script")
    client_id = get_required_env("REDDIT_CLIENT_ID")
    client_secret = get_optional_env("REDDIT_CLIENT_SECRET")
    user_agent = get_optional_env("REDDIT_USER_AGENT")

    print(
        json.dumps(
            {
                "app_type": app_type,
                "client_id": _mask(client_id),
                "client_secret": _mask(client_secret),
                "user_agent": user_agent or "<missing>",
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    spider = RedditSpider()
    subreddit = spider._reddit.subreddit("all")
    print(f"authenticated_subreddit={subreddit.display_name}")


if __name__ == "__main__":
    main()
