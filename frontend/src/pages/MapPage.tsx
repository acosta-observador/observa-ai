import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { api, qs } from "../api";
import AlertCard from "../components/AlertCard";
import Filters, { FilterState } from "../components/Filters";
import type { Alert, Meta } from "../types";

const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: { osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 18,
    attribution: "© OpenStreetMap contributors" } },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};
const FONT = ["Open Sans Regular", "Arial Unicode MS Regular"];
const MAX_CLUSTER_ZOOM = 12;
const VIEWS: Record<string, { c: [number, number]; z: number }> = {
  Continente: { c: [-8.0, 39.6], z: 5.4 }, Açores: { c: [-27.2, 38.6], z: 5.6 }, Madeira: { c: [-16.95, 32.75], z: 8.4 },
};

// Alertas no mesmo centroide ficam espalhados num pequeno círculo para serem clicáveis.
function toGeoJSON(items: Alert[]) {
  const seen = new Map<string, number>();
  return {
    type: "FeatureCollection" as const,
    features: items.filter((a) => a.lat !== null && a.lon !== null).map((a) => {
      const k = `${a.lat},${a.lon}`; const n = seen.get(k) ?? 0; seen.set(k, n + 1);
      const ang = n * 2.399, r = n === 0 ? 0 : 0.012 * Math.sqrt(n);
      return { type: "Feature" as const, properties: { id: a.id, score: a.score ?? 0 },
        geometry: { type: "Point" as const, coordinates: [a.lon! + r * Math.cos(ang), a.lat! + r * Math.sin(ang)] } };
    }),
  };
}

export default function MapPage({ meta }: { meta: Meta }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const itemsRef = useRef<Alert[]>([]);
  const [f, setF] = useState<FilterState>({ category: "", source: "", date: "", days: 7 });
  const [items, setItems] = useState<Alert[]>([]);
  const [selected, setSelected] = useState<Alert[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    const m = new maplibregl.Map({ container: el.current!, style: STYLE, center: [-8.0, 39.6], zoom: 5.4, minZoom: 4 });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    const css = getComputedStyle(document.documentElement);
    const accent = css.getPropertyValue("--accent").trim() || "#2f6fed";
    m.on("load", () => {
      m.addSource("alerts", { type: "geojson", data: toGeoJSON([]), cluster: true, clusterMaxZoom: MAX_CLUSTER_ZOOM, clusterRadius: 48 });
      m.addLayer({ id: "clusters", type: "circle", source: "alerts", filter: ["has", "point_count"],
        paint: { "circle-color": accent, "circle-opacity": 0.88, "circle-stroke-color": "#fff", "circle-stroke-width": 2,
          "circle-radius": ["step", ["get", "point_count"], 16, 5, 20, 15, 26] } });
      m.addLayer({ id: "cluster-count", type: "symbol", source: "alerts", filter: ["has", "point_count"],
        layout: { "text-field": "{point_count_abbreviated}", "text-font": FONT, "text-size": 13 }, paint: { "text-color": "#fff" } });
      m.addLayer({ id: "points", type: "circle", source: "alerts", filter: ["!", ["has", "point_count"]],
        paint: { "circle-color": accent, "circle-radius": ["interpolate", ["linear"], ["get", "score"], 0, 6, 100, 11],
          "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
      m.on("click", "points", (e) => {
        const id = e.features?.[0]?.properties?.id;
        setSelected(itemsRef.current.filter((a) => a.id === id));
      });
      m.on("click", "clusters", async (e) => {
        const feat = e.features![0];
        const src = m.getSource("alerts") as maplibregl.GeoJSONSource;
        const cid = feat.properties!.cluster_id as number;
        const zoom = await src.getClusterExpansionZoom(cid);
        const center = (feat.geometry as GeoJSON.Point).coordinates as [number, number];
        if (zoom > MAX_CLUSTER_ZOOM || m.getZoom() >= MAX_CLUSTER_ZOOM) {
          const leaves = await src.getClusterLeaves(cid, 50, 0);
          const ids = new Set(leaves.map((l) => l.properties!.id));
          setSelected(itemsRef.current.filter((a) => ids.has(a.id)).sort((a, b) => (b.score ?? 0) - (a.score ?? 0)));
        } else m.easeTo({ center, zoom: zoom + 0.3 });
      });
      for (const l of ["clusters", "points"]) {
        m.on("mouseenter", l, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", l, () => (m.getCanvas().style.cursor = ""));
      }
      (m as unknown as { _ready: boolean })._ready = true;
      m.fire("observa-ready");
    });
    return () => m.remove();
  }, []);

  useEffect(() => {
    api.get<Alert[]>("/alerts" + qs({ category: f.category, source: f.source, days: f.days, geo_only: true }))
      .then((d) => {
        setItems(d); itemsRef.current = d; setSelected([]);
        const apply = () => (map.current?.getSource("alerts") as maplibregl.GeoJSONSource | undefined)?.setData(toGeoJSON(d));
        const m = map.current as unknown as { _ready?: boolean } & maplibregl.Map;
        if (m?._ready) apply(); else m?.once("observa-ready", apply);
      }).catch((e) => setErr(e.message));
  }, [f]);

  return (
    <div className="mappage">
      <div className="mapbar">
        <Filters meta={meta} f={f} set={setF} mode="range" />
        <div className="seg" role="group" aria-label="Zona">
          {Object.entries(VIEWS).map(([k, v]) => <button key={k} onClick={() => map.current?.flyTo({ center: v.c, zoom: v.z })}>{k}</button>)}
        </div>
        <span className="muted">{items.length} no mapa</span>
        {err && <span className="error">{err}</span>}
      </div>
      <div className="mapwrap">
        <div ref={el} className="map" />
        {selected.length > 0 && (
          <aside className="sheet">
            <button className="link close" onClick={() => setSelected([])}>Fechar</button>
            <div className="stack">{selected.map((a) => <AlertCard key={a.id} a={a} />)}</div>
          </aside>
        )}
      </div>
    </div>
  );
}
