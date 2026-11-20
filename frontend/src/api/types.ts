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

// ======================= RAG chatbot & textbooks =======================
// Mirrors backend/app/schemas.py (ChatAnswer, Citation, TextbookOut, ChunkOut, ChatLogsOut).

export type TextbookStatus = "uploaded" | "processing" | "ready" | "failed";

export interface Citation {
  chunk_id: number;
  textbook_id: number;
  book_title: string;
  chapter: string;
  page: number;
  /** Verbatim indexed fragment */
  quote: string;
  similarity: number;
  /** API path to the full fragment, e.g. /api/v1/textbooks/1/chunks/42 */
  link: string;
  /** Number of the [n] marker in the answer text (only in /chat/ask) */
  ref?: number | null;
}

export interface ChatAnswer {
  /** ≤ 150 words, contains [n] markers that map to citations[].ref */
  answer: string;
  /** true — nothing relevant in the textbooks; citations is empty */
  fallback: boolean;
  citations: Citation[];
  latency_ms: number;
}

export interface Textbook {
  id: number;
  title: string;
  author: string;
  lang: string;
  status: TextbookStatus;
  /** Reason when status = "failed" */
  error: string | null;
  pages_count: number;
  chunks_count: number;
  /** ISO datetime */
  created_at: string;
}

export interface UploadTextbookRequest {
  /** PDF only, ≤ 100 MB */
  file: File;
  title: string;
  author?: string;
  /** default "en" */
  lang?: string;
}

export interface TextChunk {
  chunk_id: number;
  textbook_id: number;
  book_title: string;
  author: string;
  chapter: string;
  page: number;
  text: string;
}

export interface ChatLogStats {
  count: number;
  fallback_share: number | null;
  latency_ms_median: number | null;
  latency_ms_max: number | null;
  total_questions: number;
}

export interface ChatLogItem {
  id: number;
  question: string;
  fallback: boolean;
  best_similarity: number | null;
  latency_ms: number;
  /** Number of citations in the answer */
  citations: number;
  created_at: string;
}

export interface ChatLogs {
  stats: ChatLogStats;
  items: ChatLogItem[];
}
