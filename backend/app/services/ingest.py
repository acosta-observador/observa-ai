from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors import registry
from ..models import Document, utcnow
from . import app_settings
from .classify import classify_pending

log = logging.getLogger(__name__)


def ingest(db: Session, connectors: Optional[dict] = None, lookback_days: int = 2) -> Dict[str, Any]:
    """Ingere fontes ativas. Guarda o bruto (deduplicado por fonte+id); não classifica."""
    connectors = connectors if connectors is not None else registry()
    enabled = app_settings.enabled_sources(db)
    since = utcnow() - dt.timedelta(days=lookback_days)
    report: Dict[str, Any] = {}
    for name, conn in connectors.items():
        if name not in enabled:
            report[name] = {"skipped": "desativada"}
            continue
        ok, why = conn.availability()
        if not ok:
            report[name] = {"skipped": why}
            continue
        try:
            raws = conn.fetch(since)
        except Exception as e:  # uma fonte em baixo não pode parar as outras
            log.exception("Conector %s falhou", name)
            report[name] = {"error": str(e)[:200]}
            continue
        known = set(db.scalars(select(Document.external_id).where(Document.source == name)))
        new = 0
        for r in raws:
            if r.external_id in known:
                continue
            known.add(r.external_id)
            db.add(Document(
                source=r.source, external_id=r.external_id, url=r.url, title=r.title[:512], text=(r.text or "")[:20000],
                doc_type=r.doc_type, published_at=r.published_at or utcnow(), hint_lat=r.hint_lat, hint_lon=r.hint_lon,
                hint_distrito=r.hint_distrito, hint_concelho=r.hint_concelho,
                status="pending" if conn.has_text else "no_text"))
            new += 1
        db.commit()
        report[name] = {"fetched": len(raws), "new": new}
    return report


def run_daily(db: Session, llm=None) -> Dict[str, Any]:
    report = {"ingest": ingest(db)}
    if llm is not None:
        report["classify"] = classify_pending(db, llm)
    return report
