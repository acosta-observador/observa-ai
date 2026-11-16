"""Diário da República.

ESTADO REAL (verificado em 2026-11-16):
- Não há RSS nem API oficial acessíveis (dre.pt/rss devolve a SPA; sem dados abertos da INCM no dados.gov.pt).
- robots.txt permite acesso e publica um sitemap (https://files.dre.pt/sitemap/sitemap.xml) com <lastmod> por URL.
- As páginas de detalhe são uma SPA OutSystems: sem JavaScript NÃO têm texto nem metadados.
Logo: este conector faz DESCOBERTA de publicações novas via sitemap (tipo, número/ano, link) com rate limit,
User-Agent identificado e cache. O texto integral NÃO é obtido (has_text=False): os documentos ficam guardados
mas não são classificados por IA até existir uma fonte de texto legítima (ver README, secção 'Por validar').
"""
from __future__ import annotations

import datetime as dt
import re
from typing import List, Optional, Tuple

from .base import RawDocument, SourceConnector
from .http import PoliteClient

INDEX = "https://files.dre.pt/sitemap/sitemap.xml"
# tipos de interesse jornalístico -> rótulo
TYPES = {
    "despacho": "Despacho", "portaria": "Portaria", "aviso": "Aviso", "decreto": "Decreto",
    "resolucao": "Resolução", "decreto-lei": "Decreto-Lei", "lei": "Lei", "edital": "Edital",
}
_LOC = re.compile(r"<loc>([^<]*)</loc>\s*<lastmod>([^<]*)</lastmod>")


class DREConnector(SourceConnector):
    name = "dre"
    label = "Diário da República (só descoberta)"
    has_text = False

    def __init__(self, client: Optional[PoliteClient] = None, max_urls: int = 400):
        self.client = client or PoliteClient(min_interval=1.0, cache_ttl=6 * 3600, timeout=60)
        self.max_urls = max_urls

    def availability(self):
        return True, "só descoberta: sem texto integral (SPA com JavaScript)"

    def _entries(self, xml: str) -> List[Tuple[str, str]]:
        return _LOC.findall(xml)

    def fetch(self, since: dt.datetime) -> List[RawDocument]:
        since_s = since.date().isoformat()
        index = self._entries(self.client.get_text(INDEX))
        # por tipo, só o sub-sitemap mais recente (o de maior número) com lastmod >= since
        latest = {}
        for loc, lastmod in index:
            m = re.search(r"/sitemap/([a-z\-]+?)-sitemap-(\d+)\.xml$", loc)
            if not m or m.group(1) not in TYPES or lastmod < since_s:
                continue
            t, n = m.group(1), int(m.group(2))
            if t not in latest or n > latest[t][0]:
                latest[t] = (n, loc)
        out: List[RawDocument] = []
        for t, (_, loc) in latest.items():
            for url, lastmod in self._entries(self.client.get_text(loc)):
                if lastmod < since_s:
                    continue
                doc = _doc_from_url(url, lastmod)
                if doc:
                    out.append(doc)
                if len(out) >= self.max_urls:
                    return out
        return out


def _doc_from_url(url: str, lastmod: str) -> Optional[RawDocument]:
    m = re.search(r"/detalhe/([a-z\-]+)/([^/]+)$", url)
    if not m:
        return None
    tipo, slug = m.group(1), m.group(2)
    label = TYPES.get(tipo, tipo.capitalize())
    parts = slug.split("-")
    ident = "-".join(parts[:-1]) if len(parts) > 1 else slug
    num_year = re.match(r"^(.+)-(\d{4})$", ident)
    title = f"{label} n.º {num_year.group(1)}/{num_year.group(2)}" if num_year else f"{label} {ident}"
    try:
        when = dt.datetime.fromisoformat(lastmod)
    except ValueError:
        when = None
    return RawDocument(source="dre", external_id=slug, url=url, title=title, text="", doc_type=tipo, published_at=when)
