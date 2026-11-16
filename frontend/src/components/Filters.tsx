import type { Meta } from "../types";

export interface FilterState { category: string; source: string; date: string; days: number }

export default function Filters({ meta, f, set, mode }: { meta: Meta; f: FilterState; set: (f: FilterState) => void; mode: "date" | "range" }) {
  return (
    <div className="filters">
      <select value={f.category} onChange={(e) => set({ ...f, category: e.target.value })} aria-label="Categoria">
        <option value="">Todas as categorias</option>
        {meta.categories.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      <select value={f.source} onChange={(e) => set({ ...f, source: e.target.value })} aria-label="Fonte">
        <option value="">Todas as fontes</option>
        {meta.sources.filter((s) => s.available).map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
      </select>
      {mode === "date" ? (
        <input type="date" value={f.date} onChange={(e) => set({ ...f, date: e.target.value })} aria-label="Data" title="Vazio = últimas 24h" />
      ) : (
        <div className="seg" role="group" aria-label="Período">
          {[[1, "24h"], [7, "7 dias"], [30, "30 dias"]].map(([d, l]) => (
            <button key={d} className={f.days === d ? "on" : ""} onClick={() => set({ ...f, days: d as number })}>{l}</button>
          ))}
        </div>
      )}
    </div>
  );
}
