import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { abandonAttempt, askPatient, getAttempt, getTests, orderTest, searchIcd, submitAttempt } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import type { AttemptDetail, IcdItem } from "../api/types";
import ui from "../components/ui.module.css";
import styles from "./AttemptPage.module.css";
import EventLog from "./EventLog";
import ResultView from "./ResultView";

export default function AttemptPage() {
  const id = Number(useParams().id);
  const attempt = useQuery({ queryKey: ["attempt", id], queryFn: () => getAttempt(id) });

  if (attempt.isLoading) return <p className={ui.muted}>Loading…</p>;
  if (attempt.error) return <p className={ui.error}>{errorMessage(attempt.error)}</p>;
  const a = attempt.data!;

  if (a.status === "submitted") return <ResultView attempt={a} />;
  if (a.status === "abandoned")
    return (
      <div className={ui.card}>
        <h1>{a.case.title}</h1>
        <p className={ui.muted}>This attempt was abandoned and can no longer be continued.</p>
        <Link to="/">Back to cases</Link>
      </div>
    );
  return <ActiveAttempt a={a} />;
}

// ------------------------------------------------------------------ active attempt

function ActiveAttempt({ a }: { a: AttemptDetail }) {
  const id = a.attempt_id;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const tests = useQuery({ queryKey: ["tests"], queryFn: getTests });

  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [orderingTest, setOrderingTest] = useState("");
  const [error, setError] = useState("");
  const logEnd = useRef<HTMLDivElement>(null);

  const ordered = new Set(a.events.filter((e) => e.kind === "test").map((e) => e.test_name));
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["attempt", id] });

  useEffect(() => {
    logEnd.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [a.events.length, pendingQuestion]);

  const ask = async (e: FormEvent) => {
    e.preventDefault();
    const text = question.trim();
    if (!text) return setError("Type a question");
    setError("");
    setPendingQuestion(text);
    setQuestion("");
    try {
      await askPatient(id, text);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
      setQuestion(text);
    } finally {
      setPendingQuestion("");
    }
  };

  const order = async (name: string) => {
    setOrderingTest(name);
    setError("");
    try {
      await orderTest(id, name);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setOrderingTest("");
    }
  };

  const abandon = async () => {
    if (!window.confirm("Abandon this case? Your progress will be lost.")) return;
    try {
      await abandonAttempt(id);
      queryClient.invalidateQueries({ queryKey: ["activeAttempt"] });
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const v = a.vitals;

  return (
    <>
      <div className={ui.pageHeader}>
        <div>
          <h1>{a.case.title}</h1>
          <span className={ui.muted}>
            {a.case.specialty} · {a.case.code}
          </span>
        </div>
        <button className={ui.danger} onClick={abandon}>
          Abandon case
        </button>
      </div>

      <div className={styles.layout}>
        {/* ---------- patient ---------- */}
        <aside className={`${ui.card} ${styles.patient}`}>
          <h2>{a.patient.name}</h2>
          <p className={ui.muted}>
            {a.patient.sex === "male" ? "Male" : "Female"}, {a.patient.age} y.o.
            {a.patient.occupation && ` · ${a.patient.occupation}`}
          </p>
          <h3 className={styles.sectionTitle}>Vital signs</h3>
          <dl className={styles.vitals}>
            <dt>Temperature</dt>
            <dd>{v.temperature_c} °C</dd>
            <dt>Heart rate</dt>
            <dd>{v.heart_rate_bpm} bpm</dd>
            <dt>Blood pressure</dt>
            <dd>{v.blood_pressure} mmHg</dd>
            <dt>Resp. rate</dt>
            <dd>{v.resp_rate} /min</dd>
            <dt>SpO₂</dt>
            <dd>{v.spo2_pct} %</dd>
          </dl>
        </aside>

        {/* ---------- interview ---------- */}
        <section className={`${ui.card} ${styles.chat}`}>
          <h3 className={styles.sectionTitle}>Interview</h3>
          <div className={styles.log}>
            <EventLog events={a.events} />
            {pendingQuestion && (
              <>
                <EventLog events={[{ id: -1, kind: "question", content: pendingQuestion, created_at: "" }]} />
                <p className={ui.muted}>Patient is answering…</p>
              </>
            )}
            <div ref={logEnd} />
          </div>
          {error && <p className={ui.error}>{error}</p>}
          <form className={styles.ask} onSubmit={ask}>
            <input
              placeholder="Ask the patient a question…"
              maxLength={1000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={!!pendingQuestion}
            />
            <button disabled={!!pendingQuestion}>Ask</button>
          </form>
        </section>

        {/* ---------- tests ---------- */}
        <aside className={`${ui.card} ${styles.tests}`}>
          <h3 className={styles.sectionTitle}>Examinations & tests</h3>
          {tests.data &&
            Object.entries(tests.data).map(([group, names]) => (
              <div key={group} className={styles.testGroup}>
                <div className={styles.groupName}>{group}</div>
                {names.map((name) => (
                  <button
                    key={name}
                    className={ordered.has(name) ? styles.testDone : styles.test}
                    disabled={ordered.has(name) || !!orderingTest}
                    onClick={() => order(name)}
                  >
                    {name}
                    {orderingTest === name && " …"}
                    {ordered.has(name) && <span className={styles.check}>ordered</span>}
                  </button>
                ))}
              </div>
            ))}
        </aside>
      </div>

      <DiagnosisForm attemptId={id} />
    </>
  );
}

// ------------------------------------------------------------------ diagnosis (US-04)

function DiagnosisForm({ attemptId }: { attemptId: number }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [debounced, setDebounced] = useState("");
  const [selected, setSelected] = useState<IcdItem | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);

  const results = useQuery({
    queryKey: ["icd", debounced],
    queryFn: () => searchIcd(debounced),
    enabled: debounced.length > 0 && !selected,
  });

  const submit = async () => {
    if (!selected) return;
    if (!window.confirm(`Submit final diagnosis ${selected.code} — ${selected.name}? The case becomes read-only.`))
      return;
    setBusy(true);
    setError("");
    try {
      await submitAttempt(attemptId, selected.code);
      queryClient.invalidateQueries({ queryKey: ["attempt", attemptId] });
      queryClient.invalidateQueries({ queryKey: ["history"] });
      queryClient.invalidateQueries({ queryKey: ["activeAttempt"] });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <section className={`${ui.card} ${styles.diagnosis}`}>
      <h3 className={styles.sectionTitle}>Final diagnosis (ICD-10)</h3>
      <div className={styles.diagRow}>
        <div className={styles.picker}>
          {selected ? (
            <div className={styles.selected}>
              <span className="mono">{selected.code}</span> {selected.name}
              <button className={`${ui.ghost} ${ui.small}`} onClick={() => setSelected(null)}>
                Change
              </button>
            </div>
          ) : (
            <input
              placeholder="Search by code or name, e.g. I21 or infarction"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}
          {!selected && results.data && results.data.length > 0 && (
            <ul className={styles.icdList}>
              {results.data.map((i) => (
                <li key={i.code}>
                  <button onClick={() => setSelected(i)}>
                    <span className="mono">{i.code}</span> {i.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!selected && results.data?.length === 0 && <p className={ui.muted}>No matching codes.</p>}
        </div>
        <button onClick={submit} disabled={!selected || busy}>
          {busy ? "Submitting…" : "Submit diagnosis"}
        </button>
      </div>
      {error && <p className={ui.error}>{error}</p>}
    </section>
  );
}
