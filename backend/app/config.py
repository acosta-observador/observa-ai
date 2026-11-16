"""Configuração via variáveis de ambiente (ver .env.example). Nunca guardar chaves no código."""
from __future__ import annotations

import os


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./observa_dev.db")
    # O Render fornece postgres:// ou postgresql://; usamos o driver psycopg (v3).
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    """Lê o ambiente no momento do acesso (facilita testes)."""

    @property
    def app_password(self) -> str:
        return os.getenv("APP_PASSWORD", "")

    @property
    def secret_key(self) -> str:
        return os.getenv("SECRET_KEY", "dev-insecure-change-me")

    @property
    def llm_provider(self) -> str:
        return os.getenv("LLM_PROVIDER", "anthropic").lower()

    @property
    def anthropic_api_key(self) -> str:
        return os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def anthropic_model(self) -> str:
        return os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")

    @property
    def enable_x(self) -> bool:
        return _bool("ENABLE_X", False)

    @property
    def x_bearer_token(self) -> str:
        return os.getenv("X_BEARER_TOKEN", "")

    @property
    def relevance_threshold(self) -> int:
        return int(os.getenv("RELEVANCE_THRESHOLD", "40"))

    @property
    def max_llm_calls_per_day(self) -> int:
        return int(os.getenv("MAX_LLM_CALLS_PER_DAY", "200"))

    @property
    def classify_batch_size(self) -> int:
        return int(os.getenv("CLASSIFY_BATCH_SIZE", "5"))

    @property
    def ipma_min_level(self) -> str:
        return os.getenv("IPMA_MIN_LEVEL", "orange")  # yellow | orange | red

    @property
    def fogos_min_men(self) -> int:
        return int(os.getenv("FOGOS_MIN_MEN", "15"))

    @property
    def cache_dir(self) -> str:
        return os.getenv("CACHE_DIR", ".cache")

    @property
    def user_agent(self) -> str:
        return os.getenv("HTTP_USER_AGENT", "ObservaAI-interno/0.1 (ferramenta interna do Observador)")

    @property
    def secure_cookies(self) -> bool:
        return _bool("SECURE_COOKIES", False)


settings = Settings()
