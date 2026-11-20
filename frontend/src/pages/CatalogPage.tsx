import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getActiveAttempt, getCases, getSpecialties, startAttempt } from "../api/endpoints";
import { errorMessage, errorStatus } from "../api/errors";
import type { CaseCard, Difficulty } from "../api/types";
import ui from "../components/ui.module.css";
import styles from "./CatalogPage.module.css";

const DIFFICULTY_CLASS: Record<Difficulty, string> = { easy: ui.ok, medium: ui.warn, hard: ui.bad };

export default function CatalogPage() {
  const navigate = useNavigate();
  const [specialty, setSpecialty] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [startingId, setStartingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const specialties = useQuery({ queryKey: ["specialties"], queryFn: getSpecialties });
  const cases = useQuery({
    queryKey: ["cases", specialty, difficulty],
    queryFn: () => getCases({ specialty: specialty || undefined, difficulty: difficulty || undefined }),
  });
  const active = useQuery({ queryKey: ["activeAttempt"], queryFn: getActiveAttempt });

  const start = async (c: CaseCard) => {
    setStartingId(c.id);
    setError("");
    try {
      let attempt;
      try {
        attempt = await startAttempt(c.id);
      } catch (err) {
        // US-02: one active attempt at a time — ask before discarding it
        if (errorStatus(err) !== 409) throw err;
        if (!window.confirm(`${errorMessage(err)}\n\nStart "${c.title}" anyway?`)) return;
        attempt = await startAttempt(c.id, true);
      }
      navigate(`/attempt/${attempt.attempt_id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setStartingId(null);
    }
  };

  const total = specialties.data?.reduce((n, s) => n + s.count, 0) ?? 0;

  return (
    <>
      <div className={ui.pageHeader}>
        <h1>Clinical cases</h1>
        <label className={styles.select}>
          Difficulty
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            <option value="">Any</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
      </div>

      {active.data && (
        <div className={`${ui.card} ${styles.resume}`}>
          <div>
            <strong>Case in progress:</strong> {active.data.case.title}
            <div className={ui.muted}>
              {active.data.patient.name}, {active.data.patient.age} · {active.data.case.specialty}
            </div>
          </div>
          <Link to={`/attempt/${active.data.attempt_id}`} className={ui.linkButton}>
            Resume
          </Link>
        </div>
      )}

      <div className={styles.chips}>
        <button className={specialty === "" ? styles.chipOn : styles.chip} onClick={() => setSpecialty("")}>
          All <span>{total}</span>
        </button>
        {specialties.data?.map((s) => (
          <button
            key={s.specialty}
            className={specialty === s.specialty ? styles.chipOn : styles.chip}
            onClick={() => setSpecialty(s.specialty)}
          >
            {s.specialty} <span>{s.count}</span>
          </button>
        ))}
      </div>

      {error && <p className={ui.error}>{error}</p>}
      {cases.error && <p className={ui.error}>{errorMessage(cases.error)}</p>}
      {cases.data && (
        <p className={ui.muted}>
          {cases.data.count} {cases.data.count === 1 ? "case" : "cases"}
        </p>
      )}

      <div className={styles.grid}>
        {cases.data?.items.map((c) => (
          <article key={c.id} className={`${ui.card} ${styles.case}`}>
            <div className={ui.row}>
              <span className={ui.badge}>{c.specialty}</span>
              <span className={`${ui.badge} ${DIFFICULTY_CLASS[c.difficulty]}`}>{c.difficulty}</span>
              <span className={`${ui.muted} mono ${styles.code}`}>{c.code}</span>
            </div>
            <h2>{c.title}</h2>
            <p className={styles.complaint}>“{c.chief_complaint}”</p>
            <p className={ui.muted}>
              {c.patient.sex === "male" ? "Male" : "Female"}, {c.patient.age_range[0]}–{c.patient.age_range[1]} y.o.
            </p>
            <button onClick={() => start(c)} disabled={startingId !== null}>
              {startingId === c.id ? "Starting…" : "Start case"}
            </button>
          </article>
        ))}
      </div>
      {cases.data?.count === 0 && <p className={ui.muted}>No cases match the filter.</p>}
    </>
  );
}
