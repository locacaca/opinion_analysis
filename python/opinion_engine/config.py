"""Environment configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file() -> None:
    """Load environment variables from a local .env file if present."""
    candidate_paths = (
        Path.cwd() / ".env",
        Path.cwd() / ".env.example",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[2] / ".env.example",
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[1] / ".env.example",
    )
    for path in candidate_paths:
        if path.is_file():
            _merge_env_file(path)
            return


def get_required_env(name: str) -> str:
    """Return a required environment variable or raise a helpful error."""
    value = os.getenv(name)
    if value:
        return value
    raise ValueError(
        f"Missing required environment variable: {name}. "
        "Set it in your shell or create python/.env based on python/.env.example."
    )


def get_optional_env(name: str, default: str | None = None) -> str | None:
    """Return an optional environment variable."""
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def get_database_url() -> str:
    """Return the database URL, defaulting to a local SQLite file."""
    load_env_file()
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return _normalize_database_url(database_url)

    sqlite_path = Path(__file__).resolve().parents[2] / "data" / "trendpulse.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{sqlite_path.as_posix()}"


def _normalize_database_url(database_url: str) -> str:
    """Normalize a database setting into a SQLAlchemy-compatible URL."""
    normalized = database_url.strip()
    if "://" in normalized:
        return normalized

    path = Path(normalized).expanduser()
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[2] / path).resolve()

    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def _merge_env_file(path: Path) -> None:
    """Parse a simple KEY=VALUE .env file into process environment variables."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
