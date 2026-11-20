import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { adminListCases, generateCase, publishCase, unpublishCase } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import type { AdminCase, Difficulty, GenerateCaseRequest } from "../api/types";
import ui from "../components/ui.module.css";
import styles from "./AdminCasesPage.module.css";

export default function AdminCasesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const cases = useQuery({ queryKey: ["adminCases", status], queryFn: () => adminListCases(status || undefined) });

  const toggle = async (c: AdminCase) => {
    setBusyId(c.id);
    setError("");
    try {
      await (c.status === "published" ? unpublishCase(c.id) : publishCase(c.id));
      queryClient.invalidateQueries({ queryKey: ["adminCases"] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.invalidateQueries({ queryKey: ["specialties"] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <div className={ui.pageHeader}>
        <h1>Case templates</h1>
        <div className={ui.row}>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className={styles.filter}>
            <option value="">All statuses</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
          </select>
          <Link to="/admin/cases/new" className={ui.linkButton}>
            New case
          </Link>
        </div>
      </div>

      <GenerateForm onCreated={(id) => navigate(`/admin/cases/${id}`)} />

      {error && <p className={ui.error}>{error}</p>}
      {cases.error && <p className={ui.error}>{errorMessage(cases.error)}</p>}

      <div className={ui.card}>
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Title</th>
              <th>Specialty</th>
              <th>Difficulty</th>
              <th>Diagnosis</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {cases.data?.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.code}</td>
                <td>{c.title}</td>
                <td>{c.specialty}</td>
                <td>{c.difficulty}</td>
                <td>
                  <span className="mono">{c.diagnosis.code}</span> {c.diagnosis.name}
                </td>
                <td>
                  <span className={`${ui.badge} ${c.status === "published" ? ui.ok : ""}`}>{c.status}</span>
                </td>
                <td>
                  <div className={styles.actions}>
                    <Link to={`/admin/cases/${c.id}`}>Edit</Link>
                    <button className={`${ui.ghost} ${ui.small}`} disabled={busyId === c.id} onClick={() => toggle(c)}>
                      {c.status === "published" ? "Unpublish" : "Publish"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {cases.data?.length === 0 && <p className={ui.muted}>No cases.</p>}
      </div>
    </>
  );
}

function GenerateForm({ onCreated }: { onCreated: (id: number) => void }) {
  const [form, setForm] = useState<Required<GenerateCaseRequest>>({
    disease: "",
    specialty: "Internal Medicine",
    difficulty: "easy",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await generateCase(form);
      onCreated(created.id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <form className={`${ui.card} ${styles.generate}`} onSubmit={submit}>
      <h2>Generate a draft with AI</h2>
      <p className={ui.muted}>The model writes a draft only. Review it before publishing to students.</p>
      <div className={styles.genRow}>
        <label>
          Disease
          <input
            required
            minLength={3}
            placeholder="e.g. Community-acquired pneumonia"
            value={form.disease}
            onChange={(e) => setForm({ ...form, disease: e.target.value })}
          />
        </label>
        <label>
          Specialty
          <input value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} />
        </label>
        <label>
          Difficulty
          <select
            value={form.difficulty}
            onChange={(e) => setForm({ ...form, difficulty: e.target.value as Difficulty })}
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
        <button disabled={busy}>{busy ? "Generating…" : "Generate"}</button>
      </div>
      {error && <p className={ui.error}>{error}</p>}
    </form>
  );
}
