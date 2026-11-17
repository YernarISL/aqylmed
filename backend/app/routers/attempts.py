"""Прохождение кейса студентом: старт (US-02), опрос пациента (US-03), обследования (US-13),
диагноз и отправка (US-04), оценка и обратная связь (US-07, US-08), история попыток (US-09)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ALL_TESTS
from app.db import get_db
from app.models import Attempt, AttemptEvent, User, utcnow
from app.routers.cases import card, get_published
from app.schemas import CaseTemplate, OrderTestRequest, QuestionRequest, StartAttemptRequest, SubmitRequest
from app.security import get_current_user
from app.services import icd10, patient, scoring

router = APIRouter(prefix="/api/v1/attempts", tags=["attempts"])


# ------------------------------------------------------------------ helpers


def _own_attempt(db: Session, attempt_id: int, user: User) -> Attempt:
    a = db.get(Attempt, attempt_id)
    # чужая попытка = «не найдена», чтобы не раскрывать её существование (US-09)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Attempt not found")
    return a


def _active(db: Session, attempt_id: int, user: User) -> tuple[Attempt, CaseTemplate]:
    a = _own_attempt(db, attempt_id, user)
    if a.status != "active":
        raise HTTPException(409, "Attempt is read-only (already submitted or abandoned)")
    return a, CaseTemplate(**a.case.data)


def _active_attempt_of(db: Session, user: User) -> Attempt | None:
    return db.scalar(select(Attempt).where(Attempt.user_id == user.id, Attempt.status == "active"))


def _start_payload(a: Attempt) -> dict:
    d = a.case.data
    return {
        "attempt_id": a.id,
        "case": card(a.case),
        "patient": {k: a.patient[k] for k in ("name", "age", "sex", "occupation")},
        "vitals": a.patient["vitals"],
        "chief_complaint": d["chief_complaint"],
        "started_at": a.started_at,
    }


def _event_out(e: AttemptEvent, reveal: bool) -> dict:
    out = {"id": e.id, "kind": e.kind, "content": e.content, "created_at": e.created_at}
    if e.kind == "test":
        out["test_name"] = e.test_name
    if reveal and e.kind == "question":  # категории показываем только после отправки — иначе это подсказка
        out["key_question_ids"] = e.key_question_ids or []
    return out


# ------------------------------------------------------------------ старт


@router.post("", status_code=201)
def start_attempt(req: StartAttemptRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = get_published(db, req.case_id)  # черновик → 404 «Case not available» (US-02, сценарий 4)

    current = _active_attempt_of(db, user)
    if current:
        # У студента максимум одна активная попытка (US-02, правило 4).
        # Фронт показывает диалог «прогресс будет потерян» и при подтверждении повторяет с force=true.
        if not req.force:
            raise HTTPException(
                409,
                detail={
                    "message": "You have an active case. Starting a new one will discard its progress.",
                    "active_attempt_id": current.id,
                    "active_case_id": current.case_id,
                },
            )
        current.status = "abandoned"

    t = CaseTemplate(**case.data)
    a = Attempt(user_id=user.id, case_id=case.id, patient=patient.generate_patient(t))
    db.add(a)
    db.flush()
    db.add(AttemptEvent(attempt_id=a.id, kind="answer", content=t.chief_complaint))  # первая фраза — из шаблона, без LLM
    db.commit()
    db.refresh(a)
    return _start_payload(a)


@router.get("/active")
def get_active(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = _active_attempt_of(db, user)
    if not a:
        return None
    return dict(_start_payload(a), events=[_event_out(e, reveal=False) for e in a.events])


@router.post("/{attempt_id}/abandon")
def abandon(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a, _ = _active(db, attempt_id, user)
    a.status = "abandoned"
    db.commit()
    return {"attempt_id": a.id, "status": a.status}


# ------------------------------------------------------------------ опрос и обследования


@router.post("/{attempt_id}/questions")
def ask_patient(attempt_id: int, req: QuestionRequest, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    """US-03. Пустой вопрос отсекается валидацией (422 «Type a question»), лог не меняется."""
    a, t = _active(db, attempt_id, user)
    history = [
        ("user" if e.kind == "question" else "assistant", e.content)
        for e in a.events if e.kind in ("question", "answer")
    ]
    answer, categories = patient.answer_and_classify(t, a.patient, history, req.text)
    db.add_all([
        AttemptEvent(attempt_id=a.id, kind="question", content=req.text, key_question_ids=categories),
        AttemptEvent(attempt_id=a.id, kind="answer", content=answer),
    ])
    db.commit()
    return {"answer": answer}


@router.post("/{attempt_id}/tests")
def order_test(attempt_id: int, req: OrderTestRequest, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """US-13. Результат берётся ТОЛЬКО из шаблона кейса — LLM не участвует, выдумать нечего."""
    a, t = _active(db, attempt_id, user)
    if req.name not in ALL_TESTS:
        raise HTTPException(400, {"message": "Unknown test", "allowed": ALL_TESTS})
    result = t.test_results.get(req.name, t.default_result)
    already = any(e.kind == "test" and e.test_name == req.name for e in a.events)
    if not already:  # повторное назначение не дублирует запись в логе
        db.add(AttemptEvent(attempt_id=a.id, kind="test", test_name=req.name, content=result))
        db.commit()
    return {"test": req.name, "result": result}


# ------------------------------------------------------------------ диагноз и оценка


@router.post("/{attempt_id}/submit")
def submit(attempt_id: int, req: SubmitRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """US-04 + US-07: попытка становится read-only, сразу считается оценка."""
    a, t = _active(db, attempt_id, user)
    code = icd10.normalize(req.diagnosis_code)
    if not icd10.exists(code):
        raise HTTPException(400, "Choose a diagnosis from the ICD-10 list")
    result = scoring.build_result(db, a, t, code)
    a.status, a.diagnosis_code, a.score_total = "submitted", code, result["score"]
    a.result, a.submitted_at = result, utcnow()
    db.commit()
    return dict(result, attempt_id=a.id)


@router.get("/{attempt_id}")
def get_attempt(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = _own_attempt(db, attempt_id, user)
    done = a.status == "submitted"
    return {
        **_start_payload(a),
        "status": a.status,
        "submitted_at": a.submitted_at,
        "result": a.result if done else None,
        "events": [_event_out(e, reveal=done) for e in a.events],
    }


@router.get("")
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """US-09: только свои завершённые попытки, новые сверху."""
    rows = db.scalars(
        select(Attempt)
        .where(Attempt.user_id == user.id, Attempt.status == "submitted")
        .order_by(Attempt.submitted_at.desc(), Attempt.id.desc())
    )
    return [
        {
            "attempt_id": a.id,
            "date": a.submitted_at,
            "case": {"id": a.case_id, "title": a.case.title, "specialty": a.case.specialty},
            "score": a.score_total,
            "label": (a.result or {}).get("label"),
        }
        for a in rows
    ]
