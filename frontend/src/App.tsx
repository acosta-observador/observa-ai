import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Meta } from "./types";
import TodayPage from "./pages/TodayPage";
import MapPage from "./pages/MapPage";
import MissionsPage from "./pages/MissionsPage";
import SettingsPage from "./pages/SettingsPage";

const TABS = [["hoje", "Hoje"], ["mapa", "Mapa"], ["missoes", "Missões"], ["definicoes", "Definições"]] as const;
type Tab = typeof TABS[number][0];

function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api.post("/login", { password: pw }); onDone(); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Erro de ligação"); }
  };
  return (
    <main className="login">
      <form onSubmit={submit} className="card login-card">
        <h1>Observa AI</h1>
        <p className="muted">Ferramenta interna do Observador.</p>
        <input type="password" autoFocus placeholder="Password" value={pw} onChange={(e) => setPw(e.target.value)} />
        {err && <p className="error">{err}</p>}
        <button className="primary" type="submit">Entrar</button>
      </form>
    </main>
  );
}

export default function App() {
  const [auth, setAuth] = useState<"loading" | "no" | "yes">("loading");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [tab, setTab] = useState<Tab>(() => (TABS.find((t) => t[0] === location.hash.slice(1))?.[0] ?? "hoje"));

  const boot = useCallback(async () => {
    try {
      const s = await api.get<{ authenticated: boolean }>("/session");
      if (!s.authenticated) return setAuth("no");
      setMeta(await api.get<Meta>("/meta"));
      setAuth("yes");
    } catch { setAuth("no"); }
  }, []);
  useEffect(() => { boot(); }, [boot]);
  useEffect(() => { location.hash = tab; }, [tab]);

  if (auth === "loading") return <main className="login"><p className="muted">A carregar…</p></main>;
  if (auth === "no") return <Login onDone={boot} />;

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Observa AI</span>
        <nav>
          {TABS.map(([k, label]) => (
            <button key={k} className={"tab" + (tab === k ? " active" : "")} onClick={() => setTab(k)}>{label}</button>
          ))}
        </nav>
        <button className="link" onClick={async () => { await api.post("/logout"); setAuth("no"); }}>Sair</button>
      </header>
      <main className={"content" + (tab === "mapa" ? " wide" : "")}>
        {meta && tab === "hoje" && <TodayPage meta={meta} />}
        {meta && tab === "mapa" && <MapPage meta={meta} />}
        {tab === "missoes" && <MissionsPage meta={meta} />}
        {tab === "definicoes" && <SettingsPage onChange={boot} />}
      </main>
    </div>
  );
}
