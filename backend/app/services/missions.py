"""Searcher ativo: missões persistentes + pesquisa livre.

Estratégia (a mais simples que funciona bem): pré-filtro por palavras-chave/categoria sobre os documentos
já ingeridos (ILIKE, portátil Postgres/SQLite) + ranking e justificação por LLM sobre os candidatos.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import geo
from ..llm.base import BudgetExceeded, LLMError
from ..models import Document, Mission, MissionAlert, utcnow
from .classify import CATEGORIES

log = logging.getLogger(__name__)

STOP = set("""avisa avisa-me aviso algo sobre quando apareca aparecer onde para como quais quero entre desde todas todos
que uma uns umas dos das nos nas pelo pela pelos pelas este esta isto esse essa aquilo mais muito pouco ainda também
tambem tenha tenham seja sejam fazer feito ser estar estao está são sao com sem por num numa despachos despacho notícias
noticias noticia local locais caso casos nova novo novos novas procura procurar pesquisa pesquisar mostra mostrar encontra encontrar há tem""".split())

RANK_SYSTEM = """És o agente de pesquisa de uma redação. Recebes uma instrução do jornalista e documentos candidatos.
Para cada candidato que corresponda MESMO à instrução, devolve id, match=true, reason (porque corresponde, 1 frase) e
summary (2 frases). Ignora os que não correspondem. Não inventes documentos nem ids.
Formato: {"results":[{"id":..,"match":true,"reason":"..","summary":".."}]}"""

ANSWER_SYSTEM = """És o agente de pesquisa de uma redação. Responde à pergunta do jornalista em português, em poucas frases,
usando APENAS os documentos candidatos e citando-os por id entre parênteses retos, ex. [12]. Se não houver base, di-lo.
Devolve também os documentos relevantes. Formato:
{"answer":"..","results":[{"id":..,"match":true,"reason":"..","summary":".."}]}"""


def keywords(text: str) -> List[str]:
    words = re.findall(r"[\wçãõáéíóúâêôà]{4,}", text.lower())
    out: List[str] = []
    for w in words:
        if w in STOP or w in out:
            continue
        out.append(w)
        # radical simples para apanhar plurais/flexões (habitação -> habita)
        if len(w) > 6:
            out.append(w[:-2])
    return out[:14]


def candidates(db: Session, text: str, sources: Optional[List[str]] = None, since: Optional[dt.datetime] = None,
               limit: int = 30) -> List[Document]:
    kws = keywords(text)
    conds = []
    for k in kws:
        like = f"%{k}%"
        conds += [Document.title.ilike(like), Document.text.ilike(like), Document.summary.ilike(like)]
    for c in CATEGORIES:
        if c != "outros" and c in text.lower():
            conds.append(Document.category == c)
    if not conds:
        return []
    q = select(Document).where(or_(*conds), Document.status == "classified")
    if sources:
        q = q.where(Document.source.in_(sources))
    if since is not None:
        q = q.where(Document.fetched_at >= since)
    q = q.order_by(Document.score.desc(), Document.published_at.desc()).limit(limit)
    return list(db.scalars(q))


def _payload(docs: List[Document]) -> str:
    return json.dumps([{"id": d.id, "title": d.title, "source": d.source, "summary": d.summary,
                        "text": (d.text or "")[:500]} for d in docs], ensure_ascii=False)


def _rank(llm, system: str, instruction: str, docs: List[Document]) -> Dict[str, Any]:
    user = (f"<instruction>{instruction}</instruction>\n<question>{instruction}</question>\n"
            f"<candidates>{_payload(docs)}</candidates>")
    return llm.complete_json(system, user, max_tokens=1800)


def run_mission(db: Session, llm, mission: Mission) -> int:
    since = mission.last_run_at or (utcnow() - dt.timedelta(days=7))
    docs = candidates(db, mission.instruction + " " + mission.name, mission.sources or None, since)
    created = 0
    if docs:
        res = _rank(llm, RANK_SYSTEM, mission.instruction, docs)
        by_id = {d.id: d for d in docs}
        for r in res.get("results", []):
            d = by_id.get(int(r.get("id", -1)))
            if not d or not r.get("match", True):
                continue
            key = f"doc:{d.id}"
            if db.scalar(select(MissionAlert.id).where(MissionAlert.mission_id == mission.id, MissionAlert.dedupe_key == key)):
                continue
            db.add(MissionAlert(mission_id=mission.id, document_id=d.id, dedupe_key=key, title=d.title,
                                reason=r.get("reason") or "Corresponde à missão.", summary=r.get("summary") or d.summary or d.title,
                                url=d.url, source=d.source))
            created += 1
    if mission.use_web and llm.supports_web_search:
        try:
            for w in llm.web_search(mission.instruction):
                key = f"web:{w['url']}"
                if db.scalar(select(MissionAlert.id).where(MissionAlert.mission_id == mission.id, MissionAlert.dedupe_key == key)):
                    continue
                db.add(MissionAlert(mission_id=mission.id, dedupe_key=key, title=w.get("title") or w["url"],
                                    reason="Resultado da pesquisa na web aberta.", summary=w.get("snippet") or "",
                                    url=w["url"], source="web"))
                created += 1
        except (LLMError, NotImplementedError) as e:
            log.warning("Pesquisa web falhou: %s", e)
    mission.last_run_at = utcnow()
    db.commit()
    return created


def due(m: Mission, now: dt.datetime) -> bool:
    if not m.active:
        return False
    if m.last_run_at is None:
        return True
    gap = dt.timedelta(days=6, hours=12) if m.frequency == "weekly" else dt.timedelta(hours=20)
    return now - m.last_run_at >= gap


def run_missions(db: Session, llm, force: bool = False) -> Dict[str, Any]:
    now = utcnow()
    report: Dict[str, Any] = {}
    for m in db.scalars(select(Mission).where(Mission.active.is_(True))).all():
        if not force and not due(m, now):
            continue
        try:
            report[m.name] = run_mission(db, llm, m)
        except BudgetExceeded:
            report[m.name] = "limite diário de IA atingido"
            break
        except LLMError as e:
            report[m.name] = f"erro: {e}"
    return report


def free_search(db: Session, llm, question: str) -> Dict[str, Any]:
    docs = candidates(db, question, limit=25)
    if not docs:
        return {"answer": "Não encontrei documentos ingeridos que correspondam a esta pergunta.", "results": []}
    res = _rank(llm, ANSWER_SYSTEM, question, docs)
    by_id = {d.id: d for d in docs}
    results = []
    for r in res.get("results", []):
        d = by_id.get(int(r.get("id", -1)))
        if d and r.get("match", True):
            results.append({"id": d.id, "title": d.title, "url": d.url, "source": d.source, "reason": r.get("reason", ""),
                            "summary": r.get("summary") or d.summary, "concelho": d.concelho, "published_at": d.published_at.isoformat()})
    answer = res.get("answer") or (f"Encontrei {len(results)} documento(s) relevante(s)." if results else "Nenhum documento relevante.")
    return {"answer": answer, "results": results}
