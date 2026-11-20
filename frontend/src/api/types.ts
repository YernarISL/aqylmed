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
