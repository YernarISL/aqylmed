"""US-02 (старт), US-03 (опрос), US-13 (обследования), US-04 (диагноз), US-07 (оценка),
US-08 (обратная связь), US-09 (история). Общий тестовый кейс — CASE-IM-01."""
import json
from pathlib import Path

from app.schemas import CaseTemplate
from app.services.scoring import score
from tests.conftest import case_id

TEMPLATE = CaseTemplate(**json.loads(
    (Path(__file__).resolve().parent.parent / "data/cases/case_im_01_chest_pain.json").read_text(encoding="utf-8")
))

# По одному вопросу на каждую из 8 категорий ключевых вопросов CASE-IM-01
KEY_QUESTIONS = {
    "onset": "When did the pain start?",
    "location": "Where exactly do you feel the pain?",
    "character": "Can you describe the pain?",
    "radiation": "Does the pain spread anywhere?",
    "provocation": "Does it come on with exertion, like on the stairs?",
    "relief_duration": "How many minutes does it take to go away?",
    "associated": "Do you sweat during the attack?",
    "risk_factors": "Do you smoke?",
}


def start(client, headers, code="CASE-IM-01", force=False):
    return client.post("/api/v1/attempts", json={"case_id": case_id(client, headers, code), "force": force},
                       headers=headers)


def ask(client, headers, attempt_id, text):
    return client.post(f"/api/v1/attempts/{attempt_id}/questions", json={"text": text}, headers=headers)


def run_attempt(client, headers, questions: list[str], tests: list[str], diagnosis: str) -> dict:
    a = start(client, headers).json()["attempt_id"]
    for q in questions:
        assert ask(client, headers, a, q).status_code == 200
    for t in tests:
        assert client.post(f"/api/v1/attempts/{a}/tests", json={"name": t}, headers=headers).status_code == 200
    r = client.post(f"/api/v1/attempts/{a}/submit", json={"diagnosis_code": diagnosis}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ US-02


def test_us02_happy_path_values_inside_ranges(client, student):
    r = start(client, student)
    assert r.status_code == 201
    d = r.json()
    assert d["patient"]["sex"] == "male" and 50 <= d["patient"]["age"] <= 65
    assert d["chief_complaint"]
    v, rng = d["vitals"], TEMPLATE.vitals
    assert rng.temperature_c.min <= v["temperature_c"] <= rng.temperature_c.max
    assert rng.heart_rate_bpm.min <= v["heart_rate_bpm"] <= rng.heart_rate_bpm.max
    assert rng.systolic_bp.min <= v["systolic_bp"] <= rng.systolic_bp.max
    assert rng.diastolic_bp.min <= v["diastolic_bp"] <= rng.diastolic_bp.max
    assert rng.resp_rate.min <= v["resp_rate"] <= rng.resp_rate.max
    assert rng.spo2_pct.min <= v["spo2_pct"] <= rng.spo2_pct.max


def test_us02_new_attempt_each_time(client, student):
    first = run_attempt(client, student, [], [], "I20.0")
    second = start(client, student).json()
    assert second["attempt_id"] != first["attempt_id"]
    old = client.get(f"/api/v1/attempts/{first['attempt_id']}", headers=student).json()
    assert old["status"] == "submitted" and old["result"]["score"] == first["score"]


def test_us02_active_case_guard(client, student):
    a = start(client, student).json()["attempt_id"]
    r = start(client, student, code="CASE-IM-02")
    assert r.status_code == 409
    assert r.json()["detail"]["active_attempt_id"] == a
    # «Cancel» — активная попытка не изменилась
    assert client.get("/api/v1/attempts/active", headers=student).json()["attempt_id"] == a
    # «Continue» — старая попытка брошена, создана новая
    b = start(client, student, code="CASE-IM-02", force=True).json()["attempt_id"]
    assert client.get(f"/api/v1/attempts/{a}", headers=student).json()["status"] == "abandoned"
    assert client.get("/api/v1/attempts/active", headers=student).json()["attempt_id"] == b


def test_us02_draft_protection(client, student, admin):
    draft = next(c for c in client.get("/api/v1/admin/cases", headers=admin).json() if c["status"] == "draft")
    r = client.post("/api/v1/attempts", json={"case_id": draft["id"]}, headers=student)
    assert r.status_code == 404 and r.json()["detail"] == "Case not available"
    assert client.get("/api/v1/attempts/active", headers=student).json() is None


# ------------------------------------------------------------------ US-03


def test_us03_stored_fact_and_key_question_logged(client, student):
    a = start(client, student).json()["attempt_id"]
    r = ask(client, student, a, "Does the pain spread anywhere?")
    assert "left arm" in r.json()["answer"].lower()
    # до отправки категории не раскрываются студенту
    events = client.get(f"/api/v1/attempts/{a}", headers=student).json()["events"]
    assert "key_question_ids" not in events[-2]
    client.post(f"/api/v1/attempts/{a}/submit", json={"diagnosis_code": "I20.0"}, headers=student)
    events = client.get(f"/api/v1/attempts/{a}", headers=student).json()["events"]
    q = next(e for e in events if e["kind"] == "question")
    assert q["key_question_ids"] == ["radiation"]


def test_us03_fact_not_stored_gives_neutral_answer(client, student):
    a = start(client, student).json()["attempt_id"]
    answer = ask(client, student, a, "Have you travelled abroad recently?").json()["answer"]
    assert answer.lower().startswith("no")


def test_us03_diagnosis_request_stays_in_role(client, student):
    a = start(client, student).json()["attempt_id"]
    answer = ask(client, student, a, "What is my diagnosis?").json()["answer"]
    assert "angina" not in answer.lower() and "doctor" in answer.lower()


def test_us03_empty_input_rejected(client, student):
    a = start(client, student).json()["attempt_id"]
    before = len(client.get(f"/api/v1/attempts/{a}", headers=student).json()["events"])
    r = ask(client, student, a, "   ")
    assert r.status_code == 422 and "Type a question" in r.text
    assert len(client.get(f"/api/v1/attempts/{a}", headers=student).json()["events"]) == before


# ------------------------------------------------------------------ US-13


def test_us13_order_test_returns_stored_result(client, student):
    a = start(client, student).json()["attempt_id"]
    r = client.post(f"/api/v1/attempts/{a}/tests", json={"name": "ECG"}, headers=student).json()
    assert r["result"] == TEMPLATE.test_results["ECG"]
    # обследование без изменений в шаблоне → норма
    r = client.post(f"/api/v1/attempts/{a}/tests", json={"name": "Urinalysis"}, headers=student).json()
    assert r["result"] == TEMPLATE.default_result
    events = client.get(f"/api/v1/attempts/{a}", headers=student).json()["events"]
    assert [e["test_name"] for e in events if e["kind"] == "test"] == ["ECG", "Urinalysis"]


def test_us13_unknown_test(client, student):
    a = start(client, student).json()["attempt_id"]
    assert client.post(f"/api/v1/attempts/{a}/tests", json={"name": "MRI of the soul"}, headers=student).status_code == 400


# ------------------------------------------------------------------ US-04 + US-07


def test_us07_complete_attempt_100(client, student):
    r = run_attempt(client, student, list(KEY_QUESTIONS.values()), ["ECG", "Troponin I"], "I20.0")
    assert r["score"] == 100
    assert r["parts"] == {"history": 40, "tests": 20, "diagnosis": 40}


def test_us07_missed_questions_90(client, student):
    six = list(KEY_QUESTIONS.values())[:6]
    r = run_attempt(client, student, six, ["ECG", "Troponin I"], "I20.0")
    assert r["score"] == 90 and r["parts"] == {"history": 30, "tests": 20, "diagnosis": 40}
    assert {m["id"] for m in r["history"]["missed"]} == {"associated", "risk_factors"}


def test_us07_related_diagnosis_partial_credit_60(client, student):
    six = list(KEY_QUESTIONS.values())[:6]
    r = run_attempt(client, student, six, ["ECG"], "I21.4")
    assert r["score"] == 60 and r["parts"] == {"history": 30, "tests": 10, "diagnosis": 20}
    assert r["label"] == "Related diagnosis — partial credit"


def test_us07_scoring_is_deterministic():
    args = (TEMPLATE, {"onset", "radiation"}, {"ECG"}, "I20.0")
    assert score(*args) == score(*args)


def test_us04_submitted_attempt_is_read_only(client, student):
    a = start(client, student).json()["attempt_id"]
    assert client.post(f"/api/v1/attempts/{a}/submit", json={"diagnosis_code": "I20.0"}, headers=student).status_code == 200
    assert ask(client, student, a, "Anything else?").status_code == 409
    assert client.post(f"/api/v1/attempts/{a}/tests", json={"name": "ECG"}, headers=student).status_code == 409
    assert client.post(f"/api/v1/attempts/{a}/submit", json={"diagnosis_code": "I20.0"}, headers=student).status_code == 409


def test_us04_diagnosis_must_be_from_icd_list(client, student):
    a = start(client, student).json()["attempt_id"]
    r = client.post(f"/api/v1/attempts/{a}/submit", json={"diagnosis_code": "X99.9"}, headers=student)
    assert r.status_code == 400
    assert client.get("/api/v1/attempts/active", headers=student).json()["attempt_id"] == a


# ------------------------------------------------------------------ US-08


def test_us08_feedback_has_textbook_references(client, student, textbook):
    r = run_attempt(client, student, [KEY_QUESTIONS["onset"]], [], "I21.4")
    missed_ecg = next(t for t in r["tests"]["missed"] if t["name"] == "ECG")
    ref = missed_ecg["reference"]
    assert ref and ref["book_title"] == "Internal Medicine" and ref["page"] == 2
    chunk = client.get(ref["link"], headers=student).json()
    assert chunk["text"] == ref["quote"]
    assert r["diagnosis"]["correct"] == {"code": "I20.0", "name": "Unstable angina"}


# ------------------------------------------------------------------ US-09


def test_us09_history_newest_first_and_private(client, student, other_student):
    first = run_attempt(client, student, [], ["ECG"], "I21.4")
    second = run_attempt(client, student, list(KEY_QUESTIONS.values()), ["ECG", "Troponin I"], "I20.0")
    run_attempt(client, other_student, [], [], "I10")

    rows = client.get("/api/v1/attempts", headers=student).json()
    assert [r["attempt_id"] for r in rows] == [second["attempt_id"], first["attempt_id"]]
    assert [r["score"] for r in rows] == [100, first["score"]]
    assert all(r["case"]["title"] and r["date"] for r in rows)

    # чужую попытку нельзя открыть
    assert client.get(f"/api/v1/attempts/{first['attempt_id']}", headers=other_student).status_code == 404
