from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.db import init_db
from app.routers import attempts, auth, cases, chat, textbooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
