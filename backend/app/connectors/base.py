from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class RawDocument:
    source: str
    external_id: str
    url: str
    title: str
    text: str = ""
    doc_type: Optional[str] = None
    published_at: Optional[dt.datetime] = None
    hint_lat: Optional[float] = None
    hint_lon: Optional[float] = None
    hint_distrito: Optional[str] = None
    hint_concelho: Optional[str] = None


class SourceConnector(ABC):
    """Interface de um conector. Cada conector vive no seu ficheiro e é registado em connectors/__init__.py."""

    name: str = ""
    label: str = ""
    default_enabled: bool = True
    #: Conectores sem texto (só título/link) não são enviados ao LLM (evita gastar chamadas em ruído).
    has_text: bool = True

    def availability(self) -> Tuple[bool, str]:
        """(disponível, motivo). Ex.: stub ou token em falta."""
        return True, "ok"

    @abstractmethod
    def fetch(self, since: dt.datetime) -> List[RawDocument]:
        """Devolve documentos novos/alterados desde `since` (UTC naive)."""
