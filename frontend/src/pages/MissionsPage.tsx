import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Feedback } from "../components/AlertCard";
import type { Meta, Mission, MissionAlert, SearchResult } from "../types";

const empty = { name: "", instruction: "", sources: [] as string[], frequency: "daily" as "daily" | "weekly", active: true, use_web: false };

function FreeSearch() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async (e: React.FormEvent) => {
    e.preventDefault(); if (q.trim().length < 3) return;
    setBusy(true); setErr("");
    try { setRes(await api.post<SearchResult>("/search", { question: q })); } catch (x) { setErr((x as Error).message); }
    setBusy(false);
  };
  return (
    <section className="card">
      <form onSubmit={go} className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Pergunta livre — ex.: o que saiu sobre alojamento local em Lisboa?" />
        <button className="primary" disabled={busy}>{busy ? "A pesquisar…" : "Pesquisar"}</button>
      </form>
      {err && <p className="error">{err}</p>}
      {res && (
        <div className="result">
          <p>{res.answer}</p>
          {res.results.map((r) => (
            <div key={r.id} className="hit">
              <a href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a>
              <p className="why">{r.reason}</p>
              {r.summary && <p>{r.summary}</p>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function MissionForm({ meta, initial, onSave, onCancel }: { meta: Meta | null; initial: typeof empty; onSave: (m: typeof empty) => void; onCancel: () => void }) {
  const [m, setM] = useState(initial);
  const toggle = (s: string) => setM({ ...m, sources: m.sources.includes(s) ? m.sources.filter((x) => x !== s) : [...m.sources, s] });
  return (
    <form className="card form" onSubmit={(e) => { e.preventDefault(); onSave(m); }}>
      <label>Nome<input required value={m.name} onChange={(e) => setM({ ...m, name: e.target.value })} /></label>
      <label>Instrução<textarea required rows={3} value={m.instruction} onChange={(e) => setM({ ...m, instruction: e.target.value })}
        placeholder="Avisa-me se aparecer algo sobre habitação em despachos." /></label>
      <fieldset><legend>Fontes (nenhuma = todas)</legend>
        {meta?.sources.filter((s) => s.available).map((s) => (
          <label key={s.name} className="check"><input type="checkbox" checked={m.sources.includes(s.name)} onChange={() => toggle(s.name)} />{s.label}</label>
        ))}
      </fieldset>
      <div className="row">
        <label>Frequência
          <select value={m.frequency} onChange={(e) => setM({ ...m, frequency: e.target.value as "daily" | "weekly" })}>
            <option value="daily">Diária</option><option value="weekly">Semanal</option>
          </select></label>
        <label className="check"><input type="checkbox" checked={m.use_web} onChange={(e) => setM({ ...m, use_web: e.target.checked })} />Incluir web aberta (se o provider suportar)</label>
      </div>
      <div className="row end"><button type="button" className="ghost" onClick={onCancel}>Cancelar</button><button className="primary">Guardar</button></div>
    </form>
  );
}

export default function MissionsPage({ meta }: { meta: Meta | null }) {
  const [list, setList] = useState<Mission[]>([]);
  const [sel, setSel] = useState<Mission | null>(null);
  const [alerts, setAlerts] = useState<MissionAlert[]>([]);
  const [editing, setEditing] = useState<Mission | "new" | null>(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => setList(await api.get<Mission[]>("/missions")), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (sel) api.get<MissionAlert[]>(`/missions/${sel.id}/alerts`).then(setAlerts); else setAlerts([]); }, [sel]);

  const save = async (m: typeof empty) => {
    if (editing === "new") await api.post("/missions", m); else if (editing) await api.patch(`/missions/${editing.id}`, m);
    setEditing(null); await load();
  };
  const toggle = async (m: Mission) => { await api.patch(`/missions/${m.id}`, { active: !m.active }); load(); };
  const run = async (m: Mission) => {
    setMsg("A executar…");
    try { const r = await api.post<{ created: number }>(`/missions/${m.id}/run`); setMsg(`${r.created} novos alertas.`); load(); if (sel?.id === m.id) setSel({ ...m }); }
    catch (x) { setMsg((x as Error).message); }
  };
  const remove = async (m: Mission) => { if (confirm(`Apagar a missão "${m.name}"?`)) { await api.del(`/missions/${m.id}`); setSel(null); load(); } };

  return (
    <>
      <div className="page-head"><h2>Missões</h2><button className="primary" onClick={() => setEditing("new")}>Nova missão</button></div>
      <FreeSearch />
      {editing && <MissionForm meta={meta} initial={editing === "new" ? empty : { name: editing.name, instruction: editing.instruction, sources: editing.sources, frequency: editing.frequency, active: editing.active, use_web: editing.use_web }} onSave={save} onCancel={() => setEditing(null)} />}
      <div className="cols">
        <div className="stack">
          {list.length === 0 && <p className="empty">Ainda não há missões.</p>}
          {list.map((m) => (
            <div key={m.id} className={"card mission" + (sel?.id === m.id ? " selected" : "") + (m.active ? "" : " paused")} onClick={() => setSel(m)}>
              <div className="meta"><span className="tag">{m.active ? "ativa" : "pausada"}</span><span>{m.frequency === "daily" ? "diária" : "semanal"}</span><span>{m.alerts} alertas</span></div>
              <h3>{m.name}</h3><p className="muted">{m.instruction}</p>
              <div className="actions" onClick={(e) => e.stopPropagation()}>
                <button className="link" onClick={() => setEditing(m)}>Editar</button>
                <button className="link" onClick={() => toggle(m)}>{m.active ? "Pausar" : "Retomar"}</button>
                <button className="link" onClick={() => run(m)}>Executar agora</button>
                <button className="link danger" onClick={() => remove(m)}>Apagar</button>
              </div>
            </div>
          ))}
          {msg && <p className="muted">{msg}</p>}
        </div>
        <div className="stack">
          {sel ? <h3 className="sub">Alertas — {sel.name}</h3> : <p className="empty">Seleciona uma missão para ver os alertas.</p>}
          {sel && alerts.length === 0 && <p className="empty">Sem alertas ainda.</p>}
          {alerts.map((a) => (
            <article key={a.id} className="card alert">
              <h3>{a.title}</h3><p className="why">{a.reason}</p>{a.summary && <p>{a.summary}</p>}
              <div className="actions"><a href={a.url} target="_blank" rel="noreferrer">Fonte original ↗</a>
                <Feedback path={`/mission-alerts/${a.id}/feedback`} value={a.feedback} /></div>
            </article>
          ))}
        </div>
      </div>
    </>
  );
}
