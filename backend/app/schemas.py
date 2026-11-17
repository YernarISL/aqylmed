"""Pydantic-схемы: шаблон клинического кейса и тела запросов/ответов API."""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.config import ALL_TESTS
from app.services import icd10

# ======================= Шаблон клинического кейса =======================


class Range(BaseModel):
    min: float
    max: float

    @model_validator(mode="after")
    def check_order(self):
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) > max ({self.max})")
        return self


class VitalRanges(BaseModel):
    """Допустимые диапазоны. При старте кейса значения выбираются случайно внутри (US-02, правило 2)."""

    temperature_c: Range
    heart_rate_bpm: Range
    systolic_bp: Range
    diastolic_bp: Range
    resp_rate: Range
    spo2_pct: Range


class PatientTemplate(BaseModel):
    name: str
    sex: Literal["male", "female"]
    age: Range
    occupation: str = ""


class Symptom(BaseModel):
    name: str
    details: str  # когда началось, характер, что усиливает/облегчает


class KeyQuestion(BaseModel):
    """Одна из категорий ключевых вопросов анамнеза (в эталоне их 8)."""

    id: str = Field(pattern=r"^[a-z0-9_]+$")  # radiation, onset, ...
    label: str                                  # «Иррадиация боли» — видит студент в разборе
    keywords: list[str] = []                    # быстрые совпадения без LLM (нижний регистр, подстроки)
    reference_query: str = ""                   # запрос в учебник для ссылки в обратной связи (US-08)


class DiagnosisRef(BaseModel):
    code: str
    name: str


class CaseTemplate(BaseModel):
    code: str = Field(pattern=r"^CASE-[A-Z]+-\d{2,}$")  # CASE-IM-01
    title: str              # без диагноза! видят студенты в каталоге
    specialty: str
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    status: Literal["draft", "published"] = "draft"

    # --- это знает «пациент» (LLM) ---
    patient: PatientTemplate
    personality: str = "Calm, answers briefly"
    chief_complaint: str            # первая фраза пациента
    history_present_illness: str
    symptoms: list[Symptom]
    negative_symptoms: list[str]    # чего НЕТ — защита от выдумок
    past_medical_history: str = "No serious illnesses"
    medications: str = "Takes no medications"
    allergies: str = "None"
    family_history: str = "Does not know"
    social_history: str = ""

    # --- этого пациент НЕ знает (эталон для оценки) ---
    vitals: VitalRanges
    test_results: dict[str, str] = Field(description="Ключ — из каталога обследований, значение — точный результат")
    default_result: str = "No abnormalities detected"
    key_tests: list[str]
    test_reference_queries: dict[str, str] = {}
    diagnosis: DiagnosisRef
    accepted_codes: list[str] = []   # другие коды МКБ-10, засчитываемые полностью
    related_codes: list[str] = []    # смежные диагнозы — частичный балл
    differential: list[str] = []
    key_questions: list[KeyQuestion] = Field(min_length=1)

    @field_validator("test_results", "test_reference_queries")
    @classmethod
    def tests_from_catalogue(cls, v: dict[str, str]):
        bad = [k for k in v if k not in ALL_TESTS]
        if bad:
            raise ValueError(f"Unknown tests: {bad}. Allowed: {ALL_TESTS}")
        return v

    @field_validator("key_tests")
    @classmethod
    def key_tests_from_catalogue(cls, v: list[str]):
        bad = [k for k in v if k not in ALL_TESTS]
        if bad:
            raise ValueError(f"Unknown key tests: {bad}. Allowed: {ALL_TESTS}")
        return v

    @model_validator(mode="after")
    def check_codes_and_ids(self):
        codes = [self.diagnosis.code, *self.accepted_codes, *self.related_codes]
        unknown = [c for c in codes if not icd10.exists(c)]
        if unknown:
            raise ValueError(f"ICD-10 codes not in the list: {unknown}")
        ids = [q.id for q in self.key_questions]
        if len(ids) != len(set(ids)):
            raise ValueError("key_questions ids must be unique")
        if set(self.accepted_codes) & set(self.related_codes):
            raise ValueError("A code cannot be both accepted and related")
        return self


# ======================= Авторизация =======================


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    university: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    university: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ======================= Кейсы и попытки =======================


class GenerateCaseRequest(BaseModel):
    disease: str = Field(min_length=3)
    specialty: str = "Internal Medicine"
    difficulty: Literal["easy", "medium", "hard"] = "easy"


class StartAttemptRequest(BaseModel):
    case_id: int
    force: bool = False  # true = «продолжить, текущий прогресс будет потерян» (US-02, сценарий 3)


def _strip_not_empty(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Type a question")
    return v


class QuestionRequest(BaseModel):
    text: str = Field(max_length=1000)

    _strip = field_validator("text")(_strip_not_empty)


class OrderTestRequest(BaseModel):
    name: str


class SubmitRequest(BaseModel):
    diagnosis_code: str = Field(min_length=3, max_length=10)


class ChatRequest(BaseModel):
    question: str = Field(max_length=1000)

    _strip = field_validator("question")(_strip_not_empty)
