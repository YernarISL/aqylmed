import { api } from "./client";
import type {
  ActiveAttempt,
  AdminCase,
  AdminCaseDetail,
  AttemptDetail,
  AttemptResult,
  AttemptStart,
  CaseList,
  CaseTemplate,
  ChatAnswer,
  ChatLogs,
  Chunk,
  GenerateCaseRequest,
  HistoryItem,
  IcdItem,
  Specialty,
  TestCatalogue,
  Textbook,
} from "./types";

// ---------- catalog ----------

export const getCases = (params: { specialty?: string; difficulty?: string }) =>
  api.get<CaseList>("/cases", { params }).then((r) => r.data);

export const getSpecialties = () => api.get<Specialty[]>("/cases/specialties").then((r) => r.data);

export const getTests = () => api.get<TestCatalogue>("/tests").then((r) => r.data);

export const searchIcd = (q: string) =>
  api.get<IcdItem[]>("/icd10", { params: { q, limit: 15 } }).then((r) => r.data);

// ---------- attempts ----------

export const startAttempt = (case_id: number, force = false) =>
  api.post<AttemptStart>("/attempts", { case_id, force }).then((r) => r.data);

export const getActiveAttempt = () => api.get<ActiveAttempt | null>("/attempts/active").then((r) => r.data);

export const getAttempt = (id: number) => api.get<AttemptDetail>(`/attempts/${id}`).then((r) => r.data);

export const abandonAttempt = (id: number) => api.post(`/attempts/${id}/abandon`).then((r) => r.data);

export const askPatient = (id: number, text: string) =>
  api.post<{ answer: string }>(`/attempts/${id}/questions`, { text }).then((r) => r.data);

export const orderTest = (id: number, name: string) =>
  api.post<{ test: string; result: string }>(`/attempts/${id}/tests`, { name }).then((r) => r.data);

export const submitAttempt = (id: number, diagnosis_code: string) =>
  api.post<AttemptResult>(`/attempts/${id}/submit`, { diagnosis_code }).then((r) => r.data);

export const getHistory = () => api.get<HistoryItem[]>("/attempts").then((r) => r.data);

// ---------- chatbot & textbooks ----------

export const askChat = (question: string) =>
  api.post<ChatAnswer>("/chat/ask", { question }).then((r) => r.data);

export const getChunk = (bookId: number, chunkId: number) =>
  api.get<Chunk>(`/textbooks/${bookId}/chunks/${chunkId}`).then((r) => r.data);

export const listTextbooks = () => api.get<Textbook[]>("/textbooks").then((r) => r.data);

export const uploadTextbook = (form: FormData) => api.post<Textbook>("/textbooks", form).then((r) => r.data);

export const reindexTextbook = (id: number) =>
  api.post<Textbook>(`/textbooks/${id}/reindex`).then((r) => r.data);

export const deleteTextbook = (id: number) => api.delete(`/textbooks/${id}`);

export const getChatLogs = () => api.get<ChatLogs>("/chat/logs", { params: { limit: 100 } }).then((r) => r.data);

// ---------- staff: case templates ----------

export const adminListCases = (status?: string) =>
  api.get<AdminCase[]>("/admin/cases", { params: status ? { status } : {} }).then((r) => r.data);

export const adminGetCase = (id: number) => api.get<AdminCaseDetail>(`/admin/cases/${id}`).then((r) => r.data);

export const adminCreateCase = (data: CaseTemplate) =>
  api.post<{ id: number; status: string }>("/admin/cases", data).then((r) => r.data);

export const adminUpdateCase = (id: number, data: CaseTemplate) =>
  api.put<{ id: number; status: string }>(`/admin/cases/${id}`, data).then((r) => r.data);

export const publishCase = (id: number) => api.post(`/admin/cases/${id}/publish`).then((r) => r.data);

export const unpublishCase = (id: number) => api.post(`/admin/cases/${id}/unpublish`).then((r) => r.data);

export const generateCase = (body: GenerateCaseRequest) =>
  api.post<AdminCaseDetail>("/admin/cases/generate", body).then((r) => r.data);
