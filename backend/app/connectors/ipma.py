"""IPMA - avisos meteorológicos. API aberta: https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from ..config import settings
from .base import RawDocument, SourceConnector
from .http import PoliteClient

URL = "https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json"
LEVELS = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
LEVEL_PT = {"yellow": "amarelo", "orange": "laranja", "red": "vermelho"}

# idAreaAviso -> (distrito/região, concelho de referência para o ponto no mapa)
AREAS = {
    "AVR": ("Aveiro", None), "BJA": ("Beja", None), "BRG": ("Braga", None), "BGC": ("Bragança", None),
    "CBO": ("Castelo Branco", None), "CBR": ("Coimbra", None), "EVR": ("Évora", None), "FAR": ("Faro", None),
    "GDA": ("Guarda", None), "LRA": ("Leiria", None), "LSB": ("Lisboa", None), "PTG": ("Portalegre", None),
    "PTO": ("Porto", None), "STM": ("Santarém", None), "STB": ("Setúbal", None), "VCT": ("Viana do Castelo", None),
    "VRL": ("Vila Real", None), "VIS": ("Viseu", None),
    "MCN": ("Madeira", "Santana"), "MCS": ("Madeira", "Funchal"), "MPS": ("Madeira", "Porto Santo"), "MRM": ("Madeira", "Funchal"),
    "AOR": ("Açores", "Ponta Delgada"), "ACE": ("Açores", "Angra do Heroísmo"), "AOC": ("Açores", "Santa Cruz das Flores"),
}


class IPMAConnector(SourceConnector):
    name = "ipma"
    label = "IPMA — avisos meteorológicos"

    def __init__(self, client: Optional[PoliteClient] = None):
        self.client = client or PoliteClient(cache_ttl=0)

    def fetch(self, since: dt.datetime) -> List[RawDocument]:
        min_level = LEVELS.get(settings.ipma_min_level, 2)
        out: List[RawDocument] = []
        for w in self.client.get_json(URL):
            level = w.get("awarenessLevelID", "green")
            if LEVELS.get(level, 0) < min_level:
                continue
            area = AREAS.get(w.get("idAreaAviso", ""))
            if not area:
                continue
            distrito, concelho = area
            start = _parse(w.get("startTime"))
            end = _parse(w.get("endTime"))
            tipo = w.get("awarenessTypeName", "Aviso")
            title = f"Aviso {LEVEL_PT.get(level, level)} — {tipo} — {distrito}"
            text = f"{tipo}, nível {LEVEL_PT.get(level, level)}, para {distrito}. Válido de {w.get('startTime')} a {w.get('endTime')}. {w.get('text') or ''}".strip()
            out.append(RawDocument(
                source=self.name, external_id=f"{w['idAreaAviso']}|{tipo}|{w.get('startTime')}|{level}",
                url="https://www.ipma.pt/pt/otempo/prev.aviso/", title=title, text=text, doc_type="aviso meteorológico",
                published_at=start, hint_distrito=distrito, hint_concelho=concelho,
            ))
        return out


def _parse(s: Optional[str]) -> Optional[dt.datetime]:
    try:
        return dt.datetime.fromisoformat(s) if s else None
    except ValueError:
        return None
