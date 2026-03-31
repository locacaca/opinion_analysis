"""Run the TrendPulse FastAPI backend locally."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start the FastAPI backend with a local development server."""
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        app_dir="python",
    )


if __name__ == "__main__":
    main()
