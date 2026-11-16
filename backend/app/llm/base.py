"""Abstração de provider de LLM. Para acrescentar o Grok (xAI): criar xai_provider.py com uma
subclasse de LLMProvider e registá-la em factory.PROVIDERS. Nada mais precisa de mudar."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class LLMError(Exception):
    pass


class BudgetExceeded(LLMError):
    pass


class LLMProvider(ABC):
    name = "base"
    supports_web_search = False

    @abstractmethod
    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> Dict[str, Any]:
        """Pede uma resposta JSON (um objeto) ao modelo."""

    def web_search(self, query: str) -> List[Dict[str, str]]:
        """Pesquisa na web aberta, se o provider suportar. Devolve [{title,url,snippet}]."""
        raise NotImplementedError(f"{self.name} não suporta pesquisa web")


def extract_json(text: str) -> Dict[str, Any]:
    """Extrai o primeiro objeto JSON de um texto (tolera ```json ... ``` e texto à volta)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise LLMError("Resposta sem JSON")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError as e:
                    raise LLMError(f"JSON inválido: {e}")
    raise LLMError("JSON incompleto")
