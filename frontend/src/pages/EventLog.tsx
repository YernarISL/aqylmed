import type { AttemptEvent } from "../api/types";
import ui from "../components/ui.module.css";
import styles from "./EventLog.module.css";

/** Interview + test log. `labels` (key-question id → label) is passed only after submission. */
export default function EventLog({ events, labels }: { events: AttemptEvent[]; labels?: Record<string, string> }) {
  return (
    <>
      {events.map((e) => {
        if (e.kind === "test")
          return (
            <div key={e.id} className={styles.test}>
              <div className={styles.testName}>{e.test_name}</div>
              <div>{e.content}</div>
            </div>
          );
        const isQuestion = e.kind === "question";
        return (
          <div key={e.id} className={isQuestion ? styles.question : styles.answer}>
            <div className={styles.who}>{isQuestion ? "You" : "Patient"}</div>
            <div>{e.content}</div>
            {labels && isQuestion && (
              <div className={styles.tags}>
                {(e.key_question_ids ?? []).length === 0 ? (
                  <span className={ui.badge}>no key category</span>
                ) : (
                  e.key_question_ids!.map((id) => (
                    <span key={id} className={`${ui.badge} ${ui.accent}`}>
                      {labels[id] ?? id}
                    </span>
                  ))
                )}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
