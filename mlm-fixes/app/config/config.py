"""
app/config/config.py  —  REWRITE (drop-in replacement)

Enterprise configuration:
  * Fail-fast validation of required env vars
  * Centralised DB connection-pool tuning
  * Redis URL for the shared cache (works across ALL gunicorn workers)
  * Per-environment security toggles

Reads environment from a .env file (development) or real environment
variables (production / Docker / Kubernetes).
"""
import os
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _as_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _as_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # ---- Environment ----
    ENV: str = os.getenv("ENV", "production")
    DEBUG: bool = _as_bool("DEBUG", False)
    TESTING: bool = _as_bool("TESTING", False)

    # ---- Database ----
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = _as_int("DB_PORT", 5432)
    DB_NAME: str = os.getenv("DB_NAME", "rk_trendz_mlm")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Pool. With PgBouncer in transaction mode in front of Postgres, each
    # gunicorn/gevent worker can keep a small local pool while PgBouncer
    # multiplexes to a bounded set of real server connections.
    DB_POOL_MIN: int = _as_int("DB_POOL_MIN", 2)
    DB_POOL_MAX: int = _as_int("DB_POOL_MAX", 20)
    DB_STATEMENT_TIMEOUT_MS: int = _as_int("DB_STATEMENT_TIMEOUT_MS", 5000)

    # ---- Security ----
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    SESSION_COOKIE_SECURE: bool = _as_bool("SESSION_COOKIE_SECURE", True)

    # ---- Cache (Redis). Falls back to in-process cache only in local dev ----
    REDIS_URL: str = os.getenv("REDIS_URL", "")   # e.g. redis://127.0.0.1:6379/0
    CACHE_DEFAULT_TIMEOUT: int = _as_int("CACHE_DEFAULT_TIMEOUT", 300)

    # ---- Payments (Razorpay) ----
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", os.getenv("PAYMENT_GATEWAY_SECRET", ""))

    # ---- Rate limiting ----
    RATELIMIT_DEFAULT: str = os.getenv("RATELIMIT_DEFAULT", "300 per minute")

    # ---- CORS (comma separated list of allowed front-end origins) ----
    CORS_ORIGINS: list = [
        o.strip() for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",") if o.strip()
    ]

    @classmethod
    def validate(cls) -> None:
        missing = [
            f for f in ("DB_NAME", "SECRET_KEY", "JWT_SECRET")
            if not getattr(cls, f)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"Set them in your environment or .env file."
            )
        # Production must never run with an insecure/short secret.
        if cls.ENV == "production" and len(cls.SECRET_KEY) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters in production.")

    @classmethod
    def get_db_url(cls) -> str:
        password = quote_plus(cls.DB_PASSWORD or "")
        return (
            f"postgresql://{cls.DB_USER}:{password}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        )


@lru_cache(maxsize=1)
def get_config() -> type[Config]:
    Config.validate()
    return Config
