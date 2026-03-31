"""Async client for OpenAI-compatible chat-completions APIs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import aiohttp

from ..config import get_required_env, load_env_file


@dataclass(slots=True, frozen=True)
class LLMClientConfig:
    """Holds API configuration for the opinion analysis client."""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "LLMClientConfig":
        """Build a client config from environment variables."""
        load_env_file()
        timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "60")
        api_key = os.getenv("LLM_API_KEY") or get_required_env("API_KEY")
        base_url = (
            os.getenv("LLM_API_BASE_URL")
            or os.getenv("BASE_URL")
            or "https://api.deepseek.com/v1"
        ).rstrip("/")
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            timeout_seconds=int(timeout_raw),
        )


class OpenAICompatibleLLMClient:
    """Minimal async client for providers exposing a chat-completions interface."""

    def __init__(self, config: LLMClientConfig | None = None) -> None:
        """Initialize the client from explicit config or environment variables."""
        self._config = config or LLMClientConfig.from_env()

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Request a JSON response and parse it into a Python dictionary."""
        payload = {
            "model": self._config.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        timeout = aiohttp.ClientTimeout(total=self._config.timeout_seconds)
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self._config.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                body = await response.text()
                response.raise_for_status()
        return self._extract_json(body)

    def _extract_json(self, raw_response: str) -> dict[str, Any]:
        """Extract the model JSON payload from an OpenAI-compatible API response."""
        payload = json.loads(raw_response)
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str):
            raise ValueError("LLM response content is not a JSON string.")
        return _parse_json_object(content)


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating markdown fences around the payload."""
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Model response did not contain a JSON object.")
    return json.loads(stripped[start : end + 1])
