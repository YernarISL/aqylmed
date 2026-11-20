from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from sqlalchemy import func, select

from app.db import SessionLocal, init_db
from app.models import ClinicCase, User
from app.routers import attempts, auth, cases, chat, textbooks
from app.security import hash_password


def seed():
    """Для хостинга без Shell (бесплатный Render): пустая БД сама получает кейсы и первого админа.
    Ничего не перезаписывает — правки преподавателей и пароли не теряются при перезапуске."""
    from scripts.load_cases import load

    with SessionLocal() as db:
        if not db.scalar(select(func.count()).select_from(ClinicCase)):
            load(db)
        email = config.ADMIN_EMAIL.strip().lower()
        if email and config.ADMIN_PASSWORD and not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, password_hash=hash_password(config.ADMIN_PASSWORD), role="admin",
                        first_name="Admin"))
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="AQYLMED API",
    version="0.1.0",
    description="Clinic Case simulator + RAG textbook chatbot (MVP, Release 1).",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, cases.router, attempts.router, textbooks.router, chat.router):
    app.include_router(r)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "llm_provider": config.LLM_PROVIDER}
