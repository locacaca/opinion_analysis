"""Database persistence layer for cleaned opinion records."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .cleaning import CleanedOpinionRecord
from .config import get_database_url


class Base(DeclarativeBase):
    """Base ORM class."""


class CollectionRunModel(Base):
    """Represents a keyword collection and analysis run."""

    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sentiment_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heat_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retained_count: Mapped[int] = mapped_column(Integer, default=0)
    discarded_count: Mapped[int] = mapped_column(Integer, default=0)
    source_breakdown: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    source_errors: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)


class CleanedRecordModel(Base):
    """Represents a cleaned source record persisted before LLM analysis."""

    __tablename__ = "cleaned_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    keyword: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_link: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    publish_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_transcript: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@dataclass(slots=True, frozen=True)
class StoredOpinionRecord:
    """Represents a persisted cleaned record loaded from the database."""

    keyword: str
    source: str
    content: str
    author: str | None
    original_link: str
    metadata: dict[str, Any]


class OpinionStorage:
    """Persists cleaned records to SQLite or PostgreSQL."""

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize the storage engine."""
        self._engine = create_engine(
            database_url or get_database_url(),
            future=True,
        )
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def initialize(self) -> None:
        """Create database tables if they do not exist."""
        Base.metadata.create_all(self._engine)
        self._ensure_cleaned_record_columns()

    def create_run(self, keyword: str, language: str | None = None) -> int:
        """Create a collection run row and return its identifier."""
        with self._session() as session:
            run = CollectionRunModel(
                keyword=keyword,
                language=language,
                status="running",
                started_at=_utcnow(),
            )
            session.add(run)
            session.flush()
            return int(run.id)

    def save_cleaned_records(
        self,
        *,
        run_id: int,
        records: list[CleanedOpinionRecord],
    ) -> int:
        """Persist cleaned source records for a collection run."""
        if not records:
            return 0

        now = _utcnow()
        with self._session() as session:
            session.add_all(
                [
                    _build_cleaned_record_model(
                        run_id=run_id,
                        record=record,
                        created_at=now,
                    )
                    for record in records
                ]
            )
        return len(records)

    def load_run_records(self, run_id: int) -> list[StoredOpinionRecord]:
        """Load cleaned source records for a collection run."""
        with self._session() as session:
            rows = session.scalars(
                select(CleanedRecordModel).where(CleanedRecordModel.run_id == run_id)
            ).all()

        return [
            StoredOpinionRecord(
                keyword=row.keyword,
                source=row.source,
                content=row.content,
                author=row.author,
                original_link=row.original_link,
                metadata=_build_stored_metadata(row),
            )
            for row in rows
        ]

    def _ensure_cleaned_record_columns(self) -> None:
        """Add newly introduced cleaned-record columns to existing databases."""
        inspector = inspect(self._engine)
        if "cleaned_records" not in inspector.get_table_names():
            return

        existing_columns = {
            column["name"] for column in inspector.get_columns("cleaned_records")
        }
        column_statements = {
            "publish_date": "ALTER TABLE cleaned_records ADD COLUMN publish_date TEXT",
            "video_id": "ALTER TABLE cleaned_records ADD COLUMN video_id VARCHAR(64)",
            "video_url": "ALTER TABLE cleaned_records ADD COLUMN video_url TEXT",
            "has_transcript": (
                "ALTER TABLE cleaned_records ADD COLUMN has_transcript BOOLEAN"
            ),
            "title": "ALTER TABLE cleaned_records ADD COLUMN title TEXT",
            "description": "ALTER TABLE cleaned_records ADD COLUMN description TEXT",
            "description_text": (
                "ALTER TABLE cleaned_records ADD COLUMN description_text TEXT"
            ),
            "transcript_text": (
                "ALTER TABLE cleaned_records ADD COLUMN transcript_text TEXT"
            ),
        }

        with self._engine.begin() as connection:
            for column_name, statement in column_statements.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))

    def complete_run(
        self,
        *,
        run_id: int,
        sentiment_score: int,
        heat_score: int,
        summary: str,
        retained_count: int,
        discarded_count: int,
        source_breakdown: dict[str, int],
        source_errors: dict[str, str],
    ) -> None:
        """Persist final analysis metadata for a collection run."""
        with self._session() as session:
            run = session.get(CollectionRunModel, run_id)
            if run is None:
                return
            run.status = "completed"
            run.completed_at = _utcnow()
            run.sentiment_score = sentiment_score
            run.heat_score = heat_score
            run.summary = summary
            run.retained_count = retained_count
            run.discarded_count = discarded_count
            run.source_breakdown = source_breakdown
            run.source_errors = source_errors

    def mark_run_collected(
        self,
        *,
        run_id: int,
        retained_count: int,
        discarded_count: int,
        source_breakdown: dict[str, int],
        source_errors: dict[str, str],
    ) -> None:
        """Mark a collection run as completed at the storage stage only."""
        with self._session() as session:
            run = session.get(CollectionRunModel, run_id)
            if run is None:
                return
            run.status = "collected"
            run.completed_at = _utcnow()
            run.retained_count = retained_count
            run.discarded_count = discarded_count
            run.source_breakdown = source_breakdown
            run.source_errors = source_errors

    def fail_run(
        self,
        *,
        run_id: int,
        source_errors: dict[str, str],
        failure_reason: str,
        discarded_count: int,
    ) -> None:
        """Persist failure metadata for a collection run."""
        with self._session() as session:
            run = session.get(CollectionRunModel, run_id)
            if run is None:
                return
            run.status = "failed"
            run.completed_at = _utcnow()
            run.discarded_count = discarded_count
            run.source_errors = source_errors
            run.failure_reason = failure_reason

    @contextmanager
    def _session(self) -> Iterator[Session]:
        """Provide a transaction-scoped ORM session."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def _build_cleaned_record_model(
    *,
    run_id: int,
    record: CleanedOpinionRecord,
    created_at: datetime,
) -> CleanedRecordModel:
    """Map a cleaned record into ORM columns plus residual metadata JSON."""
    metadata = dict(record.metadata or {})
    metadata.pop("keyword", None)
    publish_date = _pop_text(metadata, "publish_date")
    video_id = _pop_text(metadata, "video_id")
    video_url = _pop_text(metadata, "video_url")
    has_transcript = _pop_bool(metadata, "has_transcript")
    title = _pop_text(metadata, "title")
    metadata.pop("title_text", None)
    description = _pop_text(metadata, "description")
    description_text = _pop_text(metadata, "description_text") or description
    transcript_text = _pop_text(metadata, "transcript_text")

    return CleanedRecordModel(
        run_id=run_id,
        keyword=record.keyword,
        source=record.source,
        author=record.author,
        original_link=record.original_link,
        content=record.content,
        publish_date=publish_date,
        video_id=video_id,
        video_url=video_url,
        has_transcript=has_transcript,
        title=title,
        description=description or description_text,
        description_text=description_text,
        transcript_text=transcript_text,
        metadata_json=metadata or None,
        created_at=created_at,
    )


def _build_stored_metadata(row: CleanedRecordModel) -> dict[str, Any]:
    """Rebuild the metadata view from dedicated columns plus any residual JSON."""
    metadata = dict(row.metadata_json or {})
    _set_if_present(metadata, "publish_date", row.publish_date)
    _set_if_present(metadata, "video_id", row.video_id)
    _set_if_present(metadata, "video_url", row.video_url)
    if row.has_transcript is not None:
        metadata["has_transcript"] = bool(row.has_transcript)
    _set_if_present(metadata, "title", row.title)
    _set_if_present(metadata, "description", row.description)
    _set_if_present(metadata, "description_text", row.description_text)
    _set_if_present(metadata, "transcript_text", row.transcript_text)
    return metadata


def _pop_text(metadata: dict[str, Any], key: str) -> str | None:
    """Pop a text-like metadata value and normalize empty strings to None."""
    value = metadata.pop(key, None)
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _pop_bool(metadata: dict[str, Any], key: str) -> bool | None:
    """Pop a boolean-like metadata value."""
    value = metadata.pop(key, None)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


def _set_if_present(metadata: dict[str, Any], key: str, value: Any) -> None:
    """Write a metadata value only when it is meaningfully present."""
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return
    metadata[key] = value


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)
