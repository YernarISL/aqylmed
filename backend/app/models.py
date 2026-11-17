"""Таблицы БД. Названия и связи — по ER-диаграмме AQYLMED_DB (упрощено под MVP).

ClinicCase хранит шаблон кейса целиком в JSON (CaseTemplate из schemas.py):
так SME может править кейс одним документом, а схема БД не меняется при новых полях.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    university: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="student")  # student / teacher / admin
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ClinicCase(Base):
    __tablename__ = "clinic_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # CASE-IM-01
    title: Mapped[str] = mapped_column(String(255))
    specialty: Mapped[str] = mapped_column(String(100), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="easy")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft / published
    data: Mapped[dict] = mapped_column(JSON)  # CaseTemplate целиком
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Attempt(Base):
    """Одна попытка прохождения кейса студентом (US-02 … US-09)."""

    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("clinic_cases.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active / submitted / abandoned
    patient: Mapped[dict] = mapped_column(JSON)  # сгенерированные возраст, пол, витальные показатели
    diagnosis_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # разбор оценки + обратная связь
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    case: Mapped[ClinicCase] = relationship()
    events: Mapped[list["AttemptEvent"]] = relationship(order_by="AttemptEvent.id", cascade="all, delete-orphan")


class AttemptEvent(Base):
    """Лог попытки: вопросы студента, ответы пациента, назначенные обследования."""

    __tablename__ = "attempt_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # question / answer / test
    content: Mapped[str] = mapped_column(Text)
    # для kind=question: какие категории ключевых вопросов закрыл этот вопрос (US-03, правило 3).
    # Считается один раз в момент вопроса и сохраняется — поэтому оценка потом детерминирована.
    key_question_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    test_name: Mapped[str | None] = mapped_column(String(100), nullable=True)       # для kind=test
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Textbook(Base):
    __tablename__ = "textbooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255), default="")
    lang: Mapped[str] = mapped_column(String(10), default="en")
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded / processing / ready / failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages_count: Mapped[int] = mapped_column(Integer, default=0)
    chunks_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TextChunk(Base):
    """Фрагмент учебника + его эмбеддинг. Цитата = этот текст дословно (US-06)."""

    __tablename__ = "text_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer)  # номер страницы как в PDF (с 1)
    chapter: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)


class ChatLog(Base):
    """Вопросы к RAG-боту: нужны QA для проверки NFR-02 (время ответа) и доли fallback."""

    __tablename__ = "chat_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    fallback: Mapped[bool] = mapped_column(default=False)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    best_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
