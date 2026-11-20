// ======================= Shared literals =======================

export type Sex = "male" | "female";
export type Difficulty = "easy" | "medium" | "hard";
export type CaseStatus = "draft" | "published";

// ======================= Clinical case template =======================

export interface Range {
  min: number;
  max: number;
}

export interface VitalRanges {
  temperature_c: Range;
  heart_rate_bpm: Range;
  systolic_bp: Range;
  diastolic_bp: Range;
  resp_rate: Range;
  spo2_pct: Range;
}

export interface PatientTemplate {
  name: string;
  sex: Sex;
  age: Range;
  occupation: string;
}

export interface Symptom {
  name: string;
  details: string;
}

export interface KeyQuestion {
  /** Pattern: ^[a-z0-9_]+$ */
  id: string;
  label: string;
  keywords: string[];
  reference_query: string;
}

export interface DiagnosisRef {
  code: string;
  name: string;
}

/** Fields with backend defaults are always present in API responses. */
export interface CaseTemplate {
  /** Pattern: ^CASE-[A-Z]+-\d{2,}$ (e.g. CASE-IM-01) */
  code: string;
  title: string;
  specialty: string;
  difficulty: Difficulty;
  status: CaseStatus;

  // --- known to the "patient" (LLM) ---
  patient: PatientTemplate;
  personality: string;
  chief_complaint: string;
  history_present_illness: string;
  symptoms: Symptom[];
  negative_symptoms: string[];
  past_medical_history: string;
  medications: string;
  allergies: string;
  family_history: string;
  social_history: string;

  // --- reference data for grading (unknown to the patient) ---
  vitals: VitalRanges;
  /** Key — test name from the catalogue, value — exact result. */
  test_results: Record<string, string>;
  default_result: string;
  key_tests: string[];
  test_reference_queries: Record<string, string>;
  diagnosis: DiagnosisRef;
  accepted_codes: string[];
  related_codes: string[];
  differential: string[];
  /** At least one item; ids must be unique. */
  key_questions: KeyQuestion[];
}

// ======================= Auth =======================

export interface RegisterRequest {
  email: string;
  /** 8–128 chars */
  password: string;
  /** 1–100 chars */
  first_name: string;
  /** max 100 chars, default "" */
  last_name?: string;
  /** max 255 chars, default "" */
  university?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserOut {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  university: string;
  role: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  user: UserOut;
}

// ======================= Cases & attempts =======================

export interface GenerateCaseRequest {
  /** min 3 chars */
  disease: string;
  /** default "Internal Medicine" */
  specialty?: string;
  /** default "easy" */
  difficulty?: Difficulty;
}

export interface StartAttemptRequest {
  case_id: number;
  /** true = continue, current progress will be lost */
  force?: boolean;
}

export interface QuestionRequest {
  /** Non-empty after trim, max 1000 chars */
  text: string;
}

export interface OrderTestRequest {
  name: string;
}

export interface SubmitRequest {
  /** 3–10 chars */
  diagnosis_code: string;
}

export interface ChatRequest {
  /** Non-empty after trim, max 1000 chars */
  question: string;
}

// ======================= API responses =======================

export interface CaseCard {
  id: number;
  code: string;
  title: string;
  specialty: string;
  difficulty: Difficulty;
  chief_complaint: string;
  patient: { sex: Sex; age_range: [number, number] };
}

export interface CaseList {
  count: number;
  items: CaseCard[];
}

export interface Specialty {
  specialty: string;
  count: number;
}

/** Group name → list of test names. */
export type TestCatalogue = Record<string, string[]>;

export interface IcdItem {
  code: string;
  name: string;
}

export interface Vitals {
  temperature_c: number;
  heart_rate_bpm: number;
  blood_pressure: string;
  systolic_bp: number;
  diastolic_bp: number;
  resp_rate: number;
  spo2_pct: number;
}

export interface AttemptStart {
  attempt_id: number;
  case: CaseCard;
  patient: { name: string; age: number; sex: Sex; occupation: string };
  vitals: Vitals;
  chief_complaint: string;
  started_at: string;
}

export interface AttemptEvent {
  id: number;
  kind: "question" | "answer" | "test";
  content: string;
  created_at: string;
  test_name?: string;
  /** Only present after submission. */
  key_question_ids?: string[];
}

export interface Citation {
  chunk_id: number;
  textbook_id: number;
  book_title: string;
  chapter: string;
  page: number;
  quote: string;
  similarity: number;
  link: string;
  /** [n] marker in a chatbot answer */
  ref?: number;
}

export type Verdict = "correct" | "related" | "incorrect";

export interface ScoreParts {
  history: number;
  tests: number;
  diagnosis: number;
}

export interface AttemptResult {
  score: number;
  parts: ScoreParts;
  max_parts: ScoreParts;
  label: string;
  diagnosis: {
    verdict: Verdict;
    submitted: { code: string; name: string | null };
    correct: DiagnosisRef;
    differential: string[];
  };
  history: {
    asked: { id: string; label: string }[];
    missed: { id: string; label: string; reference: Citation | null }[];
    questions_total: number;
  };
  tests: {
    ordered: string[];
    key_ordered: string[];
    missed: { name: string; reference: Citation | null }[];
  };
}

export type AttemptStatus = "active" | "submitted" | "abandoned";

export interface AttemptDetail extends AttemptStart {
  status: AttemptStatus;
  submitted_at: string | null;
  result: AttemptResult | null;
  events: AttemptEvent[];
}

export interface ActiveAttempt extends AttemptStart {
  events: AttemptEvent[];
}

export interface HistoryItem {
  attempt_id: number;
  date: string;
  case: { id: number; title: string; specialty: string };
  score: number;
  label: string | null;
}

export interface ChatAnswer {
  answer: string;
  fallback: boolean;
  citations: Citation[];
  latency_ms: number;
}

export interface Chunk {
  chunk_id: number;
  textbook_id: number;
  book_title: string;
  author: string;
  chapter: string;
  page: number;
  text: string;
}

export type TextbookStatus = "processing" | "ready" | "failed";

export interface Textbook {
  id: number;
  title: string;
  author: string;
  lang: string;
  status: TextbookStatus;
  error: string | null;
  pages_count: number | null;
  chunks_count: number | null;
  created_at: string;
}

export interface ChatLogs {
  stats: {
    count: number;
    fallback_share: number | null;
    latency_ms_median: number | null;
    latency_ms_max: number | null;
    total_questions: number;
  };
  items: {
    id: number;
    question: string;
    fallback: boolean;
    best_similarity: number | null;
    latency_ms: number;
    citations: number;
    created_at: string;
  }[];
}

export interface AdminCase extends CaseCard {
  status: CaseStatus;
  diagnosis: DiagnosisRef;
}

export interface AdminCaseDetail {
  id: number;
  status: CaseStatus;
  data: CaseTemplate;
}
