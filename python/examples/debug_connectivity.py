"""Debug database and LLM connectivity for the TrendPulse backend."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine.analysis.llm_client import (  # noqa: E402
    LLMClientConfig,
    OpenAICompatibleLLMClient,
)
from opinion_engine.config import get_database_url, load_env_file  # noqa: E402
from opinion_engine.storage import OpinionStorage  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for connectivity debugging."""
    parser = argparse.ArgumentParser(
        description="Debug only the database connection and LLM connectivity.",
    )
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Only test database connectivity.",
    )
    parser.add_argument(
        "--llm-only",
        action="store_true",
        help="Only test LLM connectivity.",
    )
    return parser.parse_args()


async def _run(*, db_only: bool, llm_only: bool) -> dict[str, Any]:
    """Run the requested connectivity checks and return structured JSON."""
    load_env_file()
    if db_only and llm_only:
        raise ValueError("--db-only and --llm-only cannot be used together.")

    result: dict[str, Any] = {}
    if not llm_only:
        result["database"] = await asyncio.to_thread(_debug_database)
    if not db_only:
        result["llm"] = await _debug_llm()
    return result


def _debug_database() -> dict[str, Any]:
    """Test database initialization and a simple round-trip query."""
    storage = OpinionStorage()
    storage.initialize()
    database_url = get_database_url()

    with storage._engine.connect() as connection:  # noqa: SLF001
        scalar = connection.execute(text("SELECT 1")).scalar_one()
    table_names = sorted(inspect(storage._engine).get_table_names())  # noqa: SLF001

    return {
        "ok": True,
        "database_url": database_url,
        "select_1_result": int(scalar),
        "known_tables": table_names,
    }


async def _debug_llm() -> dict[str, Any]:
    """Test whether the configured LLM endpoint can return a strict JSON response."""
    client = OpenAICompatibleLLMClient()
    config = LLMClientConfig.from_env()
    response = await client.generate_json(
        system_prompt=(
            "You are a connectivity probe. "
            "Return strict JSON only with this shape: "
            '{"status": "ok", "provider_echo": ""}.'
        ),
        user_prompt="Reply with status ok and echo the configured model name.",
        temperature=0,
    )
    return {
        "ok": True,
        "base_url": config.base_url,
        "model": config.model,
        "response": response,
    }


def main() -> None:
    """Run connectivity checks and print the JSON result."""
    args = parse_args()
    result = asyncio.run(_run(db_only=args.db_only, llm_only=args.llm_only))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
