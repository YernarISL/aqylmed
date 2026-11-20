import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getChunk } from "../api/endpoints";
import { errorMessage } from "../api/errors";
import type { Citation } from "../api/types";
import styles from "./CitationView.module.css";
import ui from "./ui.module.css";

/** Book · chapter · page + quote; "Open fragment" loads the full indexed text (US-06). */
export default function CitationView({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  const chunk = useQuery({
    queryKey: ["chunk", citation.textbook_id, citation.chunk_id],
    queryFn: () => getChunk(citation.textbook_id, citation.chunk_id),
    enabled: open,
  });

  return (
    <div className={styles.citation}>
      <div className={styles.source}>
        {citation.ref !== undefined && <span className={styles.ref}>[{citation.ref}]</span>}
        <strong>{citation.book_title}</strong>
        {citation.chapter && <span> · {citation.chapter}</span>}
        <span> · p. {citation.page}</span>
        <button className={`${ui.ghost} ${ui.small} ${styles.toggle}`} onClick={() => setOpen(!open)}>
          {open ? "Hide fragment" : "Open fragment"}
        </button>
      </div>
      {!open && <p className={styles.quote}>{citation.quote}</p>}
      {open && chunk.isLoading && <p className={ui.muted}>Loading…</p>}
      {open && chunk.error && <p className={ui.error}>{errorMessage(chunk.error)}</p>}
      {open && chunk.data && (
        <blockquote className={styles.full}>
          {chunk.data.author && <div className={ui.muted}>{chunk.data.author}</div>}
          {chunk.data.text}
        </blockquote>
      )}
    </div>
  );
}
