from __future__ import annotations

from typing import Any, Dict, List

from ..config import settings
from .base import LLMError, LLMProvider, extract_json


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    supports_web_search = True

    def __init__(self, api_key: str = "", model: str = ""):
        import anthropic  # import tardio: a app arranca sem a lib/chave em modo demo

        key = api_key or settings.anthropic_api_key
        if not key:
            raise LLMError("ANTHROPIC_API_KEY não definida")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or settings.anthropic_model

    def complete_json(self, system: str, user: str, max_tokens: int = 2000) -> Dict[str, Any]:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system + "\n\nResponde APENAS com um objeto JSON válido, sem texto à volta.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return extract_json(text)

    def web_search(self, query: str) -> List[Dict[str, str]]:
        # Ferramenta de pesquisa web do lado do servidor da Anthropic (por validar em produção; ver README).
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            messages=[{"role": "user", "content": f"Pesquisa na web notícias e fontes oficiais recentes sobre: {query}"}],
        )
        out: List[Dict[str, str]] = []
        for b in msg.content:
            if getattr(b, "type", "") == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
                for r in b.content:
                    url = getattr(r, "url", None)
                    if url:
                        out.append({"title": getattr(r, "title", "") or url, "url": url, "snippet": ""})
        return out[:10]
