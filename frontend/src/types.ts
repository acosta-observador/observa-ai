export interface Alert {
  id: number; source: string; url: string; title: string; category: string | null; score: number | null;
  summary: string | null; why: string | null; entities: { people?: string[]; orgs?: string[] };
  concelho: string | null; distrito: string | null; lat: number | null; lon: number | null;
  published_at: string; feedback: "useful" | "noise" | null;
}
export interface SourceInfo { name: string; label: string; available: boolean; note: string; enabled: boolean }
export interface Meta { categories: string[]; sources: SourceInfo[]; threshold: number }
export interface Mission {
  id: number; name: string; instruction: string; sources: string[]; frequency: "daily" | "weekly";
  active: boolean; use_web: boolean; last_run_at: string | null; alerts: number;
}
export interface MissionAlert {
  id: number; title: string; reason: string; summary: string; url: string; source: string | null;
  created_at: string; feedback: "useful" | "noise" | null;
}
export interface SearchResult {
  answer: string;
  results: { id: number; title: string; url: string; source: string; reason: string; summary: string | null; concelho: string | null; published_at: string }[];
}
export interface SettingsData {
  threshold: number; sources: SourceInfo[];
  ai: { provider: string; calls_today: number; max_calls_per_day: number; remaining: number };
  documents: { total: number; classified: number; pending: number; no_text: number };
}
export interface FeedbackStats {
  total: number; useful: number; noise: number; rate: number | null;
  series: { day: string; useful: number; noise: number; rate: number }[];
}
