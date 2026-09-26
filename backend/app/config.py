"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration sourced from environment / .env file.

    Every field maps 1-to-1 to an environment variable of the same name
    (case-insensitive).  Pydantic-settings will read from the .env file
    located in the project root as a fallback.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://omniscient:password@localhost:5432/omniscient"

    # ── Redis ──────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Amazon SP-API ──────────────────────────────────────────────────
    SP_API_REFRESH_TOKEN: str = ""
    SP_API_CLIENT_ID: str = ""
    SP_API_CLIENT_SECRET: str = ""
    SP_API_MARKETPLACE_ID: str = "ATVPDKIKX0DER"
    SP_API_CREDENTIALS_ENCRYPTION_KEY: str = ""

    # ── Amazon Advertising API ─────────────────────────────────────────
    AMAZON_ADS_CLIENT_ID: str = ""
    AMAZON_ADS_CLIENT_SECRET: str = ""
    AMAZON_ADS_REFRESH_TOKEN: str = ""
    AMAZON_ADS_PROFILE_ID: str = ""

    # ── LLM providers ─────────────────────────────────────────────────
    LLM_PROVIDER: str = "qwen"
    LLM_MODEL: str = "qwen-max-latest"
    DASHSCOPE_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""

    # ── Proxy ──────────────────────────────────────────────────────────
    PROXY_PROVIDER: str = ""
    PROXY_HOST: str = ""
    PROXY_PORT: str = ""
    PROXY_USERNAME: str = ""
    PROXY_PASSWORD: str = ""

    # ── Alibaba / 1688 ─────────────────────────────────────────────────
    # NOTE: APP_KEY/SECRET are reserved for the official Alibaba Open API and
    # are NOT wired to anything yet — see docs/SUPPLIERS.md for the plan. Only
    # the 1688 login pair below is used today (by AlibabaLoginService, to warm
    # a scraping session). Do not assume supplier data works from these keys.
    ALIBABA_APP_KEY: str = ""
    ALIBABA_APP_SECRET: str = ""
    ALIBABA_1688_EMAIL: str = ""
    ALIBABA_1688_PASSWORD: str = ""

    # ── Amazon Login (optional, for authenticated review scraping) ────
    AMAZON_EMAIL: str = ""
    AMAZON_PASSWORD: str = ""

    # ── Freightos ──────────────────────────────────────────────────────
    FREIGHTOS_API_KEY: str = ""
    FREIGHTOS_API_SECRET: str = ""

    # ── Application ────────────────────────────────────────────────────
    APP_SECRET_KEY: str = "change-me-in-production"
    # Comma-separated list of origins allowed to call the API via CORS.
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # ── Scoring ────────────────────────────────────────────────────────
    # WHY off by default: the velocity is derived from Amazon's global ratings count,
    # which grows faster than written reviews; the 5 %/3 % trap thresholds were set
    # for reviews. Turn on after checking observed ratios on tracked niches (they are
    # stored in risk_flags.review_velocity_gap_ratio).
    REVIEW_VELOCITY_FILTER_ENABLED: bool = False

    # --- Licensing (open-core) ---
    # The key a customer was issued; empty = free tier. LICENSE_PUBLIC_KEY is only
    # needed by the maintainer when the public key was not embedded in source.
    LICENSE_KEY: str = ""
    LICENSE_PUBLIC_KEY: str = ""

    # ── Celery ─────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Logging ────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
