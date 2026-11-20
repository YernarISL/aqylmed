import { api } from "./client";
import type {
  ChatAnswer,
  ChatLogs,
  ChatRequest,
  Citation,
  Textbook,
  TextChunk,
  UploadTextbookRequest,
} from "./types";

// ======================= Chatbot (US-05, US-06) =======================

/** Ask the textbook chatbot. Check `fallback` before rendering citations. */
export const askChat = async (question: string): Promise<ChatAnswer> => {
  const body: ChatRequest = { question };
  const response = await api.post<ChatAnswer>("/chat/ask", body);
  return response.data;
};

/** Staff only (teacher/admin): recent questions, fallback share and latency (NFR-02). */
export const getChatLogs = async (limit = 50): Promise<ChatLogs> => {
  const response = await api.get<ChatLogs>("/chat/logs", { params: { limit } });
  return response.data;
};

/**
 * Splits an answer into text and citation markers so the UI can render "[1]" as a clickable ref.
 * Markers without a matching citation stay plain text.
 */
export type AnswerPart = { type: "text"; text: string } | { type: "citation"; citation: Citation };

export const splitAnswer = (answer: ChatAnswer): AnswerPart[] => {
  const byRef = new Map(answer.citations.map((c) => [c.ref, c]));
  const parts: AnswerPart[] = [];
  let last = 0;
  for (const match of answer.answer.matchAll(/\[(\d+)\]/g)) {
    const citation = byRef.get(Number(match[1]));
    if (!citation) continue;
    if (match.index > last) parts.push({ type: "text", text: answer.answer.slice(last, match.index) });
    parts.push({ type: "citation", citation });
    last = match.index + match[0].length;
  }
  if (last < answer.answer.length) parts.push({ type: "text", text: answer.answer.slice(last) });
  return parts;
};

// ======================= Textbooks (US-10) & fragments (US-06) =======================

export const listTextbooks = async (): Promise<Textbook[]> => {
  const response = await api.get<Textbook[]>("/textbooks");
  return response.data;
};

export const getTextbook = async (id: number): Promise<Textbook> => {
  const response = await api.get<Textbook>(`/textbooks/${id}`);
  return response.data;
};

/** Admin only. Returns immediately with status "processing"; poll getTextbook until "ready"/"failed". */
export const uploadTextbook = async ({ file, title, author = "", lang = "en" }: UploadTextbookRequest): Promise<Textbook> => {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title);
  form.append("author", author);
  form.append("lang", lang);
  const response = await api.post<Textbook>("/textbooks", form);
  return response.data;
};

/** Admin only. */
export const reindexTextbook = async (id: number): Promise<Textbook> => {
  const response = await api.post<Textbook>(`/textbooks/${id}/reindex`);
  return response.data;
};

/** Admin only. */
export const deleteTextbook = async (id: number): Promise<void> => {
  await api.delete(`/textbooks/${id}`);
};

/** Full fragment behind a citation (also used for feedback references, US-08). */
export const getChunk = async (textbookId: number, chunkId: number): Promise<TextChunk> => {
  const response = await api.get<TextChunk>(`/textbooks/${textbookId}/chunks/${chunkId}`);
  return response.data;
};

/** Same as getChunk, but takes a citation's `link` (absolute API path). */
export const getChunkByLink = async (link: string): Promise<TextChunk> => {
  const response = await api.get<TextChunk>(link.replace(/^\/api\/v1/, ""));
  return response.data;
};
