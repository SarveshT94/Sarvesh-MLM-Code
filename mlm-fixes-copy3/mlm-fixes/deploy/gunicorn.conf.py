# deploy/gunicorn.conf.py
# ------------------------------------------------------------------
# Production WSGI server config for the Flask API.
#
# Topology for ~100,000 concurrent users:
#   Browser -> Nginx (TLS, static, rate-limit) -> Gunicorn(gevent)
#            -> PgBouncer (transaction pooling) -> PostgreSQL
#            -> Redis (shared cache / sessions)
#
# gevent gives thousands of concurrent sockets per worker with tiny memory
# cost. Rule of thumb: workers = (2 x CPU) + 1. DB concurrency is bounded by
# PgBouncer, NOT by gunicorn — keep each worker's psycopg2 pool SMALL.
# ------------------------------------------------------------------
import multiprocessing

# Network bind (Nginx proxies to this).
bind = "0.0.0.0:8000"

# Async workers — one worker handles thousands of concurrent greenlets.
worker_class = "gevent"
workers = int(__import__("os").environ.get("WEB_CONCURRENCY",
                                           multiprocessing.cpu_count() * 2 + 1))
worker_connections = int(__import__("os").environ.get("GUNICORN_CONNECTIONS", 1000))

# Recycle workers periodically to bound memory growth.
max_requests = 2000
max_requests_jitter = 200
timeout = 30
graceful_timeout = 30
keepalive = 5

# Do NOT run the Flask debugger / reloader under gunicorn.
reload = False

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security: don't leak server header
proc_name = "rktrendz-api"
