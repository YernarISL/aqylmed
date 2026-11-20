import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { deleteTextbook, listTextbooks, reindexTextbook, uploadTextbook } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import type { Textbook, TextbookStatus } from "../api/types";
import { isAdmin, useAuth } from "../auth/AuthContext";
import ui from "../components/ui.module.css";
import styles from "./TextbooksPage.module.css";

const STATUS_CLASS: Record<TextbookStatus, string> = { processing: ui.warn, ready: ui.ok, failed: ui.bad };

/** US-10: approved PDFs for the RAG chatbot. Indexing runs in the background, so we poll while processing. */
export default function TextbooksPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const queryClient = useQueryClient();
  const [error, setError] = useState("");

  const books = useQuery({
    queryKey: ["textbooks"],
    queryFn: listTextbooks,
    refetchInterval: (q) => (q.state.data?.some((b) => b.status === "processing") ? 3000 : false),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["textbooks"] });

  const run = async (action: () => Promise<unknown>) => {
    setError("");
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const remove = (b: Textbook) => {
    if (window.confirm(`Delete "${b.title}" and its index?`)) run(() => deleteTextbook(b.id));
  };

  return (
    <>
      <div className={ui.pageHeader}>
        <h1>Textbooks</h1>
      </div>

      {admin && <UploadForm onUploaded={refresh} />}

      {error && <p className={ui.error}>{error}</p>}
      {books.error && <p className={ui.error}>{errorMessage(books.error)}</p>}

      <div className={ui.card}>
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Author</th>
              <th>Lang</th>
              <th>Status</th>
              <th>Pages</th>
              <th>Chunks</th>
              {admin && <th />}
            </tr>
          </thead>
          <tbody>
            {books.data?.map((b) => (
              <tr key={b.id}>
                <td>{b.title}</td>
                <td>{b.author}</td>
                <td>{b.lang}</td>
                <td>
                  <span className={`${ui.badge} ${STATUS_CLASS[b.status]}`}>{b.status}</span>
                  {b.error && <div className={`${ui.error} ${styles.bookError}`}>{b.error}</div>}
                </td>
                <td>{b.pages_count ?? "—"}</td>
                <td>{b.chunks_count ?? "—"}</td>
                {admin && (
                  <td>
                    <div className={styles.actions}>
                      <button
                        className={`${ui.ghost} ${ui.small}`}
                        disabled={b.status === "processing"}
                        onClick={() => run(() => reindexTextbook(b.id))}
                      >
                        Reindex
                      </button>
                      <button className={`${ui.danger} ${ui.small}`} onClick={() => remove(b)}>
                        Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {books.data?.length === 0 && <p className={ui.muted}>No textbooks uploaded yet.</p>}
      </div>
    </>
  );
}

function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("author", author);
    form.append("lang", lang);
    setBusy(true);
    setError("");
    try {
      await uploadTextbook(form);
      setTitle("");
      setAuthor("");
      setFile(null);
      (e.target as HTMLFormElement).reset();
      onUploaded();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className={`${ui.card} ${styles.upload}`} onSubmit={submit}>
      <h2>Upload a PDF</h2>
      <div className={styles.uploadRow}>
        <label>
          File
          <input type="file" accept="application/pdf" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label>
          Title
          <input required value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Author
          <input value={author} onChange={(e) => setAuthor(e.target.value)} />
        </label>
        <label>
          Language
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="en">English</option>
            <option value="ru">Russian</option>
            <option value="kk">Kazakh</option>
          </select>
        </label>
        <button disabled={busy}>{busy ? "Uploading…" : "Upload"}</button>
      </div>
      {error && <p className={ui.error}>{error}</p>}
    </form>
  );
}
