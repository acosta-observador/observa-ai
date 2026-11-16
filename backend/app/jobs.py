"""Entrada dos Render Cron Jobs (mesmo código do backend):

  python -m app.jobs ingest     # ingestão + classificação
  python -m app.jobs missions   # execução das missões
"""
from __future__ import annotations

import json
import logging
import sys

from .db import SessionLocal
from .llm import LLMError, get_provider
from .services import budget, ingest as ingest_svc, missions as mission_svc
from .services.classify import classify_pending

log = logging.getLogger("jobs")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    cmd = (argv or sys.argv[1:] or [""])[0]
    if cmd not in ("ingest", "missions"):
        print(__doc__)
        return 2
    with SessionLocal() as db:
        try:
            llm = budget.BudgetedLLM(db, get_provider())
        except LLMError as e:
            log.error("IA indisponível: %s", e)
            llm = None
        if cmd == "ingest":
            report = {"ingest": ingest_svc.ingest(db)}
            if llm:
                report["classify"] = classify_pending(db, llm)
        else:
            if llm is None:
                return 1
            report = mission_svc.run_missions(db, llm)
        log.info("%s", json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
