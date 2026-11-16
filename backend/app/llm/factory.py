from __future__ import annotations

from typing import Callable, Dict

from ..config import settings
from .base import LLMError, LLMProvider


def _anthropic() -> LLMProvider:
    from .anthropic_provider import AnthropicProvider
    return AnthropicProvider()


def _fake() -> LLMProvider:
    from .fake import FakeProvider
    return FakeProvider()


# Para acrescentar o Grok: PROVIDERS["xai"] = _xai
PROVIDERS: Dict[str, Callable[[], LLMProvider]] = {"anthropic": _anthropic, "fake": _fake}


def get_provider() -> LLMProvider:
    name = settings.llm_provider
    if name not in PROVIDERS:
        raise LLMError(f"LLM_PROVIDER desconhecido: {name} (disponíveis: {', '.join(PROVIDERS)})")
    return PROVIDERS[name]()
