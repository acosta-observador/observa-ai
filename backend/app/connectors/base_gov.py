"""Portal BASE (contratação pública) — STUB documentado.

O que existe (verificado em 2026-11-16): o BASE/IMPIC publica no dados.gov.pt exportações COMPLETAS
(zip/xlsx/json, 2012-2026) de contratos, anúncios e modificações contratuais, e um dataset OCDS.
Não encontrámos uma API incremental estável e documentada, e as exportações completas são demasiado
grandes para um cron diário num serviço barato. Por isso NÃO se faz scraping do site (tem proteções)
e o conector devolve vazio até haver uma fonte incremental validada.

Para implementar: https://dados.gov.pt/datasets/ocds-portal-base-www-base-gov-pt
"""
from __future__ import annotations

import datetime as dt
from typing import List

from .base import RawDocument, SourceConnector


class BaseGovConnector(SourceConnector):
    name = "base"
    label = "Portal BASE — contratos (stub)"
    default_enabled = False

    def availability(self):
        return False, "stub: sem API incremental validada (ver README)"

    def fetch(self, since: dt.datetime) -> List[RawDocument]:
        return []
