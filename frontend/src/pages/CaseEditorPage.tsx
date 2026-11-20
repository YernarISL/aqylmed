import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { adminCreateCase, adminGetCase, adminUpdateCase } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import type { CaseTemplate } from "../api/types";
import ui from "../components/ui.module.css";
import styles from "./CaseEditorPage.module.css";

/** Starting point for a new case: the smallest template the backend accepts. */
const SKELETON: CaseTemplate = {
  code: "CASE-IM-99",
  title: "New case title (without the diagnosis)",
  specialty: "Internal Medicine",
  difficulty: "easy",
  status: "draft",
  patient: { name: "Patient", sex: "female", age: { min: 30, max: 40 }, occupation: "" },
  personality: "Calm, answers briefly",
  chief_complaint: "Doctor, I feel tired all the time.",
  history_present_illness: "",
  symptoms: [{ name: "fatigue", details: "for about a month" }],
  negative_symptoms: ["fever"],
  past_medical_history: "No serious illnesses",
  medications: "Takes no medications",
  allergies: "None",
  family_history: "Does not know",
  social_history: "",
  vitals: {
    temperature_c: { min: 36.4, max: 36.8 },
    heart_rate_bpm: { min: 70, max: 85 },
    systolic_bp: { min: 110, max: 125 },
    diastolic_bp: { min: 70, max: 80 },
    resp_rate: { min: 14, max: 18 },
    spo2_pct: { min: 97, max: 99 },
  },
  test_results: { "Complete blood count": "Hb 90 g/L, MCV 70 fL" },
  default_result: "No abnormalities detected",
  key_tests: ["Complete blood count"],
  test_reference_queries: {},
  diagnosis: { code: "D50.9", name: "Iron deficiency anaemia, unspecified" },
  accepted_codes: [],
  related_codes: [],
  differential: [],
  key_questions: [{ id: "onset", label: "Onset of symptoms", keywords: ["when", "how long"], reference_query: "" }],
};

export default function CaseEditorPage() {
  const param = useParams().id!;
  const isNew = param === "new";
  const id = Number(param);
  const existing = useQuery({ queryKey: ["adminCase", id], queryFn: () => adminGetCase(id), enabled: !isNew });

  if (isNew) return <Editor caseId={null} initial={SKELETON} />;
  if (existing.isLoading) return <p className={ui.muted}>Loading…</p>;
  if (existing.error) return <p className={ui.error}>{errorMessage(existing.error)}</p>;
  return <Editor caseId={id} initial={existing.data!.data} />;
}

function Editor({ caseId, initial }: { caseId: number | null; initial: CaseTemplate }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [text, setText] = useState(() => JSON.stringify(initial, null, 2));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setError("");
    setSaved(false);
    let data: CaseTemplate;
    try {
      data = JSON.parse(text);
    } catch (err) {
      return setError(`Invalid JSON: ${(err as Error).message}`);
    }
    setBusy(true);
    try {
      const res = caseId === null ? await adminCreateCase(data) : await adminUpdateCase(caseId, data);
      queryClient.invalidateQueries({ queryKey: ["adminCases"] });
      queryClient.invalidateQueries({ queryKey: ["adminCase", res.id] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.invalidateQueries({ queryKey: ["specialties"] });
      if (caseId === null) navigate(`/admin/cases/${res.id}`, { replace: true });
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className={ui.pageHeader}>
        <div>
          <h1>{caseId === null ? "New case template" : `Edit case #${caseId}`}</h1>
          <span className={ui.muted}>
            Edit the template as JSON. Set <code>"status"</code> to <code>"published"</code> to show it to students.
          </span>
        </div>
        <div className={ui.row}>
          <Link to="/admin/cases">Back to list</Link>
          <button onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
      {error && <pre className={`${ui.error} ${styles.errors}`}>{error}</pre>}
      {saved && <p className={`${ui.badge} ${ui.ok}`}>Saved</p>}
      <textarea
        className={styles.editor}
        spellCheck={false}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setSaved(false);
        }}
      />
    </>
  );
}
