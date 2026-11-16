from __future__ import annotations

from typing import Any, List

from sqlalchemy.orm import Session

from ..config import settings
from ..connectors import CONNECTOR_CLASSES
from ..models import Setting


def get(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(Setting, key)
    return row.value if row is not None else default


def put(db: Session, key: str, value: Any) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def threshold(db: Session) -> int:
    return int(get(db, "relevance_threshold", settings.relevance_threshold))


def enabled_sources(db: Session) -> List[str]:
    stored = get(db, "enabled_sources", None)
    if stored is not None:
        return list(stored)
    out = []
    for c in CONNECTOR_CLASSES:
        inst = c()
        if inst.default_enabled and inst.availability()[0]:
            out.append(inst.name)
    return out
