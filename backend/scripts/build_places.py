"""Gera backend/app/data/pt_places.json a partir do Wikidata (execução única, offline em runtime).

Uso: python backend/scripts/build_places.py
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

DISTRITOS = {
    "Aveiro": (40.6405, -8.6538), "Beja": (38.0151, -7.8632), "Braga": (41.5454, -8.4265),
    "Bragança": (41.8060, -6.7567), "Castelo Branco": (39.8222, -7.4909), "Coimbra": (40.2033, -8.4103),
    "Évora": (38.5710, -7.9135), "Faro": (37.0194, -7.9304), "Guarda": (40.5373, -7.2675),
    "Leiria": (39.7437, -8.8071), "Lisboa": (38.7223, -9.1393), "Portalegre": (39.2967, -7.4285),
    "Porto": (41.1579, -8.6291), "Santarém": (39.2369, -8.6850), "Setúbal": (38.5244, -8.8882),
    "Viana do Castelo": (41.6918, -8.8345), "Vila Real": (41.3006, -7.7441), "Viseu": (40.6610, -7.9097),
}
REGIOES = {"Açores": (37.7412, -25.6756), "Madeira": (32.6669, -16.9241)}
EXCLUIR = {"Lafões"}  # comunidade intermunicipal histórica, não é concelho
OVERRIDE_REGIAO = {"Lagoa": "Açores"}  # homónimo (Lagoa, Algarve vs. Lagoa, S. Miguel) com P131 estranho

SPARQL = """SELECT ?m ?mLabel ?coord ?pLabel WHERE {
  ?m wdt:P31 wd:Q13217644 . ?m wdt:P625 ?coord .
  OPTIONAL { ?m wdt:P131 ?p . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt,en". } }"""


def main() -> None:
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": SPARQL})
    req = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json", "User-Agent": "ObservaAI-internal/0.1"})
    rows = json.load(urllib.request.urlopen(req, timeout=90))["results"]["bindings"]
    muni: dict = {}
    for b in rows:
        name = b["mLabel"]["value"]
        if name in EXCLUIR:
            continue
        lon, lat = map(float, re.findall(r"-?\d+\.?\d*", b["coord"]["value"]))
        e = muni.setdefault(b["m"]["value"], {"name": name, "lat": lat, "lon": lon, "ps": set()})
        if "pLabel" in b:
            e["ps"].add(b["pLabel"]["value"])
    out = []
    for e in muni.values():
        reg = OVERRIDE_REGIAO.get(e["name"]) if e["name"] in OVERRIDE_REGIAO and not (e["ps"] & set(DISTRITOS)) else None
        cands = [p for p in e["ps"] if p in DISTRITOS or p in REGIOES]
        parent = reg or (cands[0] if cands else None)
        if parent:
            out.append({"name": e["name"], "parent": parent, "lat": round(e["lat"], 4), "lon": round(e["lon"], 4)})
    out.sort(key=lambda x: x["name"])
    data = {
        "concelhos": out,
        "distritos": [{"name": k, "lat": v[0], "lon": v[1]} for k, v in DISTRITOS.items()],
        "regioes": [{"name": k, "lat": v[0], "lon": v[1]} for k, v in REGIOES.items()],
    }
    assert len(out) == 308, f"esperados 308 concelhos, obtidos {len(out)}"
    dest = Path(__file__).resolve().parents[1] / "app" / "data" / "pt_places.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    print("ok", len(out))


if __name__ == "__main__":
    main()
