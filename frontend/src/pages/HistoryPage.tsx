import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getHistory } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import { formatDate } from "../format";
import ui from "../components/ui.module.css";

const scoreClass = (score: number) => (score >= 70 ? ui.ok : score >= 40 ? ui.warn : ui.bad);

export default function HistoryPage() {
  const history = useQuery({ queryKey: ["history"], queryFn: getHistory });

  return (
    <>
      <div className={ui.pageHeader}>
        <h1>My attempts</h1>
      </div>
      {history.error && <p className={ui.error}>{errorMessage(history.error)}</p>}
      {history.data?.length === 0 && (
        <p className={ui.muted}>
          No completed cases yet. <Link to="/">Pick a case</Link> to get started.
        </p>
      )}
      {!!history.data?.length && (
        <div className={ui.card}>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Case</th>
                <th>Specialty</th>
                <th>Score</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map((h) => (
                <tr key={h.attempt_id}>
                  <td className={ui.muted}>{formatDate(h.date)}</td>
                  <td>
                    <Link to={`/attempt/${h.attempt_id}`}>{h.case.title}</Link>
                  </td>
                  <td>{h.case.specialty}</td>
                  <td>
                    <span className={`${ui.badge} ${scoreClass(h.score)}`}>{h.score} / 100</span>
                  </td>
                  <td>{h.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
