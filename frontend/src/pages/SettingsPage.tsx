import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { FeedbackStats, SettingsData } from "../types";

export default function SettingsPage({ onChange }: { onChange: () => void }) {
  const [s, setS] = useState<SettingsData | null>(null);
  const [st, setSt] = useState<FeedbackStats | null>(null);
  const [th, setTh] = useState(40);
  const load = useCallback(async () => {
    const d = await api.get<SettingsData>("/settings"); setS(d); setTh(d.threshold);
    setSt(await api.get<FeedbackStats>("/feedback/stats"));
  }, []);
  useEffect(() => { load(); }, [load]);
  if (!s) return <p className="muted">A carregar…</p>;

  const saveTh = async () => { setS(await api.put<SettingsData>("/settings", { threshold: th })); onChange(); };
  const toggleSource = async (name: string) => {
    const enabled = s.sources.filter((x) => x.enabled).map((x) => x.name);
    const next = enabled.includes(name) ? enabled.filter((x) => x !== name) : [...enabled, name];
    setS(await api.put<SettingsData>("/settings", { enabled_sources: next })); onChange();
  };
  const pct = Math.min(100, Math.round((100 * s.ai.calls_today) / Math.max(1, s.ai.max_calls_per_day)));
  const max = Math.max(1, ...(st?.series.map((d) => d.useful + d.noise) ?? [1]));

  return (
    <>
      <div className="page-head"><h2>Definições</h2></div>
      <section className="card">
        <h3>Limiar de relevância</h3>
        <p className="muted">Abaixo deste score os documentos ficam guardados mas escondidos.</p>
        <div className="row"><input type="range" min={0} max={100} value={th} onChange={(e) => setTh(+e.target.value)} /><strong className="num">{th}</strong>
          <button className="primary" onClick={saveTh} disabled={th === s.threshold}>Guardar</button></div>
      </section>
      <section className="card">
        <h3>Fontes</h3>
        {s.sources.map((x) => (
          <label key={x.name} className={"check src" + (x.available ? "" : " off")}>
            <input type="checkbox" checked={x.enabled} disabled={!x.available} onChange={() => toggleSource(x.name)} />
            <span>{x.label}<small className="muted"> — {x.note}</small></span>
          </label>
        ))}
        <p className="muted">Documentos: {s.documents.classified} classificados · {s.documents.pending} pendentes · {s.documents.no_text} sem texto.</p>
      </section>
      <section className="card">
        <h3>Gasto de IA hoje</h3>
        <div className="bar"><div style={{ width: pct + "%" }} /></div>
        <p className="muted">{s.ai.calls_today} / {s.ai.max_calls_per_day} chamadas · provider: {s.ai.provider}</p>
      </section>
      <section className="card">
        <h3>Utilidade dos alertas</h3>
        {st && st.total > 0 ? (<>
          <p><strong className="num">{st.rate}%</strong> úteis <span className="muted">({st.useful} úteis · {st.noise} ruído · últimos 30 dias)</span></p>
          <div className="spark" aria-label="Votos por dia">
            {st.series.map((d) => (
              <div key={d.day} className="col" title={`${d.day}: ${d.rate}% úteis (${d.useful}/${d.useful + d.noise})`}>
                <div className="stackbar" style={{ height: `${(100 * (d.useful + d.noise)) / max}%` }}>
                  <div className="n" style={{ flex: d.noise }} /><div className="u" style={{ flex: d.useful }} />
                </div>
              </div>
            ))}
          </div>
          <p className="muted">Cada barra é um dia (parte cheia = úteis). Os votos recentes entram no prompt de classificação.</p>
        </>) : <p className="muted">Ainda sem feedback. Usa “Útil” / “Ruído” nos alertas.</p>}
      </section>
    </>
  );
}
