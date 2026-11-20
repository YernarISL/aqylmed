import { isAxiosError } from "axios";

interface ValidationItem {
  loc?: (string | number)[];
  msg: string;
}

/** Turns a FastAPI error (detail as a string, an object with message, or a 422 list) into readable text. */
export const errorMessage = (err: unknown): string => {
  if (!isAxiosError(err)) return err instanceof Error ? err.message : "Something went wrong";
  const detail = err.response?.data?.detail;
  if (!detail) return err.response ? `Request failed (${err.response.status})` : "Server is unreachable";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((d) => {
        const where = (d.loc ?? []).filter((p) => p !== "body").join(".");
        return where ? `${where}: ${d.msg}` : d.msg;
      })
      .join("\n");
  }
  if (typeof detail === "object" && "message" in detail) return String(detail.message);
  return JSON.stringify(detail);
};

export const errorStatus = (err: unknown): number | undefined =>
  isAxiosError(err) ? err.response?.status : undefined;
