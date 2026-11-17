"""RAG по одобренным учебникам: индексация PDF (US-10), поиск, ответы только из контекста
(US-05) и цитаты с книгой/главой/страницей (US-06).

Векторное хранилище — таблица text_chunks (эмбеддинг в JSON) + матрица numpy в памяти.
Для 2 учебников MVP (решение 2 на груминге) это проще и бесплатнее отдельной векторной БД;
при росте корпуса заменяется на pgvector без изменения API.
"""
import re
import threading
import time
from dataclasses import dataclass

import numpy as np
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import config, prompts
from app.db import SessionLocal
from app.models import ChatLog, Textbook, TextChunk
from app.services import llm


def similarity_threshold() -> float:
    """0.75 — стартовое значение для эмбеддингов Gemini (US-05, правило 2).
    Mock-векторизатор («мешок слов») даёт меньшие значения, поэтому свой порог."""
    import os

    if os.getenv("RAG_MIN_SIMILARITY"):
        return config.RAG_MIN_SIMILARITY
    return 0.3 if llm.is_mock() else config.RAG_MIN_SIMILARITY


# ============================================================ Индексация (US-10)

_CHAPTER_RE = re.compile(r"^\s*((chapter|глава|part|раздел)\s+[\w.]+.*)$", re.I | re.M)


def _outline_chapters(reader: PdfReader) -> list[tuple[int, str]]:
    """Главы из оглавления PDF (bookmarks): [(индекс_первой_страницы, название), ...]."""
    result: list[tuple[int, str]] = []
    try:
        for item in reader.outline:
            if isinstance(item, list):  # вложенные подпункты — пропускаем, нужны главы
                continue
            page = reader.get_destination_page_number(item)
            if page is not None and page >= 0:
                result.append((page, str(item.title).strip()))
    except Exception:
        return []
    return sorted(result)


def extract_pages(path: str) -> list[dict]:
    """[{page: 1, chapter: "...", text: "..."}, ...] — номера страниц как в PDF, с 1."""
    reader = PdfReader(path)
    outline = _outline_chapters(reader)
    pages, current_chapter = [], ""
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = re.sub(r"[ \t]+", " ", text).strip()
        if outline:
            current_chapter = next((t for p, t in reversed(outline) if p <= idx), current_chapter)
        else:
            m = _CHAPTER_RE.search(text)
            if m:
                current_chapter = m.group(1).strip()[:200]
        if text:
            pages.append({"page": idx + 1, "chapter": current_chapter, "text": text})
    return pages


def chunk_text(text: str, size: int = config.RAG_CHUNK_CHARS, overlap: int = config.RAG_CHUNK_OVERLAP) -> list[str]:
    """Режем страницу на куски ~size символов по границам предложений, с перекрытием.
    Кусок не выходит за страницу — поэтому у каждой цитаты точный номер страницы."""
    sentences = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    chunks, cur = [], ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if cur and len(cur) + len(s) + 1 > size:
            chunks.append(cur)
            cur = cur[-overlap:].lstrip() + " " + s if overlap else s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    # очень длинное «предложение» без точек (таблица) — режем жёстко
    out = []
    for c in chunks:
        if len(c) > size * 1.5:
            out.extend(c[i : i + size] for i in range(0, len(c), size - overlap))
        else:
            out.append(c)
    return out


def index_textbook(textbook_id: int) -> None:
    """Фоновая задача: PDF → текст по страницам → куски → эмбеддинги → БД. Статус → ready."""
    db = SessionLocal()
    try:
        book = db.get(Textbook, textbook_id)
        if not book:
            return
        book.status, book.error = "processing", None
        db.commit()

        pages = extract_pages(book.file_path)
        if not pages:
            raise ValueError("No extractable text in the PDF (scanned images need OCR first)")

        rows = [(p["page"], p["chapter"], c) for p in pages for c in chunk_text(p["text"])]
        vectors = llm.embed([f"{ch}\n{text}" if ch else text for _, ch, text in rows], task="document")

        db.execute(delete(TextChunk).where(TextChunk.textbook_id == book.id))
        db.add_all(
            TextChunk(textbook_id=book.id, page=page, chapter=chapter, text=text, embedding=vec.tolist())
            for (page, chapter, text), vec in zip(rows, vectors)
        )
        book.status, book.pages_count, book.chunks_count = "ready", len(pages), len(rows)
        db.commit()
    except Exception as e:
        db.rollback()
        book = db.get(Textbook, textbook_id)
        if book:
            book.status, book.error = "failed", str(e)[:1000]
            db.commit()
    finally:
        db.close()
        index.invalidate()


# ============================================================ Поиск


@dataclass
class Hit:
    chunk_id: int
    textbook_id: int
    textbook_title: str
    chapter: str
    page: int
    text: str
    similarity: float

    def citation(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "textbook_id": self.textbook_id,
            "book_title": self.textbook_title,
            "chapter": self.chapter,
            "page": self.page,
            "quote": self.text,
            "similarity": round(self.similarity, 3),
            "link": f"/api/v1/textbooks/{self.textbook_id}/chunks/{self.chunk_id}",
        }


class VectorIndex:
    """Матрица эмбеддингов всех готовых учебников в памяти. Перечитывается после (пере)индексации."""

    def __init__(self):
        self._lock = threading.Lock()
        self._loaded = False
        self.matrix = np.zeros((0, 1), dtype=np.float32)
        self.meta: list[tuple[int, int, str, str, int, str]] = []

    def invalidate(self):
        with self._lock:
            self._loaded = False

    def _load(self, db: Session):
        rows = db.execute(
            select(TextChunk.id, TextChunk.textbook_id, Textbook.title, TextChunk.chapter,
                   TextChunk.page, TextChunk.text, TextChunk.embedding)
            .join(Textbook, Textbook.id == TextChunk.textbook_id)
            .where(Textbook.status == "ready")
        ).all()
        self.meta = [tuple(r[:6]) for r in rows]
        self.matrix = np.array([r[6] for r in rows], dtype=np.float32) if rows else np.zeros((0, 1), np.float32)
        self._loaded = True

    def search_many(self, db: Session, queries: list[str], k: int) -> list[list[Hit]]:
        with self._lock:
            if not self._loaded:
                self._load(db)
            matrix, meta = self.matrix, self.meta
        if not meta or not queries:
            return [[] for _ in queries]
        q = llm.embed(queries, task="query")
        if q.shape[1] != matrix.shape[1]:
            raise llm.LLMError("Embedding size changed — re-index textbooks")
        sims = q @ matrix.T  # векторы нормированы → это косинусное сходство
        result = []
        for row in sims:
            top = np.argsort(-row)[:k]
            result.append([Hit(*meta[i], similarity=float(row[i])) for i in top])
        return result

    def search(self, db: Session, query: str, k: int = config.RAG_TOP_K) -> list[Hit]:
        return self.search_many(db, [query], k)[0]


index = VectorIndex()


# ============================================================ Ответ бота (US-05, US-06)

_CITE_RE = re.compile(r"\[(\d+)\]")


def ask(db: Session, user_id: int, question: str) -> dict:
    started = time.perf_counter()
    hits = index.search(db, question, config.RAG_TOP_K)
    best = hits[0].similarity if hits else None
    relevant = [h for h in hits if h.similarity >= similarity_threshold()]

    answer, citations, fallback = config.RAG_FALLBACK_MESSAGE, [], True
    if relevant:  # ниже порога LLM вообще не вызывается (US-05, правило 2)
        text = _mock_rag_answer(question, relevant) if llm.is_mock() else _llm_rag_answer(question, relevant)
        if text and "NOT_FOUND" not in text:
            cited = sorted({int(n) for n in _CITE_RE.findall(text) if 1 <= int(n) <= len(relevant)})
            if not cited:  # у каждого ответа должна быть хотя бы одна цитата (US-05, правило 3)
                cited = [1]
                text += " [1]"
            answer = _limit_words(text, config.RAG_MAX_ANSWER_WORDS)
            citations = [dict(relevant[n - 1].citation(), ref=n) for n in cited]
            fallback = False

    latency_ms = int((time.perf_counter() - started) * 1000)
    db.add(ChatLog(user_id=user_id, question=question, answer=answer, fallback=fallback,
                   citations=citations, best_similarity=best, latency_ms=latency_ms))
    db.commit()
    return {"answer": answer, "fallback": fallback, "citations": citations, "latency_ms": latency_ms}


def _llm_rag_answer(question: str, hits: list[Hit]) -> str | None:
    passages = "\n\n".join(
        f"[{i}] ({h.textbook_title}, {h.chapter or 'no chapter'}, p. {h.page})\n{h.text}"
        for i, h in enumerate(hits, 1)
    )
    try:
        return llm.generate(
            prompts.RAG_SYSTEM.format(max_words=config.RAG_MAX_ANSWER_WORDS),
            [("user", prompts.RAG_USER.format(passages=passages, question=question))],
            max_tokens=400,
            temperature=0.0,
        )
    except llm.LLMError:
        return None  # → fallback-сообщение, а не выдуманный ответ


def _mock_rag_answer(question: str, hits: list[Hit]) -> str:
    """Экстрактивный ответ: 2 предложения лучшего фрагмента, больше всего похожие на вопрос."""
    q = set(llm.tokens(question))
    sentences = re.split(r"(?<=[.!?])\s+", hits[0].text)
    ranked = sorted(sentences, key=lambda s: -len(q & set(llm.tokens(s))))[:2]
    return " ".join(s.strip() for s in ranked if s.strip()) + " [1]"


def _limit_words(text: str, n: int) -> str:
    words = text.split()
    return text if len(words) <= n else " ".join(words[:n]) + "…"


# ============================================================ Ссылки для обратной связи (US-08)


def find_references(db: Session, queries: list[str]) -> list[dict | None]:
    """Лучший фрагмент учебника для каждого запроса (без вызова LLM, один батч эмбеддингов)."""
    try:
        results = index.search_many(db, queries, k=1)
    except llm.LLMError:
        return [None] * len(queries)
    thr = similarity_threshold()
    return [hits[0].citation() if hits and hits[0].similarity >= thr else None for hits in results]
