from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth
from .config import settings
from .connectors import CONNECTOR_CLASSES
from .db import get_db
from .llm import BudgetExceeded, LLMError, get_provider
from .models import Document, Feedback, Mission, MissionAlert, utcnow
from .services import app_settings, budget, missions as mission_svc
from .services.classify import CATEGORIES

router = APIRouter(prefix="/api")
protected = APIRouter(prefix="/api", dependencies=[Depends(auth.require_auth)])


# ---------- sessão ----------
class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    auth.login(request, response, body.password)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@router.get("/session")
def session(request: Request):
    return {"authenticated": auth.is_authenticated(request), "auth_required": auth.auth_enabled()}


# ---------- alertas (Radar) ----------
def doc_out(d: Document) -> Dict[str, Any]:
    fb = max(d.feedback, key=lambda f: f.created_at).value if d.feedback else None
    return {"id": d.id, "source": d.source, "url": d.url, "title": d.title, "category": d.category, "score": d.score,
            "summary": d.summary, "why": d.why, "entities": d.entities or {}, "concelho": d.concelho, "distrito": d.distrito,
            "lat": d.lat, "lon": d.lon, "published_at": d.published_at.isoformat(), "feedback": fb}


@protected.get("/alerts")
def alerts(category: Optional[str] = None, source: Optional[str] = None, days: int = Query(1, ge=1, le=365),
           date: Optional[dt.date] = None, include_hidden: bool = False, geo_only: bool = False,
           limit: int = Query(200, le=1000), db: Session = Depends(get_db)):
    q = select(Document).where(Document.status == "classified")
    if date:
        q = q.where(Document.published_at >= dt.datetime.combine(date, dt.time.min),
                    Document.published_at < dt.datetime.combine(date + dt.timedelta(days=1), dt.time.min))
    else:
        q = q.where(Document.published_at >= utcnow() - dt.timedelta(days=days))
    if not include_hidden:
        q = q.where(Document.score >= app_settings.threshold(db))
    if category:
        q = q.where(Document.category == category)
    if source:
        q = q.where(Document.source == source)
    if geo_only:
        q = q.where(Document.lat.is_not(None))
    q = q.order_by(Document.score.desc(), Document.published_at.desc()).limit(limit)
    return [doc_out(d) for d in db.scalars(q)]


class FeedbackIn(BaseModel):
    value: str = Field(pattern="^(useful|noise)$")


@protected.post("/alerts/{doc_id}/feedback")
def alert_feedback(doc_id: int, body: FeedbackIn, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404)
    db.query(Feedback).filter(Feedback.document_id == doc_id).delete()  # um voto por alerta (o último conta)
    db.add(Feedback(document_id=doc_id, value=body.value))
    db.commit()
    return {"ok": True, "value": body.value}


# ---------- missões ----------
class MissionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    instruction: str = Field(min_length=3)
    sources: List[str] = []
    frequency: str = Field("daily", pattern="^(daily|weekly)$")
    active: bool = True
    use_web: bool = False


class MissionPatch(BaseModel):
    name: Optional[str] = None
    instruction: Optional[str] = None
    sources: Optional[List[str]] = None
    frequency: Optional[str] = Field(None, pattern="^(daily|weekly)$")
    active: Optional[bool] = None
    use_web: Optional[bool] = None


def mission_out(m: Mission, n_alerts: int = 0) -> Dict[str, Any]:
    return {"id": m.id, "name": m.name, "instruction": m.instruction, "sources": m.sources or [], "frequency": m.frequency,
            "active": m.active, "use_web": m.use_web, "last_run_at": m.last_run_at.isoformat() if m.last_run_at else None,
            "alerts": n_alerts}


@protected.get("/missions")
def list_missions(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(MissionAlert.mission_id, func.count()).group_by(MissionAlert.mission_id)).all())
    return [mission_out(m, counts.get(m.id, 0)) for m in db.scalars(select(Mission).order_by(Mission.created_at.desc()))]


@protected.post("/missions")
def create_mission(body: MissionIn, db: Session = Depends(get_db)):
    m = Mission(**body.model_dump())
    db.add(m)
    db.commit()
    return mission_out(m)


@protected.patch("/missions/{mid}")
def patch_mission(mid: int, body: MissionPatch, db: Session = Depends(get_db)):
    m = db.get(Mission, mid)
    if not m:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    return mission_out(m)


@protected.delete("/missions/{mid}")
def delete_mission(mid: int, db: Session = Depends(get_db)):
    m = db.get(Mission, mid)
    if not m:
        raise HTTPException(404)
    db.delete(m)
    db.commit()
    return {"ok": True}


@protected.get("/missions/{mid}/alerts")
def mission_alerts(mid: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(MissionAlert).where(MissionAlert.mission_id == mid).order_by(MissionAlert.created_at.desc()).limit(200))
    out = []
    for a in rows:
        fb = max(a.feedback, key=lambda f: f.created_at).value if a.feedback else None
        out.append({"id": a.id, "title": a.title, "reason": a.reason, "summary": a.summary, "url": a.url, "source": a.source,
                    "created_at": a.created_at.isoformat(), "feedback": fb})
    return out


@protected.post("/mission-alerts/{aid}/feedback")
def mission_alert_feedback(aid: int, body: FeedbackIn, db: Session = Depends(get_db)):
    if not db.get(MissionAlert, aid):
        raise HTTPException(404)
    db.query(Feedback).filter(Feedback.mission_alert_id == aid).delete()
    db.add(Feedback(mission_alert_id=aid, value=body.value))
    db.commit()
    return {"ok": True, "value": body.value}


def _llm(db: Session):
    try:
        return budget.BudgetedLLM(db, get_provider())
    except LLMError as e:
        raise HTTPException(503, f"IA indisponível: {e}")


@protected.post("/missions/{mid}/run")
def run_mission_now(mid: int, db: Session = Depends(get_db)):
    m = db.get(Mission, mid)
    if not m:
        raise HTTPException(404)
    try:
        return {"created": mission_svc.run_mission(db, _llm(db), m)}
    except BudgetExceeded as e:
        raise HTTPException(429, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))


class SearchIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@protected.post("/search")
def search(body: SearchIn, db: Session = Depends(get_db)):
    try:
        return mission_svc.free_search(db, _llm(db), body.question)
    except BudgetExceeded as e:
        raise HTTPException(429, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))


# ---------- meta e definições ----------
def _sources(db: Session) -> List[Dict[str, Any]]:
    enabled = set(app_settings.enabled_sources(db))
    out = []
    for c in CONNECTOR_CLASSES:
        inst = c()
        ok, why = inst.availability()
        out.append({"name": inst.name, "label": inst.label, "available": ok, "note": why, "enabled": inst.name in enabled and ok})
    return out


@protected.get("/meta")
def meta(db: Session = Depends(get_db)):
    return {"categories": CATEGORIES, "sources": _sources(db), "threshold": app_settings.threshold(db)}


@protected.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return {"threshold": app_settings.threshold(db), "sources": _sources(db),
            "ai": {"provider": settings.llm_provider, "calls_today": budget.calls_today(db),
                   "max_calls_per_day": settings.max_llm_calls_per_day, "remaining": budget.remaining(db)},
            "documents": {"total": db.scalar(select(func.count(Document.id))) or 0,
                          "classified": db.scalar(select(func.count(Document.id)).where(Document.status == "classified")) or 0,
                          "pending": db.scalar(select(func.count(Document.id)).where(Document.status == "pending")) or 0,
                          "no_text": db.scalar(select(func.count(Document.id)).where(Document.status == "no_text")) or 0}}


class SettingsIn(BaseModel):
    threshold: Optional[int] = Field(None, ge=0, le=100)
    enabled_sources: Optional[List[str]] = None


@protected.put("/settings")
def put_settings(body: SettingsIn, db: Session = Depends(get_db)):
    if body.threshold is not None:
        app_settings.put(db, "relevance_threshold", body.threshold)
    if body.enabled_sources is not None:
        valid = {c.name for c in CONNECTOR_CLASSES}
        app_settings.put(db, "enabled_sources", [s for s in body.enabled_sources if s in valid])
    return get_settings(db)


@protected.get("/feedback/stats")
def feedback_stats(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    since = utcnow() - dt.timedelta(days=days)
    rows = db.scalars(select(Feedback).where(Feedback.created_at >= since)).all()
    per_day: Dict[str, Dict[str, int]] = {}
    for f in rows:
        d = per_day.setdefault(f.created_at.date().isoformat(), {"useful": 0, "noise": 0})
        d[f.value] += 1
    series = [{"day": k, "useful": v["useful"], "noise": v["noise"],
               "rate": round(100 * v["useful"] / (v["useful"] + v["noise"])) } for k, v in sorted(per_day.items())]
    useful = sum(1 for f in rows if f.value == "useful")
    total = len(rows)
    return {"total": total, "useful": useful, "noise": total - useful,
            "rate": round(100 * useful / total) if total else None, "series": series}
