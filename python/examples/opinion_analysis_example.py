"""Executable example for LLM-based opinion analysis."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from opinion_engine.analysis import analyze_opinions

SAMPLE_COMMENTS = [
    "The new product update is much faster, but the battery drain is worse than before.",
    "I like the new UI. It feels cleaner and easier to navigate.",
    "Terrible rollout. The app crashes every time I upload a video.",
    "Buy now! Limited discount! Visit https://spam.example.com",
    "Customer support is still too slow, even though the features improved.",
    "The privacy policy changes are the real problem, not the design refresh.",
    "This is the best version so far, but premium pricing is getting hard to justify.",
    "asdfasdfasdf111111111",
    "Ads are more aggressive now. That makes the whole experience worse.",
    "Performance is better on Android, but iOS users seem much angrier.",
    "I don't mind the redesign, but removing old shortcuts hurts power users.",
]


def main() -> None:
    """Run the opinion analysis example and print strict JSON output."""
    result = asyncio.run(analyze_opinions(SAMPLE_COMMENTS))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
