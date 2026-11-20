import { useState, type FormEvent } from "react";
import { askChat } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import type { ChatAnswer } from "../api/types";
import CitationView from "../components/CitationView";
import ui from "../components/ui.module.css";
import styles from "./ChatPage.module.css";

interface Turn {
  question: string;
  answer?: ChatAnswer;
  error?: string;
}

/** Highlights [n] citation markers inside the answer text. */
function AnswerText({ text }: { text: string }) {
  return (
    <p className={styles.answerText}>
      {text.split(/(\[\d+\])/).map((part, i) =>
        /^\[\d+\]$/.test(part) ? (
          <span key={i} className={styles.marker}>
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </p>
  );
}

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [{ question: q }, ...t]);
    let done: Turn;
    try {
      done = { question: q, answer: await askChat(q) };
    } catch (err) {
      done = { question: q, error: errorMessage(err) };
    }
    setTurns((t) => [done, ...t.slice(1)]);
    setBusy(false);
  };

  return (
    <div className={styles.page}>
      <div className={ui.pageHeader}>
        <div>
          <h1>Textbook assistant</h1>
          <p className={ui.muted}>Answers come only from the indexed course textbooks, with page citations.</p>
        </div>
      </div>

      <form className={`${ui.card} ${styles.form}`} onSubmit={ask}>
        <textarea
          rows={2}
          maxLength={1000}
          placeholder="e.g. What are the ECG signs of an anterior STEMI?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <button disabled={busy || !question.trim()}>{busy ? "Searching…" : "Ask"}</button>
      </form>

      <div className={ui.stack}>
        {turns.map((t, i) => (
          <article key={turns.length - i} className={ui.card}>
            <div className={styles.question}>{t.question}</div>
            {!t.answer && !t.error && <p className={ui.muted}>Searching the textbooks…</p>}
            {t.error && <p className={ui.error}>{t.error}</p>}
            {t.answer && (
              <>
                <div className={t.answer.fallback ? styles.fallback : undefined}>
                  <AnswerText text={t.answer.answer} />
                </div>
                {t.answer.citations.length > 0 && (
                  <div className={`${ui.stack} ${styles.citations}`}>
                    {t.answer.citations.map((c) => (
                      <CitationView key={c.chunk_id} citation={c} />
                    ))}
                  </div>
                )}
                <div className={ui.muted}>{(t.answer.latency_ms / 1000).toFixed(2)} s</div>
              </>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
