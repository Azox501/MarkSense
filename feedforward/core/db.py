"""SQLite persistence and transaction boundaries."""
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterator

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from core.config import get_settings


def utcnow() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(10))


class Classroom(Base):
    __tablename__ = "classrooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    join_code: Mapped[str] = mapped_column(String(6), unique=True)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.6)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("classroom_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("classroom_id", "kind", "content_hash"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    kind: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    question_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    page: Mapped[int] = mapped_column()
    chroma_id: Mapped[str] = mapped_column(String(100), unique=True)


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    rubric_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    max_marks: Mapped[float] = mapped_column(Float)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(10))
    file_path: Mapped[str] = mapped_column(Text)
    transcript_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    hints_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    feedback_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    similarity_warning_shown: Mapped[bool] = mapped_column(Boolean, default=False)
    review_comment: Mapped[str] = mapped_column(Text, default="")
    final_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)


class CriterionResult(Base):
    __tablename__ = "criterion_results"
    __table_args__ = (UniqueConstraint("submission_id", "question_no", "criterion_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    question_no: Mapped[str] = mapped_column(String(30))
    criterion_id: Mapped[str] = mapped_column(String(100))
    level: Mapped[float] = mapped_column(Float)
    ai_marks: Mapped[float] = mapped_column(Float)
    teacher_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(Text)
    evidence_quote: Mapped[str] = mapped_column(Text)
    source_chunk_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float)


class QuestionResult(Base):
    __tablename__ = "question_results"
    __table_args__ = (UniqueConstraint("submission_id", "question_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    question_no: Mapped[str] = mapped_column(String(30))
    ai_score: Mapped[float] = mapped_column(Float)
    teacher_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_marks: Mapped[float] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean)
    teacher_remark: Mapped[str] = mapped_column(Text, default="")


class IntegrityReport(Base):
    __tablename__ = "integrity_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    matched_submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    similarity: Mapped[float] = mapped_column(Float)
    flagged_passages_json: Mapped[list[dict[str, str]]] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    """Initialize local storage, foreign keys and SQLite WAL mode."""
    directory = get_settings(False).data_dir
    directory.mkdir(parents=True, exist_ok=True)
    engine = create_engine("sqlite:///" + str(directory / "app.db"),
                           connect_args={"check_same_thread": False, "timeout": 30})
    @event.listens_for(engine, "connect")
    def configure(connection: Any, _: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Commit a complete operation, or roll it back on any failure."""
    with session_factory()() as session:
        with session.begin():
            yield session
