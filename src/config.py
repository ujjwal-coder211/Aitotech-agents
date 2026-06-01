"""Centralized configuration loaded from environment variables (.env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Groq / LLM
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Orchestrator
    orchestrator_poll_interval: int = 10
    orchestrator_batch_size: int = 5

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Website (Aitotech) integration
    # comma-separated allowed origins, "*" = सब allow (dev के लिए)
    website_allowed_origins: str = "*"

    # ai-engine (self-hosted n8n) integration
    # agents यहाँ webhook भेजकर real actions (email/WhatsApp/CRM) करवाते हैं
    n8n_webhook_url: str = ""
    # shared secret: outbound header में जाता है + inbound webhook verify करता है
    n8n_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def is_llm_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def is_n8n_configured(self) -> bool:
        return bool(self.n8n_webhook_url)

    @property
    def cors_origins(self) -> list[str]:
        """website_allowed_origins string को list में बदलो।"""
        raw = (self.website_allowed_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
