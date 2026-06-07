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
    # Website live chat — fast model for low latency
    groq_chat_model: str = "llama-3.1-8b-instant"

    # Orchestrator
    orchestrator_poll_interval: int = 10
    orchestrator_batch_size: int = 5

    # Agent swarm pipeline (agent-to-agent chaining)
    # ek agent complete hone par next_agents ke liye naye tasks bante hain
    pipeline_enabled: bool = True
    pipeline_max_depth: int = 8

    # Auto-orchestrate: API server ke andar hi background scheduler chalega
    # taaki company "running mode" me rahe (manual tick ki zaroorat nahi)
    auto_orchestrate: bool = True

    # Autonomous growth loop: company khud market dhoondh ke prospecting shuru kare
    # (user ko har baar task dene ki zaroorat nahi)
    auto_growth: bool = False           # production me ON karein (RAILWAY var se)
    growth_interval_min: int = 360       # har kitne minute me ek naya scout cycle
    growth_markets: str = ""             # comma-separated, e.g. "SMB accounting India, dental clinics"
    growth_max_active_pipelines: int = 3 # itne se zyada active ho to naya cycle skip

    # Owner (Master) — Sayra delivery/requirement notifications iske liye banati hai
    owner_email: str = ""
    owner_name: str = "Master Ujjwal"

    # Payments (Razorpay) — paisa seedha aapke bank account me settle hota hai
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    payment_currency: str = "INR"

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
    def is_payments_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def growth_market_list(self) -> list[str]:
        raw = (self.growth_markets or "").strip()
        if not raw:
            return []
        return [m.strip() for m in raw.split(",") if m.strip()]

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
