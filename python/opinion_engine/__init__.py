"""Core package for the multi-source opinion collection engine."""

from .analysis import OpinionAnalyzer, analyze_opinions
from .cleaning import CleanRecordsResult, CleanedOpinionRecord, clean_opinion_records
from .config import load_env_file
from .engine import MultiSourceCollectionEngine
from .models import OpinionRecord, SpiderRequest
from .pipeline import analyze_keyword, collect_and_store_keyword
from .storage import OpinionStorage, StoredOpinionRecord

__all__ = [
    "MultiSourceCollectionEngine",
    "OpinionAnalyzer",
    "OpinionStorage",
    "OpinionRecord",
    "SpiderRequest",
    "StoredOpinionRecord",
    "analyze_keyword",
    "collect_and_store_keyword",
    "analyze_opinions",
    "CleanedOpinionRecord",
    "CleanRecordsResult",
    "clean_opinion_records",
    "load_env_file",
]
