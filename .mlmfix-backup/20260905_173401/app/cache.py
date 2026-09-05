"""
app/cache.py  —  REWRITE (drop-in replacement)

Why this changed
----------------
The old file used Flask-Caching's **SimpleCache**, which:
  * is per-process -> with 9 gunicorn workers you get 9 separate caches that
    never agree, and each caches a *different* copy of heavy data;
  * stores everything in each worker's RAM -> memory blows up under load;
  * is explicitly documented as "not thread safe / not for production".

At 1 lakh concurrent users you MUST have a single shared cache. We use Redis
when REDIS_URL is set (production), and automatically fall back to a
filesystem/simple cache only for local development so the app still boots.
"""
import os
import logging

from flask_caching import Cache

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "").strip()

if REDIS_URL:
    # RedisCache is shared across every worker and every app server.
    _config = {
        "CACHE_TYPE": "RedisCache",
        "CACHE_REDIS_URL": REDIS_URL,
        "CACHE_DEFAULT_TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", 300)),
        # Fail fast / degrade instead of hanging if Redis blips.
        "CACHE_REDIS_CONNECT_TIMEOUT": 1,
        "CACHE_REDIS_SOCKET_TIMEOUT": 1,
        "CACHE_KEY_PREFIX": "rktrendz:",
    }
    logger.info("Cache backend: Redis (%s)", REDIS_URL.split("@")[-1])
else:
    # Local development only.
    _config = {
        "CACHE_TYPE": "SimpleCache",
        "CACHE_DEFAULT_TIMEOUT": 300,
    }
    logger.warning(
        "REDIS_URL not set -> using in-process SimpleCache. "
        "This is fine for local dev but MUST be Redis in production."
    )

cache = Cache(config=_config)


def cache_key(*parts) -> str:
    """Helper to build stable, collision-free cache keys."""
    return ":".join(str(p) for p in parts)
