"""Каталог кейсов (US-01, US-11) и управление шаблонами для преподавателя/SME."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import prompts
from app.config import ALL_TESTS, TEST_CATALOGUE
from app.db import get_db
from app.models import ClinicCase, User
from app.schemas import CaseTemplate, GenerateCaseRequest
from app.security import get_current_user, require_staff
from app.services import icd10, llm

router = APIRouter(prefix="/api/v1", tags=["cases"])

NOT_AVAILABLE = "Case not available"


def card(c: ClinicCase) -> dict:
    """Карточка каталога: только то, что не выдаёт диагноз."""
    d = c.data
    return {
        "id": c.id,
        "code": c.code,
        "title": c.title,
        "specialty": c.specialty,
        "difficulty": c.difficulty,
        "chief_complaint": d["chief_complaint"],
        "patient": {
            "sex": d["patient"]["sex"],
            "age_range": [int(d["patient"]["age"]["min"]), int(d["patient"]["age"]["max"])],
        },
    }


def get_published(db: Session, case_id: int) -> ClinicCase:
    c = db.get(ClinicCase, case_id)
    if not c or c.status != "published":
        raise HTTPException(404, NOT_AVAILABLE)
    return c


# ------------------------------------------------------------- студент


@router.get("/cases")
def list_cases(
    specialty: str | None = Query(None, description="US-11: фильтр по специальности"),
    difficulty: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """US-01: только опубликованные кейсы; черновики скрыты."""
    q = select(ClinicCase).where(ClinicCase.status == "published")
    if specialty:
        q = q.where(func.lower(ClinicCase.specialty) == specialty.lower())
    if difficulty:
        q = q.where(ClinicCase.difficulty == difficulty)
    items = [card(c) for c in db.scalars(q.order_by(ClinicCase.specialty, ClinicCase.id))]
    return {"count": len(items), "items": items}


@router.get("/cases/specialties")
def specialties(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(ClinicCase.specialty, func.count())
        .where(ClinicCase.status == "published")
        .group_by(ClinicCase.specialty)
        .order_by(ClinicCase.specialty)
    ).all()
    return [{"specialty": s, "count": n} for s, n in rows]


@router.get("/cases/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return card(get_published(db, case_id))


@router.get("/tests")
def test_catalogue(_: User = Depends(get_current_user)):
    """US-13: фиксированный список обследований, сгруппированный для UI."""
    return TEST_CATALOGUE


@router.get("/icd10")
def icd10_search(q: str = "", limit: int = Query(20, le=100), _: User = Depends(get_current_user)):
    """US-04: автодополнение диагноза по коду или названию."""
    return icd10.search(q, limit)


# ------------------------------------------------------------- преподаватель / SME


@router.get("/admin/cases", tags=["cases: staff"])
def admin_list(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    q = select(ClinicCase).order_by(ClinicCase.id)
    if status:
        q = q.where(ClinicCase.status == status)
    return [dict(card(c), status=c.status, diagnosis=c.data["diagnosis"]) for c in db.scalars(q)]


@router.get("/admin/cases/{case_id}", tags=["cases: staff"])
def admin_get(case_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    c = db.get(ClinicCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    return {"id": c.id, "status": c.status, "data": c.data}


def _save(db: Session, t: CaseTemplate, user: User, case: ClinicCase | None = None) -> ClinicCase:
    clash = db.scalar(select(ClinicCase).where(ClinicCase.code == t.code))
    if clash and (case is None or clash.id != case.id):
        raise HTTPException(409, f"Case code {t.code} already exists")
    case = case or ClinicCase(created_by_user_id=user.id)
    case.code, case.title, case.specialty, case.difficulty = t.code, t.title, t.specialty, t.difficulty
    case.status, case.data = t.status, t.model_dump()
    db.add(case)
    db.commit()
    return case


@router.post("/admin/cases", status_code=201, tags=["cases: staff"])
def create_case(t: CaseTemplate, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    c = _save(db, t, user)
    return {"id": c.id, "status": c.status}


@router.put("/admin/cases/{case_id}", tags=["cases: staff"])
def update_case(case_id: int, t: CaseTemplate, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    c = db.get(ClinicCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    c = _save(db, t, user, c)
    return {"id": c.id, "status": c.status}


def _set_status(db: Session, case_id: int, status: str) -> dict:
    c = db.get(ClinicCase, case_id)
    if not c:
        raise HTTPException(404, "Case not found")
    c.status = status
    c.data = {**c.data, "status": status}
    db.commit()
    return {"id": c.id, "status": c.status}


@router.post("/admin/cases/{case_id}/publish", tags=["cases: staff"])
def publish(case_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    """Публикация — только после проверки SME (TSIS 6-7, п. 10: не публиковать непроверенные кейсы)."""
    return _set_status(db, case_id, "published")


@router.post("/admin/cases/{case_id}/unpublish", tags=["cases: staff"])
def unpublish(case_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    return _set_status(db, case_id, "draft")


@router.post("/admin/cases/generate", status_code=201, tags=["cases: staff"])
def generate_case(req: GenerateCaseRequest, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """LLM пишет ЧЕРНОВИК шаблона. Студенты его не видят, пока SME не опубликует."""
    if llm.is_mock():
        raise HTTPException(503, "Case generation needs a real LLM (LLM_PROVIDER=gemini)")
    prefix = "".join(w[0] for w in req.specialty.upper().split() if "A" <= w[0] <= "Z")[:4] or "GEN"
    prompt = prompts.GENERATE_CASE.format(
        disease=req.disease, specialty=req.specialty, difficulty=req.difficulty, prefix=prefix,
        tests=ALL_TESTS, icd=[i["code"] for i in icd10.search(limit=10_000)],
        schema=json.dumps(CaseTemplate.model_json_schema(), ensure_ascii=False),
    )
    last_error = None
    for _ in range(2):  # 2 попытки, если JSON получился невалидным
        try:
            data = llm.generate_json(prompts.GENERATE_CASE_SYSTEM, prompt, max_tokens=6000, temperature=0.4)
            data["status"] = "draft"
            t = CaseTemplate(**data)
            break
        except (ValidationError, ValueError, llm.LLMError) as e:
            last_error = e
    else:
        raise HTTPException(502, f"Model returned an invalid case: {last_error}")

    # код может совпасть с существующим — подбираем свободный номер
    n = 1
    while db.scalar(select(ClinicCase).where(ClinicCase.code == t.code)):
        t.code = f"CASE-{prefix}-{90 + n:02d}"
        n += 1
    c = _save(db, t, user)
    return {"id": c.id, "status": c.status, "data": c.data}
