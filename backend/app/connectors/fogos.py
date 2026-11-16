"""Ocorrências ativas (incêndios/proteção civil) via API aberta do fogos.pt (projeto de terceiros;
a ANEPC não publica API aberta equivalente). Tem rate limit: um pedido por execução."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from ..config import settings
from .base import RawDocument, SourceConnector
from .http import PoliteClient

URL = "https://api.fogos.pt/v2/incidents/active"


class FogosConnector(SourceConnector):
    name = "fogos"
    label = "Proteção Civil — ocorrências (fogos.pt)"

    def __init__(self, client: Optional[PoliteClient] = None):
        self.client = client or PoliteClient(cache_ttl=0)

    def fetch(self, since: dt.datetime) -> List[RawDocument]:
        data = self.client.get_json(URL).get("data", [])
        out: List[RawDocument] = []
        for i in data:
            men = int(i.get("man") or 0)
            if men < settings.fogos_min_men and not i.get("important"):
                continue
            ts = (i.get("dateTime") or {}).get("sec")
            when = dt.datetime.utcfromtimestamp(ts) if ts else dt.datetime.utcnow()
            nat = i.get("natureza") or "Ocorrência"
            title = f"{nat} — {i.get('concelho') or i.get('location')} ({i.get('district') or ''})".strip()
            text = (f"{nat} em {i.get('location')}. Estado: {i.get('status')}. Meios: {men} operacionais, "
                    f"{i.get('terrain') or 0} terrestres, {i.get('aerial') or 0} aéreos. {i.get('detailLocation') or ''}")
            out.append(RawDocument(
                source=self.name, external_id=str(i["id"]), url=f"https://fogos.pt/fogo/{i['id']}", title=title, text=text,
                doc_type="ocorrência", published_at=when, hint_lat=i.get("lat"), hint_lon=i.get("lng"),
                hint_distrito=i.get("district"), hint_concelho=i.get("concelho"),
            ))
        return out
