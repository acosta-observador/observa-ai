from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Document(Base):
    """Documento bruto ingerido + resultado da classificação."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_doc_source_ext"), Index("ix_doc_pub", "published_at"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(512))
    text: Mapped[str] = mapped_column(Text, default="")
    doc_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    published_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    # Pistas de localização dadas pelo conector (ex.: coordenadas do fogos.pt, distrito do IPMA)
    hint_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hint_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hint_distrito: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hint_concelho: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # pending | classified | no_text | skipped
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entities: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    concelho: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    distrito: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    classified_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)

    feedback: Mapped[list["Feedback"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    instruction: Mapped[str] = mapped_column(Text)
    sources: Mapped[Any] = mapped_column(JSON, default=list)  # lista vazia = todas
    frequency: Mapped[str] = mapped_column(String(16), default="daily")  # daily | weekly
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    use_web: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_run_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)

    alerts: Mapped[list["MissionAlert"]] = relationship(back_populates="mission", cascade="all, delete-orphan")


class MissionAlert(Base):
    __tablename__ = "mission_alerts"
    __table_args__ = (UniqueConstraint("mission_id", "dedupe_key", name="uq_alert_mission_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(512))
    reason: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1024))
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    mission: Mapped[Mission] = relationship(back_populates="alerts")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="mission_alert", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    mission_alert_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mission_alerts.id", ondelete="CASCADE"), nullable=True, index=True)
    value: Mapped[str] = mapped_column(String(8))  # useful | noise
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)

    document: Mapped[Optional[Document]] = relationship(back_populates="feedback")
    mission_alert: Mapped[Optional[MissionAlert]] = relationship(back_populates="feedback")


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    day: Mapped[dt.date] = mapped_column(primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
