"""Виртуальный пациент (US-02, US-03).

Главная защита от галлюцинаций — LLM получает только «лист фактов» (fact sheet):
диагноз, результаты анализов и ключевые вопросы туда не попадают. Чего модель не знает —
того она не сможет проболтать (US-03, бизнес-правило 1).
"""
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor

from app import prompts
from app.schemas import CaseTemplate
from app.services import llm

_pool = ThreadPoolExecutor(max_workers=8)

DIAGNOSIS_REPLY = "I hoped you could tell me, doctor."
NEUTRAL_REPLY = "No, nothing like that."
LLM_DOWN_REPLY = "Sorry, doctor, could you repeat the question?"


# ---------------------------------------------------------------- генерация пациента


def generate_patient(t: CaseTemplate, rng: random.Random | None = None) -> dict:
    """Возраст и витальные показатели — случайно внутри диапазонов шаблона (US-02, правило 2)."""
    rng = rng or random.Random()
    v = t.vitals
    systolic = rng.randint(int(v.systolic_bp.min), int(v.systolic_bp.max))
    diastolic = rng.randint(int(v.diastolic_bp.min), int(v.diastolic_bp.max))
    diastolic = min(diastolic, systolic - 20)  # физиологически: пульсовое давление ≥ 20
    diastolic = max(diastolic, int(v.diastolic_bp.min))
    return {
        "name": t.patient.name,
        "sex": t.patient.sex,
        "age": rng.randint(int(t.patient.age.min), int(t.patient.age.max)),
        "occupation": t.patient.occupation,
        "vitals": {
            "temperature_c": round(rng.uniform(v.temperature_c.min, v.temperature_c.max), 1),
            "heart_rate_bpm": rng.randint(int(v.heart_rate_bpm.min), int(v.heart_rate_bpm.max)),
            "blood_pressure": f"{systolic}/{diastolic}",
            "systolic_bp": systolic,
            "diastolic_bp": diastolic,
            "resp_rate": rng.randint(int(v.resp_rate.min), int(v.resp_rate.max)),
            "spo2_pct": rng.randint(int(v.spo2_pct.min), int(v.spo2_pct.max)),
        },
    }


def fact_sheet(t: CaseTemplate, patient: dict) -> dict:
    """Только то, что знает пациент. Витальные показатели и всё ниже «эталона» — скрыты."""
    return {
        "name": patient["name"],
        "age": patient["age"],
        "sex": patient["sex"],
        "occupation": patient["occupation"],
        "chief_complaint": t.chief_complaint,
        "history_present_illness": t.history_present_illness,
        "symptoms": [s.model_dump() for s in t.symptoms],
        "negative_symptoms": t.negative_symptoms,
        "past_medical_history": t.past_medical_history,
        "medications": t.medications,
        "allergies": t.allergies,
        "family_history": t.family_history,
        "social_history": t.social_history,
    }


# ---------------------------------------------------------------- ответ пациента


def answer(t: CaseTemplate, patient: dict, history: list[tuple[str, str]], question: str) -> str:
    if llm.is_mock():
        return _mock_answer(t, patient, question)
    system = prompts.PATIENT_SYSTEM.format(
        fact_sheet=json.dumps(fact_sheet(t, patient), ensure_ascii=False, indent=2),
        personality=t.personality,
    )
    try:
        return llm.generate(system, [*history, ("user", question)], max_tokens=200, temperature=0.3)
    except llm.LLMError:
        return LLM_DOWN_REPLY


def answer_and_classify(
    t: CaseTemplate, patient: dict, history: list[tuple[str, str]], question: str
) -> tuple[str, list[str]]:
    """Ответ пациента и классификация вопроса идут параллельно — время ответа = max, а не сумма."""
    fut_answer = _pool.submit(answer, t, patient, history, question)
    categories = classify(t, question)
    return fut_answer.result(), categories


# ---------------------------------------------------------------- ключевые вопросы


def classify(t: CaseTemplate, question: str) -> list[str]:
    """К каким категориям ключевых вопросов относится вопрос (US-03, правило 3).

    1) ключевые слова из шаблона — быстро, без сети;
    2) если совпадений нет и LLM доступна — классификация по смыслу.
    """
    q = question.lower()
    matched = [kq.id for kq in t.key_questions if any(kw.lower() in q for kw in kq.keywords)]
    if matched or llm.is_mock():
        return matched
    cats = "\n".join(f"- {kq.id}: {kq.label}" for kq in t.key_questions)
    try:
        data = llm.generate_json(
            prompts.CLASSIFY_SYSTEM,
            prompts.CLASSIFY_USER.format(categories=cats, question=question),
            max_tokens=100,
            temperature=0.0,
        )
    except (llm.LLMError, ValueError):
        return []
    valid = {kq.id for kq in t.key_questions}
    return [c for c in data.get("categories", []) if c in valid]


# ---------------------------------------------------------------- mock-пациент

_DIAGNOSIS_RE = re.compile(r"diagnos|what do i have|what('s| is) wrong with me|диагноз|чем я болен|что со мной", re.I)
_STOP = {w[:5] for w in (
    "what when where which have does your you the and did any for with how that this there doctor "
    "tell about feel feeling been ever like please could would".split()
)}


def _mock_answer(t: CaseTemplate, patient: dict, question: str) -> str:
    """Офлайн-пациент: находит в листе фактов предложение с наибольшим пересечением слов."""
    if _DIAGNOSIS_RE.search(question):
        return DIAGNOSIS_REPLY
    q = set(llm.tokens(question)) - _STOP
    if not q:
        return NEUTRAL_REPLY

    facts: list[str] = []
    facts += re.split(r"(?<=[.!?])\s+", t.history_present_illness)
    facts += [f"{s.name}: {s.details}" for s in t.symptoms]
    facts += [f"No {n}." for n in t.negative_symptoms]
    facts += [
        f"Past illnesses: {t.past_medical_history}",
        f"Medications: {t.medications}",
        f"Allergies: {t.allergies}",
        f"Family history: {t.family_history}",
        f"Lifestyle, smoking, alcohol, work: {t.social_history}",
        f"I am {patient['age']} years old, I work as {patient['occupation']}.",
    ]
    best, best_score = None, 0
    for fact in facts:
        score = len(q & set(llm.tokens(fact)))
        if score > best_score:
            best, best_score = fact, score
    return best if best else NEUTRAL_REPLY
