import { useEffect, useState } from "react";
import { api, qs } from "../api";
import AlertCard from "../components/AlertCard";
import Filters, { FilterState } from "../components/Filters";
import type { Alert, Meta } from "../types";

export default function TodayPage({ meta }: { meta: Meta }) {
  const [f, setF] = useState<FilterState>({ category: "", source: "", date: "", days: 1 });
  const [items, setItems] = useState<Alert[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setItems(null);
    api.get<Alert[]>("/alerts" + qs({ category: f.category, source: f.source, date: f.date, days: 1 }))
      .then(setItems).catch((e) => setErr(e.message));
  }, [f]);
  return (
    <>
      <div className="page-head"><h2>Hoje</h2><span className="muted">{items ? `${items.length} alertas` : ""}</span></div>
      <Filters meta={meta} f={f} set={setF} mode="date" />
      {err && <p className="error">{err}</p>}
      {items === null && !err && <p className="muted">A carregar…</p>}
      {items?.length === 0 && <p className="empty">Sem alertas para estes filtros. Se a base estiver vazia, corre <code>python -m app.seed</code> para ver dados de demonstração.</p>}
      <div className="stack">{items?.map((a) => <AlertCard key={a.id} a={a} />)}</div>
    </>
  );
}
