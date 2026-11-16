import { useState } from "react";
import { api } from "../api";
import type { Alert } from "../types";

export function Feedback({ path, value }: { path: string; value: "useful" | "noise" | null }) {
  const [v, setV] = useState(value);
  const send = async (next: "useful" | "noise") => {
    setV(next);
    try { await api.post(path, { value: next }); } catch { setV(value); }
  };
  return (
    <div className="fb">
      <button className={"chip-btn" + (v === "useful" ? " on" : "")} onClick={() => send("useful")} aria-pressed={v === "useful"}>Útil</button>
      <button className={"chip-btn" + (v === "noise" ? " on noise" : "")} onClick={() => send("noise")} aria-pressed={v === "noise"}>Ruído</button>
    </div>
  );
}

const fmt = (iso: string) => new Date(iso + "Z").toLocaleString("pt-PT", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export default function AlertCard({ a }: { a: Alert }) {
  const place = [a.concelho, a.distrito && a.distrito !== a.concelho ? a.distrito : null].filter(Boolean).join(", ");
  return (
    <article className="card alert">
      <div className="meta">
        {a.category && <span className="tag">{a.category}</span>}
        {place && <span>{place}</span>}
        <span>{a.source.toUpperCase()}</span>
        <span>{fmt(a.published_at)}</span>
        {a.score !== null && <span className="score" title="Relevância (0–100)">{a.score}</span>}
      </div>
      <h3>{a.title}</h3>
      {a.summary && <p>{a.summary}</p>}
      {a.why && <p className="why">{a.why}</p>}
      <div className="actions">
        <a href={a.url} target="_blank" rel="noreferrer">Fonte original ↗</a>
        <Feedback path={`/alerts/${a.id}/feedback`} value={a.feedback} />
      </div>
    </article>
  );
}
