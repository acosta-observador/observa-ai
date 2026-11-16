"""X/Twitter — conector OPCIONAL. Desligado por defeito (ENABLE_X=false). O resto da app não depende dele.

Implementação mínima com a API v2 (pesquisa recente) e bearer token. POR VALIDAR: depende do plano da API X
(o acesso de leitura é pago) e das contas/consultas definidas em X_QUERY."""
from __future__ import annotations

import datetime as dt
import os
from typing import List, Optional, Tuple

import httpx

from ..config import settings
from .base import RawDocument, SourceConnector

API = "https://api.twitter.com/2/tweets/search/recent"


class XConnector(SourceConnector):
    name = "x"
    label = "X/Twitter (opcional)"
    default_enabled = False

    def availability(self) -> Tuple[bool, str]:
        if not settings.enable_x:
            return False, "desligado (ENABLE_X=false)"
        if not settings.x_bearer_token:
            return False, "sem X_BEARER_TOKEN"
        return True, "ok (por validar)"

    def fetch(self, since: dt.datetime) -> List[RawDocument]:
        ok, _ = self.availability()
        if not ok:
            return []
        query = os.getenv("X_QUERY", "(from:govpt OR from:ProtecaoCivil OR from:IPMA_pt) -is:retweet lang:pt")
        r = httpx.get(API, params={"query": query, "max_results": 50, "tweet.fields": "created_at"},
                      headers={"Authorization": f"Bearer {settings.x_bearer_token}", "User-Agent": settings.user_agent}, timeout=30)
        r.raise_for_status()
        out: List[RawDocument] = []
        for t in r.json().get("data", []):
            created: Optional[dt.datetime] = None
            if t.get("created_at"):
                created = dt.datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            out.append(RawDocument(source=self.name, external_id=t["id"], url=f"https://x.com/i/web/status/{t['id']}",
                                   title=t["text"][:120], text=t["text"], doc_type="tweet", published_at=created))
        return out
