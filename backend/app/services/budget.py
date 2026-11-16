"""Controlo de custos: limite diário de chamadas ao LLM (MAX_LLM_CALLS_PER_DAY)."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..config import settings
from ..llm.base import BudgetExceeded, LLMProvider
from ..models import LLMUsage


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def calls_today(db: Session) -> int:
    row = db.get(LLMUsage, today())
    return row.calls if row else 0


def remaining(db: Session) -> int:
    return max(0, settings.max_llm_calls_per_day - calls_today(db))


def _count(db: Session) -> None:
    row = db.get(LLMUsage, today())
    if row is None:
        row = LLMUsage(day=today(), calls=0)
        db.add(row)
    row.calls += 1
    db.commit()


class BudgetedLLM:
    """Envolve um LLMProvider e recusa chamadas acima do limite diário."""

    def __init__(self, db: Session, provider: LLMProvider):
        self.db = db
        self.provider = provider

    @property
    def supports_web_search(self) -> bool:
        return self.provider.supports_web_search

    def _check(self) -> None:
        if remaining(self.db) <= 0:
            raise BudgetExceeded(f"Limite diário de {settings.max_llm_calls_per_day} chamadas ao LLM atingido")

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> Dict[str, Any]:
        self._check()
        _count(self.db)
        return self.provider.complete_json(system, user, max_tokens)

    def web_search(self, query: str) -> List[Dict[str, str]]:
        self._check()
        _count(self.db)
        return self.provider.web_search(query)
