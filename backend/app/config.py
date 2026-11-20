"""Все настройки в одном месте. Значения берутся из .env (см. .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# --- База данных ---
# SQLite для прототипа. Для Postgres: postgresql+psycopg2://user:pass@host:5432/aqylmed
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'aqylmed.db'}")
# Render/Heroku иногда отдают старую схему postgres:// — SQLAlchemy 2 её не принимает
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# Первый админ создаётся при старте, если задан (на бесплатном Render нет Shell для scripts.create_user)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# --- Авторизация (JWT) ---
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-in-production-32b")
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", 60 * 24))

# --- LLM ---
# "gemini" — настоящий Gemini (нужен GEMINI_API_KEY);
# "mock"   — локальные заглушки без интернета и без затрат (для тестов и демо, бюджет $0).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", 768))
LLM_TIMEOUT_SECONDS = _float("LLM_TIMEOUT_SECONDS", 4.5)  # NFR-02: ответ ≤ 5 с

# --- RAG (US-05, US-06, US-10) ---
RAG_TOP_K = int(os.getenv("RAG_TOP_K", 5))                    # бизнес-правило US-05 (1)
RAG_MIN_SIMILARITY = _float("RAG_MIN_SIMILARITY", 0.75)       # бизнес-правило US-05 (2), тюнится на 20 вопросах
RAG_MAX_ANSWER_WORDS = int(os.getenv("RAG_MAX_ANSWER_WORDS", 150))  # бизнес-правило US-05 (4)
RAG_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", 900))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", 150))
RAG_FALLBACK_MESSAGE = (
    "Information not found in the indexed medical textbooks. "
    "Please ask your teacher or consult the course materials."
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 100))

# --- Скоринг (US-07). Веса согласованы на груминге (Q3), SME подтверждает ---
SCORE_HISTORY = 40
SCORE_TESTS = 20
SCORE_DIAGNOSIS = 40
RELATED_DIAGNOSIS_SHARE = 0.5  # смежный диагноз = половина баллов (20 из 40)

# --- Фиксированный каталог обследований (US-13) ---
# В шаблоне кейса заполняются только изменённые результаты, остальное = норма (default_result).
TEST_CATALOGUE: dict[str, list[str]] = {
    "Physical examination": [
        "General inspection",
        "Lung auscultation",
        "Lung percussion",
        "Heart auscultation",
        "Abdominal palpation",
        "Neurological examination",
    ],
    "Laboratory": [
        "Complete blood count",
        "Urinalysis",
        "Blood biochemistry",
        "C-reactive protein",
        "Troponin I",
        "Lipid profile",
        "Blood glucose",
        "Serum iron and ferritin",
        "Coagulation panel",
    ],
    "Instrumental": [
        "ECG",
        "Chest X-ray",
        "Abdominal ultrasound",
        "Echocardiography",
        "Head CT",
        "Pulse oximetry",
    ],
}
ALL_TESTS: list[str] = [t for group in TEST_CATALOGUE.values() for t in group]

# Пять витальных показателей, которые генерируются при старте кейса (US-02)
VITAL_SIGNS = ["temperature_c", "heart_rate_bpm", "systolic_bp", "diastolic_bp", "resp_rate", "spo2_pct"]
