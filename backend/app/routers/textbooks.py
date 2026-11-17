"""Учебники для RAG (US-10) и просмотр цитат (US-06, ссылки из обратной связи US-08)."""
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.models import Textbook, TextChunk, User
from app.security import get_current_user, require_admin
from app.services import rag

router = APIRouter(prefix="/api/v1/textbooks", tags=["textbooks"])


def book_out(b: Textbook) -> dict:
    return {
        "id": b.id, "title": b.title, "author": b.author, "lang": b.lang, "status": b.status,
        "error": b.error, "pages_count": b.pages_count, "chunks_count": b.chunks_count,
        "created_at": b.created_at,
    }


@router.post("", status_code=202)
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="Approved textbook PDF"),
    title: str = Form(..., min_length=1),
    author: str = Form(""),
    lang: str = Form("en"),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Загрузка PDF. Индексация идёт в фоне: статус processing → ready (или failed с причиной)."""
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are accepted")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB")

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = config.UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"  # своё имя файла — никаких путей от клиента
    path.write_bytes(data)

    book = Textbook(title=title.strip(), author=author.strip(), lang=lang, file_path=str(path),
                    status="processing", uploaded_by_user_id=user.id)
    db.add(book)
    db.commit()
    background.add_task(rag.index_textbook, book.id)
    return book_out(book)


@router.get("")
def list_books(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [book_out(b) for b in db.scalars(select(Textbook).order_by(Textbook.id))]


@router.get("/{book_id}")
def get_book(book_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    b = db.get(Textbook, book_id)
    if not b:
        raise HTTPException(404, "Textbook not found")
    return book_out(b)


@router.post("/{book_id}/reindex", status_code=202)
def reindex(book_id: int, background: BackgroundTasks, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    b = db.get(Textbook, book_id)
    if not b:
        raise HTTPException(404, "Textbook not found")
    b.status = "processing"
    db.commit()
    background.add_task(rag.index_textbook, b.id)
    return book_out(b)


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    b = db.get(Textbook, book_id)
    if not b:
        raise HTTPException(404, "Textbook not found")
    db.execute(delete(TextChunk).where(TextChunk.textbook_id == b.id))
    Path(b.file_path).unlink(missing_ok=True)
    db.delete(b)
    db.commit()
    rag.index.invalidate()


@router.get("/{book_id}/chunks/{chunk_id}")
def get_chunk(book_id: int, chunk_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Открыть цитату: книга, глава, страница и дословный проиндексированный текст (US-06)."""
    c = db.get(TextChunk, chunk_id)
    if not c or c.textbook_id != book_id:
        raise HTTPException(404, "Fragment not found")
    b = db.get(Textbook, book_id)
    return {"chunk_id": c.id, "textbook_id": b.id, "book_title": b.title, "author": b.author,
            "chapter": c.chapter, "page": c.page, "text": c.text}
