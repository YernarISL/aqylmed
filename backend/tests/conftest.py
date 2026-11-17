"""Тесты работают офлайн: LLM_PROVIDER=mock, отдельная SQLite-база во временной папке."""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="aqylmed-test-"))
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-bytes-long!"
os.environ.pop("RAG_MIN_SIMILARITY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import rag  # noqa: E402
from scripts.load_cases import load  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rag.index.invalidate()
    with SessionLocal() as db:
        load(db)
        db.add(User(email="admin@test.kz", password_hash=hash_password("admin12345"), role="admin", first_name="Admin"))
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register(client, email: str) -> dict:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "first_name": "Test"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def student(client):
    return _register(client, "student@test.kz")


@pytest.fixture
def other_student(client):
    return _register(client, "other@test.kz")


@pytest.fixture
def admin(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.kz", "password": "admin12345"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def case_id(client, headers, code: str) -> int:
    items = client.get("/api/v1/cases", headers=headers).json()["items"]
    return next(c["id"] for c in items if c["code"] == code)


# ---------------------------------------------------------------- минимальный PDF для тестов RAG


def make_pdf(pages: list[list[str]]) -> bytes:
    """Собрать простой PDF: каждая страница — список строк текста (Helvetica)."""
    objects: list[bytes] = []
    n_pages = len(pages)
    font_id = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    for i, lines in enumerate(pages):
        content_id = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        ops = ["BT", "/F1 11 Tf", "14 TL", "50 740 Td"]
        for line in lines:
            esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({esc}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


TEXTBOOK_PAGES = [
    ["Chapter 5. Ischaemic heart disease",
     "Stable angina is chest pain caused by myocardial ischaemia on exertion.",
     "First-line drugs for stable angina are beta-blockers or calcium channel blockers.",
     "Sublingual nitroglycerin is used for the acute relief of anginal pain."],
    ["Unstable angina is angina at rest or new crescendo angina.",
     "ECG changes in unstable angina include ST depression and T wave inversion.",
     "Cardiac troponin is not elevated in unstable angina, which distinguishes it from NSTEMI."],
    ["Chapter 6. Arterial hypertension",
     "Hypertension is a major cardiovascular risk factor.",
     "Smoking, high cholesterol and family history increase coronary risk."],
]


@pytest.fixture
def textbook(client, admin):
    r = client.post(
        "/api/v1/textbooks",
        headers=admin,
        data={"title": "Internal Medicine", "author": "Test Author"},
        files={"file": ("im.pdf", make_pdf(TEXTBOOK_PAGES), "application/pdf")},
    )
    assert r.status_code == 202, r.text
    book = client.get(f"/api/v1/textbooks/{r.json()['id']}", headers=admin).json()
    assert book["status"] == "ready", book
    return book
