import { Link } from "react-router-dom";
import type { AttemptDetail, Citation, Verdict } from "../api/types";
import CitationView from "../components/CitationView";
import { formatDate } from "../format";
import ui from "../components/ui.module.css";
import EventLog from "./EventLog";
import styles from "./ResultView.module.css";

const VERDICT_CLASS: Record<Verdict, string> = { correct: ui.ok, related: ui.warn, incorrect: ui.bad };

function Reference({ reference }: { reference: Citation | null }) {
  return reference ? <CitationView citation={reference} /> : <p className={ui.muted}>No textbook reference found.</p>;
}

/** US-07 score + US-08 feedback for a submitted attempt. */
export default function ResultView({ attempt }: { attempt: AttemptDetail }) {
  const r = attempt.result!;
  const labels = Object.fromEntries(
    [...r.history.asked, ...r.history.missed].map((q) => [q.id, q.label]),
  );
  const parts = [
    { key: "history", name: "History taking" },
    { key: "tests", name: "Examinations" },
    { key: "diagnosis", name: "Diagnosis" },
  ] as const;

  return (
    <>
      <div className={ui.pageHeader}>
        <div>
          <h1>{attempt.case.title}</h1>
          <span className={ui.muted}>
            {attempt.patient.name}, {attempt.patient.age} · {attempt.case.specialty} · submitted{" "}
            {attempt.submitted_at && formatDate(attempt.submitted_at)}
          </span>
        </div>
        <Link to="/" className={ui.linkButton}>
          Back to cases
        </Link>
      </div>

      <div className={styles.top}>
        <section className={`${ui.card} ${styles.score}`}>
          <div className={styles.total}>
            {r.score}
            <span>/100</span>
          </div>
          <span className={`${ui.badge} ${VERDICT_CLASS[r.diagnosis.verdict]}`}>{r.label}</span>
          <div className={styles.bars}>
            {parts.map((p) => (
              <div key={p.key}>
                <div className={styles.barLabel}>
                  <span>{p.name}</span>
                  <span className="mono">
                    {r.parts[p.key]} / {r.max_parts[p.key]}
                  </span>
                </div>
                <div className={styles.bar}>
                  <div style={{ width: `${(100 * r.parts[p.key]) / r.max_parts[p.key]}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className={ui.card}>
          <h2>Diagnosis</h2>
          <dl className={styles.diag}>
            <dt>Your answer</dt>
            <dd>
              <span className="mono">{r.diagnosis.submitted.code}</span> {r.diagnosis.submitted.name}
            </dd>
            <dt>Correct</dt>
            <dd>
              <span className="mono">{r.diagnosis.correct.code}</span> {r.diagnosis.correct.name}
            </dd>
            {r.diagnosis.differential.length > 0 && (
              <>
                <dt>Differential</dt>
                <dd>{r.diagnosis.differential.join(", ")}</dd>
              </>
            )}
          </dl>
        </section>
      </div>

      <div className={styles.columns}>
        <section className={ui.card}>
          <h2>History taking</h2>
          <p className={ui.muted}>
            {r.history.asked.length} of {r.history.asked.length + r.history.missed.length} key categories covered ·{" "}
            {r.history.questions_total} questions asked
          </p>
          <div className={styles.tagList}>
            {r.history.asked.map((q) => (
              <span key={q.id} className={`${ui.badge} ${ui.ok}`}>
                {q.label}
              </span>
            ))}
          </div>
          {r.history.missed.length > 0 && <h3 className={styles.missedTitle}>Missed</h3>}
          <div className={ui.stack}>
            {r.history.missed.map((q) => (
              <div key={q.id} className={styles.missed}>
                <span className={`${ui.badge} ${ui.bad}`}>{q.label}</span>
                <Reference reference={q.reference} />
              </div>
            ))}
          </div>
        </section>

        <section className={ui.card}>
          <h2>Examinations</h2>
          <p className={ui.muted}>
            {r.tests.ordered.length} ordered · {r.tests.key_ordered.length} of{" "}
            {r.tests.key_ordered.length + r.tests.missed.length} key tests
          </p>
          <div className={styles.tagList}>
            {r.tests.ordered.map((t) => (
              <span key={t} className={`${ui.badge} ${r.tests.key_ordered.includes(t) ? ui.ok : ""}`}>
                {t}
              </span>
            ))}
          </div>
          {r.tests.missed.length > 0 && <h3 className={styles.missedTitle}>Missed key tests</h3>}
          <div className={ui.stack}>
            {r.tests.missed.map((t) => (
              <div key={t.name} className={styles.missed}>
                <span className={`${ui.badge} ${ui.bad}`}>{t.name}</span>
                <Reference reference={t.reference} />
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className={`${ui.card} ${styles.log}`}>
        <h2>Case log</h2>
        <p className={ui.muted}>Each question is tagged with the key history category it covered.</p>
        <EventLog events={attempt.events} labels={labels} />
      </section>
    </>
  );
}
