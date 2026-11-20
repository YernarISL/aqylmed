import { useQuery } from "@tanstack/react-query";
import { getChatLogs } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import { formatDate } from "../format";
import ui from "../components/ui.module.css";
import styles from "./ChatLogsPage.module.css";

const ms = (v: number | null) => (v === null ? "—" : `${(v / 1000).toFixed(2)} s`);

/** NFR-02 QA view: latency (max ≤ 5 s, median ≤ 3 s) and fallback share. */
export default function ChatLogsPage() {
  const logs = useQuery({ queryKey: ["chatLogs"], queryFn: getChatLogs });
  const s = logs.data?.stats;

  return (
    <>
      <div className={ui.pageHeader}>
        <h1>Chatbot logs</h1>
        <button className={ui.ghost} onClick={() => logs.refetch()} disabled={logs.isFetching}>
          Refresh
        </button>
      </div>
      {logs.error && <p className={ui.error}>{errorMessage(logs.error)}</p>}

      {s && (
        <div className={styles.stats}>
          <Stat label="Questions (all time)" value={String(s.total_questions)} />
          <Stat label={`Fallback share (last ${s.count})`} value={s.fallback_share === null ? "—" : `${Math.round(s.fallback_share * 100)} %`} />
          <Stat label="Median latency" value={ms(s.latency_ms_median)} warn={(s.latency_ms_median ?? 0) > 3000} />
          <Stat label="Max latency" value={ms(s.latency_ms_max)} warn={(s.latency_ms_max ?? 0) > 5000} />
        </div>
      )}

      {logs.data && (
        <div className={ui.card}>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Question</th>
                <th>Answer</th>
                <th>Best similarity</th>
                <th>Citations</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {logs.data.items.map((r) => (
                <tr key={r.id}>
                  <td className={ui.muted}>{formatDate(r.created_at)}</td>
                  <td>{r.question}</td>
                  <td>
                    <span className={`${ui.badge} ${r.fallback ? ui.warn : ui.ok}`}>{r.fallback ? "fallback" : "answered"}</span>
                  </td>
                  <td className="mono">{r.best_similarity?.toFixed(3) ?? "—"}</td>
                  <td>{r.citations}</td>
                  <td className="mono">{ms(r.latency_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.data.items.length === 0 && <p className={ui.muted}>No questions yet.</p>}
        </div>
      )}
    </>
  );
}

function Stat({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className={ui.card}>
      <div className={ui.muted}>{label}</div>
      <div className={warn ? `${styles.value} ${styles.warn}` : styles.value}>{value}</div>
    </div>
  );
}
