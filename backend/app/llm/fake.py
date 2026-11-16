"""Provider determinístico, sem rede, para demo e testes. NÃO é IA: usa palavras-chave."""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from .base import LLMProvider

CATS = {
    "habitação": ["habita", "arrendamento", "renda", "alojamento", "urbaniza", "pdm", "imobili"],
    "saúde": ["saúde", "hospital", "sns", "urgência", "médico", "centro de saúde"],
    "autarquias": ["câmara", "município", "autarquia", "junta de freguesia", "presidente da câmara"],
    "justiça": ["tribunal", "juiz", "ministério público", "justiça", "acórdão", "polícia judiciária"],
    "economia": ["contrato", "milhões", "orçamento", "empresa", "adjudica", "preço"],
    "ambiente": ["incêndio", "ambiente", "aviso", "tempestade", "vento", "chuva", "seca", "agitação marítima"],
    "política": ["governo", "ministro", "nomeação", "nomeado", "parlamento", "assembleia", "secretário de estado"],
}


class FakeProvider(LLMProvider):
    name = "fake"
    supports_web_search = False

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> Dict[str, Any]:
        m = re.search(r"<docs>(.*?)</docs>", user, re.S)
        if m:
            return {"items": [self._classify(d) for d in json.loads(m.group(1))]}
        m = re.search(r"<candidates>(.*?)</candidates>", user, re.S)
        if m:
            q = re.search(r"<instruction>(.*?)</instruction>", user, re.S)
            words = {w for w in re.findall(r"\w{4,}", (q.group(1) if q else "").lower())}
            res = []
            for c in json.loads(m.group(1)):
                hay = (c["title"] + " " + c.get("text", "")).lower()
                hits = [w for w in words if w in hay]
                if hits:
                    res.append({"id": c["id"], "match": True, "reason": "Contém: " + ", ".join(sorted(hits)[:4]), "summary": c.get("summary") or c["title"]})
            return {"results": res}
        return {}

    @staticmethod
    def _classify(d: Dict[str, Any]) -> Dict[str, Any]:
        hay = (d["title"] + " " + d.get("text", "")).lower()
        cat, best = "outros", 0
        for k, kws in CATS.items():
            n = sum(1 for w in kws if w in hay)
            if n > best:
                cat, best = k, n
        score = min(95, 20 + best * 18 + (15 if re.search(r"\d+ milh", hay) else 0) + (15 if "vermelho" in hay or "laranja" in hay else 0))
        return {"id": d["id"], "score": score, "category": cat, "summary": (d.get("text") or d["title"])[:200],
                "why": "Classificação automática de demonstração (palavras-chave).", "people": [], "orgs": [],
                "concelho": d.get("hint_concelho"), "distrito": d.get("hint_distrito")}
