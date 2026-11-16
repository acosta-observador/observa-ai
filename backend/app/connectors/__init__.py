from __future__ import annotations

from typing import Dict

from .base import RawDocument, SourceConnector
from .base_gov import BaseGovConnector
from .dre import DREConnector
from .fogos import FogosConnector
from .ipma import IPMAConnector
from .x_twitter import XConnector

# Ordem de prioridade
CONNECTOR_CLASSES = [DREConnector, BaseGovConnector, IPMAConnector, FogosConnector, XConnector]


def registry() -> Dict[str, SourceConnector]:
    return {c.name: c() for c in CONNECTOR_CLASSES}


__all__ = ["RawDocument", "SourceConnector", "registry", "CONNECTOR_CLASSES"]
