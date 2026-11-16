"""Georreferenciação 100% local: concelho/distrito -> coordenadas (centroides)."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Optional

_DATA = Path(__file__).parent / "data" / "pt_places.json"

ALIASES = {
    "acores": "Açores", "regiao autonoma dos acores": "Açores", "r.a. acores": "Açores",
    "madeira": "Madeira", "regiao autonoma da madeira": "Madeira", "r.a. madeira": "Madeira",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(concelho|municipio|distrito|camara municipal|cm) (de |do |da )?", "", s)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


class Place(NamedTuple):
    concelho: Optional[str]
    distrito: Optional[str]
    lat: float
    lon: float
    level: str  # concelho | distrito | regiao


@lru_cache(maxsize=1)
def _load():
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    conc: dict = {}
    for c in data["concelhos"]:
        conc.setdefault(norm(c["name"]), []).append(c)
    dist = {norm(d["name"]): d for d in data["distritos"] + data["regioes"]}
    return data, conc, dist


def all_places() -> dict:
    return _load()[0]


def locate(concelho: Optional[str] = None, distrito: Optional[str] = None) -> Optional[Place]:
    """Devolve o ponto mais específico possível. Concelho tem prioridade; o distrito desambigua homónimos."""
    _, conc, dist = _load()
    dkey = norm(distrito) if distrito else ""
    dkey = norm(ALIASES.get(dkey, distrito)) if dkey else ""
    if concelho:
        matches = conc.get(norm(concelho)) or []
        if matches:
            pick = next((m for m in matches if dkey and norm(m["parent"]) == dkey), matches[0])
            return Place(pick["name"], pick["parent"], pick["lat"], pick["lon"], "concelho")
    if dkey and dkey in dist:
        d = dist[dkey]
        level = "regiao" if d["name"] in ("Açores", "Madeira") else "distrito"
        return Place(None, d["name"], d["lat"], d["lon"], level)
    # concelho que coincide com nome de distrito (ex.: "Lisboa", "Porto") sem distrito explícito
    if concelho and norm(concelho) in dist:
        d = dist[norm(concelho)]
        return Place(None, d["name"], d["lat"], d["lon"], "distrito")
    return None


def find_in_text(text: str) -> Optional[Place]:
    """Fallback grosseiro: procura nomes de concelhos no texto (usa o mais longo). Só concelhos com nome >= 5 letras."""
    _, conc, _ = _load()
    hay = " " + norm(text) + " "
    best = None
    for k, v in conc.items():
        if len(k) >= 5 and f" {k} " in hay and (best is None or len(k) > len(best[0])):
            best = (k, v[0])
    if best:
        c = best[1]
        return Place(c["name"], c["parent"], c["lat"], c["lon"], "concelho")
    return None
