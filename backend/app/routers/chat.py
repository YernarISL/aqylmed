"""RAG-чатбот: ответы только из проиндексированных учебников, с цитатами (US-05, US-06)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ChatLog, User
from app.schemas import ChatRequest
from app.security import get_current_user, require_staff
from app.services import rag

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/ask")
def ask(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Ответ ≤ 150 слов с цитатами, либо fallback-сообщение (LLM тогда не вызывается)."""
    return rag.ask(db, user.id, req.question)


@router.get("/logs", tags=["chat: staff"])
def logs(limit: int = Query(50, le=500), db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Для QA: последние вопросы, доля fallback и время ответа (NFR-02: max ≤ 5 с, медиана ≤ 3 с)."""
    rows = list(db.scalars(select(ChatLog).order_by(ChatLog.id.desc()).limit(limit)))
    latencies = sorted(r.latency_ms for r in rows)
    stats = {
        "count": len(rows),
        "fallback_share": round(sum(r.fallback for r in rows) / len(rows), 3) if rows else None,
        "latency_ms_median": latencies[len(latencies) // 2] if latencies else None,
        "latency_ms_max": latencies[-1] if latencies else None,
        "total_questions": db.scalar(select(func.count()).select_from(ChatLog)),
    }
    items = [
        {"id": r.id, "question": r.question, "fallback": r.fallback, "best_similarity": r.best_similarity,
         "latency_ms": r.latency_ms, "citations": len(r.citations), "created_at": r.created_at}
        for r in rows
    ]
    return {"stats": stats, "items": items}
