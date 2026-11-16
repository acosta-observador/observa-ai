"""Classificação por LLM em lotes, com few-shot dinâmico a partir do feedback."""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import geo
from ..config import settings
from ..llm.base import BudgetExceeded, LLMError
from ..models import Document, Feedback, utcnow

log = logging.getLogger(__name__)

CATEGORIES = ["política", "habitação", "saúde", "autarquias", "justiça", "economia", "ambiente", "outros"]

SYSTEM = """És um assistente da redação do Observador (jornal português) que faz triagem de documentos oficiais e alertas.
Para cada documento decide se pode dar notícia. Critérios: impacto público, novidade, dinheiro público envolvido,
pessoas/entidades relevantes, risco para pessoas, decisões políticas ou administrativas com consequências.
Rotina administrativa sem impacto (retificações, nomeações menores, avisos genéricos) deve ter score baixo (< 30).
Escala: 0-29 ruído, 30-59 talvez, 60-79 relevante, 80-100 muito relevante.
Para cada item devolve: id (o mesmo recebido), score (0-100), category (uma de: {cats}), summary (2 frases em português),
why (porque pode ser notícia, 1 frase), people (lista de pessoas), orgs (lista de organizações),
concelho e distrito (nomes oficiais em Portugal, ou null se não houver localização clara).
Formato: {{"items":[{{"id":..,"score":..,"category":"..","summary":"..","why":"..","people":[],"orgs":[],"concelho":null,"distrito":null}}]}}"""


def few_shot_block(db: Session, n: int = 4) -> str:
    def recent(value: str) -> List[Document]:
        q = (select(Document).join(Feedback, Feedback.document_id == Document.id)
             .where(Feedback.value == value).order_by(Feedback.created_at.desc()).limit(n))
        return list(db.scalars(q))

    lines: List[str] = []
    for label, value in (("ÚTIL", "useful"), ("RUÍDO", "noise")):
        for d in recent(value):
            lines.append(f"- [{label}] ({d.source}) {d.title} — {(d.summary or d.text or '')[:140]}")
    if not lines:
        return ""
    return ("\nExemplos recentes de decisões dos jornalistas (usa-os para calibrar o score; "
            "'ÚTIL' = score alto, 'RUÍDO' = score baixo):\n" + "\n".join(lines) + "\n")


def build_prompts(db: Session, docs: List[Document]) -> tuple:
    payload = [{"id": d.id, "source": d.source, "type": d.doc_type, "title": d.title, "text": (d.text or "")[:1500],
                "hint_concelho": d.hint_concelho, "hint_distrito": d.hint_distrito} for d in docs]
    system = SYSTEM.format(cats=", ".join(CATEGORIES)) + few_shot_block(db)
    user = "Classifica os documentos abaixo.\n<docs>" + json.dumps(payload, ensure_ascii=False) + "</docs>"
    return system, user


def apply_result(doc: Document, item: Dict[str, Any]) -> None:
    try:
        score = int(round(float(item.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    doc.score = max(0, min(100, score))
    cat = str(item.get("category") or "outros").lower()
    doc.category = cat if cat in CATEGORIES else "outros"
    doc.summary = (item.get("summary") or doc.title)[:1000]
    doc.why = (item.get("why") or "")[:500]
    doc.entities = {"people": list(item.get("people") or [])[:12], "orgs": list(item.get("orgs") or [])[:12]}

    place = None
    if doc.hint_lat is not None and doc.hint_lon is not None:  # coordenadas exatas da fonte têm prioridade
        doc.lat, doc.lon = doc.hint_lat, doc.hint_lon
        place = geo.locate(doc.hint_concelho or item.get("concelho"), doc.hint_distrito or item.get("distrito"))
    else:
        place = (geo.locate(item.get("concelho"), item.get("distrito"))
                 or geo.locate(doc.hint_concelho, doc.hint_distrito)
                 or geo.find_in_text(doc.title + " " + (doc.text or "")))
        if place:
            doc.lat, doc.lon = place.lat, place.lon
    doc.concelho = (place.concelho if place else None) or item.get("concelho") or doc.hint_concelho
    doc.distrito = (place.distrito if place else None) or item.get("distrito") or doc.hint_distrito
    doc.status = "classified"
    doc.classified_at = utcnow()


def classify_pending(db: Session, llm, limit: int = 200) -> Dict[str, int]:
    """Classifica documentos pendentes (nunca reclassifica). Pára quando o orçamento diário acaba."""
    pending = list(db.scalars(
        select(Document).where(Document.status == "pending").order_by(Document.published_at.desc()).limit(limit)))
    stats = {"classified": 0, "failed": 0, "budget_stopped": 0}
    size = max(1, settings.classify_batch_size)
    for i in range(0, len(pending), size):
        batch = pending[i:i + size]
        system, user = build_prompts(db, batch)
        try:
            res = llm.complete_json(system, user, max_tokens=300 * len(batch) + 300)
        except BudgetExceeded:
            stats["budget_stopped"] = len(pending) - i
            break
        except LLMError as e:
            log.warning("Falha de classificação (lote mantém-se pendente): %s", e)
            stats["failed"] += len(batch)
            continue
        by_id = {int(it["id"]): it for it in res.get("items", []) if "id" in it}
        for d in batch:
            if d.id in by_id:
                apply_result(d, by_id[d.id])
                stats["classified"] += 1
            else:
                stats["failed"] += 1
        db.commit()
    return stats
