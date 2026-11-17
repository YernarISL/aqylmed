"""Автоматическая оценка попытки (US-07) и обратная связь (US-08).

Формула (груминг, Q3): анамнез 40 + обследования 20 + диагноз 40 = 100.
  * анамнез  = 40 × (закрытые категории ключевых вопросов / все категории)
  * обследования = 20 × (назначенные ключевые обследования / все ключевые)
  * диагноз  = 40 — верный или принятый код; 20 — смежный (related); 0 — иначе

Оценка детерминирована (US-07, правило 2): функция score() чистая — она читает только
сохранённый лог попытки и шаблон; LLM здесь не вызывается.
"""
from sqlalchemy.orm import Session

from app import config
from app.models import Attempt
from app.schemas import CaseTemplate
from app.services import icd10, rag


def score(t: CaseTemplate, asked_ids: set[str], ordered_tests: set[str], diagnosis_code: str) -> dict:
    key_ids = [kq.id for kq in t.key_questions]
    asked = [i for i in key_ids if i in asked_ids]
    history = round(config.SCORE_HISTORY * len(asked) / len(key_ids))

    key_tests_done = [x for x in t.key_tests if x in ordered_tests]
    tests = (
        round(config.SCORE_TESTS * len(key_tests_done) / len(t.key_tests)) if t.key_tests else config.SCORE_TESTS
    )

    code = icd10.normalize(diagnosis_code)
    if code in {t.diagnosis.code, *t.accepted_codes}:
        verdict, diagnosis = "correct", config.SCORE_DIAGNOSIS
    elif code in t.related_codes:
        verdict, diagnosis = "related", round(config.SCORE_DIAGNOSIS * config.RELATED_DIAGNOSIS_SHARE)
    else:
        verdict, diagnosis = "incorrect", 0

    return {
        "total": history + tests + diagnosis,
        "parts": {"history": history, "tests": tests, "diagnosis": diagnosis},
        "max_parts": {"history": config.SCORE_HISTORY, "tests": config.SCORE_TESTS, "diagnosis": config.SCORE_DIAGNOSIS},
        "diagnosis_verdict": verdict,
        "asked_key_question_ids": asked,
        "missed_key_question_ids": [i for i in key_ids if i not in asked_ids],
        "key_tests_ordered": key_tests_done,
        "key_tests_missed": [x for x in t.key_tests if x not in ordered_tests],
    }


_VERDICT_LABEL = {
    "correct": "Correct diagnosis",
    "related": "Related diagnosis — partial credit",
    "incorrect": "Incorrect diagnosis",
}


def build_result(db: Session, attempt: Attempt, t: CaseTemplate, diagnosis_code: str) -> dict:
    asked_ids = {i for e in attempt.events if e.kind == "question" for i in (e.key_question_ids or [])}
    ordered = {e.test_name for e in attempt.events if e.kind == "test"}
    s = score(t, asked_ids, ordered, diagnosis_code)

    kq_by_id = {kq.id: kq for kq in t.key_questions}
    missed_q = [kq_by_id[i] for i in s["missed_key_question_ids"]]
    missed_tests = s["key_tests_missed"]

    # Ссылки на учебник для каждого упущенного пункта (US-08) — одним батчем
    queries = [kq.reference_query or kq.label for kq in missed_q]
    queries += [t.test_reference_queries.get(x) or f"{x} in {t.diagnosis.name}" for x in missed_tests]
    refs = rag.find_references(db, queries) if queries else []
    q_refs, t_refs = refs[: len(missed_q)], refs[len(missed_q):]

    code = icd10.normalize(diagnosis_code)
    return {
        "score": s["total"],
        "parts": s["parts"],
        "max_parts": s["max_parts"],
        "label": _VERDICT_LABEL[s["diagnosis_verdict"]],
        "diagnosis": {
            "verdict": s["diagnosis_verdict"],
            "submitted": {"code": code, "name": icd10.name(code)},
            "correct": t.diagnosis.model_dump(),
            "differential": t.differential,
        },
        "history": {
            "asked": [{"id": i, "label": kq_by_id[i].label} for i in s["asked_key_question_ids"]],
            "missed": [{"id": kq.id, "label": kq.label, "reference": r} for kq, r in zip(missed_q, q_refs)],
            "questions_total": sum(1 for e in attempt.events if e.kind == "question"),
        },
        "tests": {
            "ordered": sorted(ordered),
            "key_ordered": s["key_tests_ordered"],
            "missed": [{"name": x, "reference": r} for x, r in zip(missed_tests, t_refs)],
        },
    }
