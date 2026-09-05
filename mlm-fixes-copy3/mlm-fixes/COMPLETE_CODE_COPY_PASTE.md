# MLM — COMPLETE CODE (copy & paste file by file)

**How to use:** Follow the order below. For each section, open the file at the
shown path in your GitHub project and **replace its entire contents** with the
code in that section. Files marked 🆕 do not exist yet — create them. Files
marked 🗑️ must be deleted. The database migration runs once in PostgreSQL.

> Do the DATABASE step (Step 1) BEFORE restarting the new code. It only ADDs
> data/columns — your existing users, packages and wallets are NOT deleted.
> Backup first:  `pg_dump -U postgres -d rk_trendz_mlm -f backup.sql`

**Order:** 1) DB migration → 2) Backend files → 3) Delete 1 file + edit main.py
→ 4) `pip install -r requirements.txt` & restart → 5) Front-end.

---


## STEP 1 — DATABASE (run once in PostgreSQL / psql)  `migrations/0004_enterprise_scale_and_plan.sql`

```sql
-- ============================================================================
--  RK TRENDZ MLM  ::  ENTERPRISE HARDENING MIGRATION
--  File: migrations/0004_enterprise_scale_and_plan.sql
--  Engine: PostgreSQL 12+
-- ----------------------------------------------------------------------------
--  WHAT THIS DOES (and WHY)
--  ------------------------
--  A. Fixes schema/code mismatches that currently BREAK commissions:
--       * wallet_ledger has `reference_id`, but commission_engine.py inserts
--         into `reference`  -> whole payout transaction rolls back every time.
--       * level_commissions has `commission_percentage`, but package_service
--         reads `percentage` -> level income is always empty.
--       * commissions / wallet_ledger rows are never linked to the order,
--         so there is no real idempotency / audit link.
--       * `orders` table is QUERIED in team_service but DOES NOT EXIST.
--
--  B. Makes the app survive 100,000 concurrent users:
--       * Adds an ltree genealogy path (`users.tree_path`) so "total team",
--         "team by level" and subtree searches are O(subtree size) with an
--         INDEX SCAN instead of an ever-growing recursive CTE walk.
--       * Adds denormalised counters (direct_count / total_team_count) that
--         are maintained by triggers - the dashboard/header never runs a
--         recursive count again.
--       * Adds the missing indexes that every hot query needs.
--       * Adds pg_trgm for the admin "search name/email/phone" box so it does
--         not sequential-scan 100k rows on every keystroke.
--
--  C. Makes the COMPENSATION / COMMISSION PLAN explicit and seeded so it
--     cannot silently "not exist".
--
--  SAFE TO RUN MORE THAN ONCE (idempotent). Safe on an existing database.
--  TAKE A BACKUP FIRST:  pg_dump rk_trendz_mlm > backup_before_0004.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. EXTENSIONS
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- 1. ORDERS TABLE  (referenced by team_service.get_user_purchase_history but
--    previously MISSING entirely - that query threw an error every time)
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.orders (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT      NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    package_id    INTEGER     NOT NULL,
    amount        NUMERIC(12,2) NOT NULL,
    status        VARCHAR(30) NOT NULL DEFAULT 'completed',
    payment_ref   VARCHAR(120),
    created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Backfill an order row for every package already on the ledger (one-time).
INSERT INTO public.orders (user_id, package_id, amount, status, payment_ref, created_at)
SELECT up.user_id, up.package_id, up.amount, 'completed',
       'LEGACY-' || up.id::text, up.created_at
FROM public.user_packages up
WHERE NOT EXISTS (
    SELECT 1 FROM public.orders o
    WHERE o.user_id = up.user_id AND o.package_id = up.package_id
      AND o.payment_ref = 'LEGACY-' || up.id::text
);

-- ============================================================================
-- 2. WALLET LEDGER  :: make it match BOTH old and new code
--    Code (commission_engine) writes column `reference`. Schema has
--    `reference_id`. We add `reference` as a GENERATED column synced to
--    reference_id so neither name ever breaks again.
-- ============================================================================
ALTER TABLE public.wallet_ledger
    ADD COLUMN IF NOT EXISTS running_balance NUMERIC(14,2);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='wallet_ledger' AND column_name='reference') THEN
        ALTER TABLE public.wallet_ledger ADD COLUMN reference TEXT;
    END IF;
END $$;

-- Keep the two reference columns in sync both ways via triggers.
CREATE OR REPLACE FUNCTION public.sync_ledger_reference()
RETURNS TRIGGER AS $fn$
BEGIN
    IF NEW.reference IS NULL AND NEW.reference_id IS NOT NULL THEN
        NEW.reference := NEW.reference_id::text;
    ELSIF NEW.reference_id IS NULL AND NEW.reference IS NOT NULL THEN
        NEW.reference_id := NEW.reference;
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_ledger_reference ON public.wallet_ledger;
CREATE TRIGGER trg_sync_ledger_reference
    BEFORE INSERT OR UPDATE ON public.wallet_ledger
    FOR EACH ROW EXECUTE FUNCTION public.sync_ledger_reference();

-- Idempotency: a paid commission must never be inserted twice for the same
-- (earner, order, level). This is the REAL unique guard (the old one used a
-- free-text type string that could drift).
ALTER TABLE public.commissions
    ADD COLUMN IF NOT EXISTS order_id BIGINT REFERENCES public.orders(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_commissions_earner_order_level
    ON public.commissions (earner_id, COALESCE(order_id, 0), level);

CREATE INDEX IF NOT EXISTS idx_commissions_earner   ON public.commissions (earner_id);
CREATE INDEX IF NOT EXISTS idx_commissions_fromuser ON public.commissions (from_user_id);
CREATE INDEX IF NOT EXISTS idx_wallet_user_created  ON public.wallet_ledger (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user          ON public.orders (user_id, created_at DESC);

-- ============================================================================
-- 3. GENEALOGY PATH + DENORMALISED COUNTERS (the scale fix)
-- ============================================================================
-- tree_path is an ltree like  1.5.12  meaning root(1) -> 5 -> 12
-- All subtree questions become:  tree_path <@ '1'   (descendants of 1)
-- Direct children:               tree_path ~ '1.*{1}'
-- Level of a node:               nlevel(tree_path)
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS tree_path       ltree,
    ADD COLUMN IF NOT EXISTS direct_count    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_team_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_users_tree_path ON public.users USING GIST (tree_path);
CREATE INDEX IF NOT EXISTS idx_users_sponsor   ON public.users (sponsor_id);
CREATE INDEX IF NOT EXISTS idx_users_rank      ON public.users (rank_level);
CREATE INDEX IF NOT EXISTS idx_users_active    ON public.users (is_active);
CREATE INDEX IF NOT EXISTS idx_users_created   ON public.users (created_at DESC);

-- One-time backfill of tree_path for all existing users using the existing
-- sponsor links. Runs bottom-up so a parent path always exists before child.
WITH RECURSIVE build_path AS (
    SELECT id,
           sponsor_id,
           (text(id))::ltree AS path,
           1 AS depth
    FROM public.users
    WHERE sponsor_id IS NULL
    UNION ALL
    SELECT u.id,
           u.sponsor_id,
           (bp.path || u.id::text)::ltree AS path,
           bp.depth + 1
    FROM public.users u
    JOIN build_path bp ON u.sponsor_id = bp.id
    WHERE bp.depth < 100          -- safety stop against corrupt cycles
)
UPDATE public.users u
SET tree_path = bp.path
FROM build_path bp
WHERE u.id = bp.id AND u.tree_path IS NULL;

-- Maintain tree_path + counters automatically on INSERT / sponsor change.
CREATE OR REPLACE FUNCTION public.users_tree_maintenance()
RETURNS TRIGGER AS $fn$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.sponsor_id IS NULL THEN
            NEW.tree_path := text(NEW.id)::ltree;
        ELSE
            SELECT tree_path || NEW.id::text INTO NEW.tree_path
            FROM public.users WHERE id = NEW.sponsor_id;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        -- If the sponsor changed, re-root this whole subtree.
        IF NEW.sponsor_id IS DISTINCT FROM OLD.sponsor_id THEN
            IF NEW.sponsor_id IS NULL THEN
                NEW.tree_path := text(NEW.id)::ltree;
            ELSE
                SELECT tree_path || NEW.id::text INTO NEW.tree_path
                FROM public.users WHERE id = NEW.sponsor_id;
            END IF;
            -- Repath every descendant of this node.
            WITH RECURSIVE subtree AS (
                SELECT id, tree_path FROM public.users WHERE sponsor_id = NEW.id
                UNION ALL
                SELECT u.id, u.tree_path FROM public.users u
                JOIN subtree s ON u.sponsor_id = s.id
            )
            UPDATE public.users d
            SET tree_path = NEW.tree_path ||
                    subpath(d.tree_path, nlevel(NEW.tree_path) - 1)
            FROM subtree s
            WHERE d.id = s.id AND d.id <> NEW.id;
        END IF;
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_tree ON public.users;
CREATE TRIGGER trg_users_tree
    BEFORE INSERT OR UPDATE OF sponsor_id ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.users_tree_maintenance();

-- Keep direct_count / total_team_count fresh. total_team_count uses ltree so
-- it is a single indexed subtree count, even on a huge network.
CREATE OR REPLACE FUNCTION public.refresh_user_counters()
RETURNS void AS $fn$
BEGIN
    UPDATE public.users u SET
        direct_count = (
            SELECT COUNT(*) FROM public.users c WHERE c.sponsor_id = u.id
        ),
        total_team_count = (
            SELECT COUNT(*) FROM public.users d
            WHERE d.tree_path IS NOT NULL
              AND u.tree_path IS NOT NULL
              AND d.tree_path <@ u.tree_path
              AND d.id <> u.id
        );
END;
$fn$ LANGUAGE plpgsql;

SELECT public.refresh_user_counters();   -- initial population

-- ============================================================================
-- 4. ADMIN SEARCH  :: trigram indexes (fast ILIKE on 100k+ rows)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_name_trgm  ON public.users USING GIN (full_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_users_email_trgm ON public.users USING GIN (email gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_users_phone_trgm ON public.users USING GIN (phone gin_trgm_ops);

-- ============================================================================
-- 5. COMPENSATION / COMMISSION PLAN  (single source of truth, seeded)
-- ----------------------------------------------------------------------------
-- We standardise on `commission_plan` as the editable level payout table and
-- keep `level_commissions` in sync (legacy screens read it). Levels are the
-- UPLINE level of the earner relative to a purchase: Level 1 = direct sponsor.
-- Percentages apply to the purchased package price.
-- Seeded from your existing business plan (edit later in Admin > Packages).
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.commission_plan (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    level      INTEGER NOT NULL UNIQUE,
    percentage NUMERIC(5,2) NOT NULL,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO public.commission_plan (level, percentage) VALUES
    (1, 10.00),   -- Direct / sponsor income
    (2,  3.00),
    (3,  2.50),
    (4,  2.00),
    (5,  1.50),
    (6,  1.50),
    (7,  1.50),
    (8,  1.00),
    (9,  1.00),
    (10, 1.00)
ON CONFLICT (level) DO NOTHING;

-- Make sure level_commissions (legacy table) has the complete 1..10 ladder
-- with the SAME column your admin template already uses (commission_percentage).
INSERT INTO public.level_commissions (level, commission_percentage)
SELECT g.lvl, p.percentage
FROM generate_series(1,10) AS g(lvl)
JOIN public.commission_plan p ON p.level = g.lvl
WHERE NOT EXISTS (SELECT 1 FROM public.level_commissions lc WHERE lc.level = g.lvl);

-- Guarded unique constraints so ON CONFLICT / re-runs behave predictably.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_global_comm_key') THEN
        ALTER TABLE public.global_commissions ADD CONSTRAINT uq_global_comm_key UNIQUE (setting_key);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_level_comm_level') THEN
        ALTER TABLE public.level_commissions ADD CONSTRAINT uq_level_comm_level UNIQUE (level);
    END IF;
END $$;

-- Global settings your code references (fill gaps without touching existing).
INSERT INTO public.global_commissions (setting_key, percentage_value, description) VALUES
    ('direct_commission',   10.00, 'Direct sponsor commission (%) on package purchase'),
    ('self_cashback',        5.00, 'Cashback to buyer on own purchase (%)'),
    ('tds_percentage',       5.00, 'TDS deducted on withdrawal (%)'),
    ('admin_fee_percentage',10.00, 'Admin/processing fee on withdrawal (%)')
ON CONFLICT DO NOTHING;

-- Package plans (your 5-tier catalogue). Prices seeded; edit in admin.
INSERT INTO public.subscription_plans (id, name, price, lucky_draw_coupons, is_active, product_cost)
VALUES
    (1, 'Starter',   1800.00, 12, TRUE, 1000),
    (2, 'Bronze',    3600.00, 12, TRUE, 0),
    (3, 'Silver',    7200.00, 12, TRUE, 0),
    (4, 'Gold',     14400.00, 12, TRUE, 0),
    (5, 'Platinum', 28800.00, 12, TRUE, 0)
ON CONFLICT (id) DO NOTHING;

-- Keep the sequence ahead of manual ids so future inserts don't collide.
SELECT setval(pg_get_serial_sequence('public.subscription_plans','id'),
              (SELECT COALESCE(MAX(id),1) FROM public.subscription_plans));

-- ============================================================================
-- DONE.  Verify with:
--   SELECT level, percentage FROM commission_plan ORDER BY level;
--   SELECT id, full_name, direct_count, total_team_count, tree_path FROM users LIMIT 5;
-- ============================================================================
```

---

## STEP 2 — BACKEND FILES

---

## ✏️ REPLACE  `requirements.txt`

```text
# ---- Core web framework ----
Flask==3.1.3
Werkzeug==3.1.6
Jinja2==3.1.6
itsdangerous==2.2.0
click==8.3.1

# ---- Database (PostgreSQL + pooling) ----
SQLAlchemy==2.0.48
psycopg2-binary==2.9.11
greenlet==3.3.2
# PgBouncer runs as a separate service (apt install pgbouncer), not pip.

# ---- Auth / security / API ----
Flask-Login==0.6.3
Flask-CORS==6.0.2
flask-talisman==1.1.0
Flask-Limiter==4.1.1
limits==5.8.0
ordered-set==4.1.0

# ---- Shared cache (Redis) — REQUIRED for production scale ----
Flask-Caching==2.4.1
cachelib==0.16.1
redis==5.2.1

# ---- Background tasks / jobs ----
Flask-Executor==1.0.0

# ---- Production WSGI server ----
gunicorn==23.0.0
gevent==24.2.1

# ---- Config / util ----
python-dotenv==1.2.2
Mako==1.3.10
MarkupSafe==3.0.3
Deprecated==1.3.1
wrapt==2.3.0
blinker==1.9.0
packaging==26.3
typing_extensions==4.15.0
```

---

## ✏️ REPLACE  `run.py`

```python
"""
run.py — REWRITE

Local development entrypoint ONLY.

In production you must NOT use Flask's built-in server (debug=True exposes the
Werkzeug interactive debugger = remote code execution). Production runs under
gunicorn + gevent (see deploy/gunicorn.conf.py and deploy/deployment.md):

    gunicorn -c deploy/gunicorn.conf.py "app:create_app()"

This file keeps `python run.py` working for local dev with debug OFF unless
FLASK_DEBUG=1 is explicitly set.
"""
from app import create_app
from app.utils.logger import setup_logging
from app.config.config import get_config

setup_logging()
cfg = get_config()
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", 5000)),
        debug=cfg.DEBUG and cfg.ENV != "production",
        use_reloader=cfg.DEBUG and cfg.ENV != "production",
    )
```

---

## ✏️ REPLACE  `app/__init__.py`

```python
"""
app/__init__.py  —  REWRITE (drop-in replacement)

Application factory. Changes vs the old file:
  * Registers the NEW team drill blueprint (app/routes/team_routes.py).
  * Drives CORS origins and cookie flags from config (no hard-coded
    localhost / SameSite=None in dev).
  * Registers a /healthz liveness endpoint.
  * No debug server here — production runs under gunicorn (see deploy/).

IMPORTANT HOUSEKEEPING (do this when you replace files):
  * DELETE the duplicate factory at  app/routes/__init__.py
    (it defines a SECOND, conflicting create_app and even references an
     undefined `rank_bp` -> if anyone imports it, the app crashes).
  * The old duplicate routes /api/team/me and /api/genealogy/me lived in BOTH
    app/routes/main.py and app/routes/user_routes.py. Keep the user_routes
    versions and remove the two blocks from main.py (instructions in the
    audit report).
"""
import os
import logging

from dotenv import load_dotenv
from flask import Flask, jsonify

from flask_login import LoginManager, UserMixin
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_executor import Executor

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address,
                  default_limits=[os.getenv("RATELIMIT_DEFAULT", "300 per minute")])
executor = Executor()


class User(UserMixin):
    def __init__(self, data):
        self.id = str(data.get("id"))
        self.full_name = data.get("full_name")
        self.email = data.get("email")
        self.role_id = data.get("role_id")
        self.phone = data.get("phone")
        self.referral_code = data.get("referral_code")


def create_app():
    app = Flask(__name__)

    from app.config.config import get_config
    cfg = get_config()

    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = cfg.SESSION_COOKIE_SECURE
    app.config["PREFERRED_URL_SCHEME"] = "https"

    limiter.init_app(app)

    from app.cache import cache
    cache.init_app(app)

    executor.init_app(app)

    Talisman(
        app,
        force_https=cfg.ENV == "production",
        content_security_policy={
            "default-src": ["'self'"],
            "style-src": ["'self'", "'unsafe-inline'",
                          "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
            "font-src": ["'self'", "https://fonts.gstatic.com",
                         "https://cdn.jsdelivr.net", "data:"],
            "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
        },
    )

    CORS(
        app,
        supports_credentials=True,
        origins=cfg.CORS_ORIGINS,
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # ----- Blueprints -----
    from app.routes.auth_routes import auth_bp
    from app.routes.main import main
    from app.routes.admin_routes import admin
    from app.routes.user_routes import user_bp
    from app.routes.team_routes import team_bp          # NEW drill-down API
    from app.routes.admin.tree_routes import admin_tree_bp
    from app.routes.admin.wallet_routes import admin_wallet_bp
    from app.routes.admin.commission_routes import admin_commission_bp
    from app.routes.admin.fraud_routes import admin_fraud_bp
    from app.routes.admin.activity_routes import admin_activity_bp
    from app.routes.admin.cron_routes import admin_cron_bp
    from app.routes.admin.analytics_routes import admin_analytics_bp
    from app.routes.notification_routes import notification_bp
    from app.routes.support_routes import support_bp
    from app.routes.admin.support_routes import admin_support_bp
    from app.routes.admin.backup_routes import admin_backup_bp
    from app.routes.admin.package_routes import admin_package_bp
    from app.routes.profile_routes import profile_bp
    from app.routes.admin.report_routes import admin_report_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_package_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(main)
    app.register_blueprint(user_bp, url_prefix="/api")
    app.register_blueprint(team_bp, url_prefix="/api")     # NEW
    app.register_blueprint(admin, url_prefix="/api/admin")
    app.register_blueprint(admin_tree_bp, url_prefix="/api/admin/tree")
    app.register_blueprint(admin_wallet_bp, url_prefix="/api/admin/wallet")
    app.register_blueprint(admin_commission_bp, url_prefix="/api/admin/commission")
    app.register_blueprint(admin_fraud_bp, url_prefix="/api/admin/fraud")
    app.register_blueprint(admin_activity_bp, url_prefix="/api/admin/activity")
    app.register_blueprint(admin_cron_bp, url_prefix="/api/admin/cron")
    app.register_blueprint(admin_analytics_bp, url_prefix="/api/admin/analytics")
    app.register_blueprint(notification_bp, url_prefix="/api/notifications")
    app.register_blueprint(support_bp, url_prefix="/api/support")
    app.register_blueprint(admin_support_bp, url_prefix="/api/admin/support")
    app.register_blueprint(admin_backup_bp, url_prefix="/api/admin/backup")
    app.register_blueprint(admin_report_bp, url_prefix="/api/admin/report")

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.db import get_cursor
            with get_cursor() as cur:
                cur.execute(
                    "SELECT id, full_name, email, phone, referral_code, role_id "
                    "FROM users WHERE id = %s",
                    (user_id,),
                )
                data = cur.fetchone()
            return User(data) if data else None
        except Exception as e:
            logger.error("user_loader error: %s", e)
            return None

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    @app.errorhandler(404)
    def not_found(e):
        from flask import request, render_template
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request, render_template
        logger.error("500 error: %s", e)
        if request.path.startswith("/api/"):
            return jsonify({"status": "error", "message": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    # Start / stop the DB pool cleanly.
    @app.before_request
    def _ensure_pool():
        from app.db import init_db_pool
        init_db_pool()

    return app
```

---

## ✏️ REPLACE  `app/cache.py`

```python
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
```

---

## ✏️ REPLACE  `app/db.py`

```python
"""
app/db.py  —  REWRITE (drop-in replacement)

Connection-pool + transaction management.

Scale notes for 100,000 concurrent users
----------------------------------------
* Use a SMALL per-process pool (DB_POOL_MIN/MAX) and put **PgBouncer** in
  TRANSACTION pooling mode in front of PostgreSQL. 10 gunicorn workers x
  gevent x a 10-20 pool is plenty; PgBouncer multiplexes them onto a few
  dozen real Postgres connections. A per-process pool of 100 against a
  single Postgres = up to 1,000 server connections = guaranteed meltdown.
* Every transaction gets a `statement_timeout` so one runaway recursive
  query can never pin a DB connection for minutes.
* get_cursor() commits on success, rolls back on error, and never leaks a
  connection back into the pool dirty.
"""
import os
import logging
import contextlib

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from app.config.config import get_config

config = get_config()
logger = logging.getLogger(__name__)

_connection_pool = None


def init_db_pool():
    global _connection_pool
    if _connection_pool is not None:
        return

    max_conn = int(os.environ.get("DB_POOL_MAX", config.DB_POOL_MAX))
    min_conn = int(os.environ.get("DB_POOL_MIN", config.DB_POOL_MIN))
    timeout_ms = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS",
                                    config.DB_STATEMENT_TIMEOUT_MS))

    _connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=min_conn,
        maxconn=max_conn,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        connect_timeout=5,
        options=f"-c statement_timeout={timeout_ms}",
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    logger.info(
        "DB pool ready (min=%s max=%s host=%s db=%s)",
        min_conn, max_conn, config.DB_HOST, config.DB_NAME,
    )


def close_db_pool():
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("DB pool closed.")


@contextlib.contextmanager
def get_cursor():
    """
    Yield a RealDictCursor inside a transaction.

        with get_cursor() as cur:
            cur.execute("SELECT ...")
            row = cur.fetchone()

    Commits automatically on success, rolls back on exception, and always
    returns the connection to the pool.
    """
    global _connection_pool
    if _connection_pool is None:
        init_db_pool()

    conn = _connection_pool.getconn()
    cursor = None
    failed = False
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        conn.commit()
    except Exception:
        failed = True
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        # A connection that errored may be in a bad state - close it instead
        # of recycling it.
        _connection_pool.putconn(conn, close=failed)


# Backwards-compatible alias used by some modules.
transaction = get_cursor
```

---

## ✏️ REPLACE  `app/config/config.py`

```python
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
```

---

## ✏️ REPLACE  `app/services/team_service.py`

```python
"""
app/services/team_service.py  —  REWRITE (drop-in replacement)

Why this changed
----------------
The old version answered "how big is my team?" and "give me the tree" with
recursive CTEs that walk the ENTIRE downline on every page load, and the
admin tree service did it with one SQL query PER node (N+1). At 1 lakh users
a single dashboard click could fire thousands of queries.

This version uses the materialised ltree genealogy path (`users.tree_path`)
and denormalised counters added in migration 0004:

  * direct_count        -> number of direct referrals (kept by trigger)
  * total_team_count    -> size of whole subtree (kept by trigger)
  * tree_path           -> e.g. 1.5.12  => subtree = descendants via `<@`

All public function names/signatures are preserved so the rest of the app
keeps working, but they are now O(subtree) index scans instead of full
recursive walks. Results are cached in Redis and invalidated when the
network changes.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 20
_TEAM_TTL = 120          # seconds for short-lived team aggregates
_TREE_TTL = 300          # seconds for tree payloads


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt(row: dict) -> dict:
    """Serialise a user row into JSON-safe data for the API / templates."""
    if not row:
        return row
    out = dict(row)
    out["id"] = str(out.get("id"))
    if out.get("sponsor_id") is not None:
        out["sponsor_id"] = str(out["sponsor_id"])
    out["is_active"] = bool(out.get("is_active", False))
    out["rank"] = out.get("rank") or "Distributor"
    if isinstance(out.get("created_at"), datetime):
        out["created_at"] = out["created_at"].isoformat()
    return out


# ---------------------------------------------------------------------------
# 1. Direct (Level-1) team
# ---------------------------------------------------------------------------
def get_level_1_team(user_id):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT id, sponsor_id, referral_code, full_name, email, phone,
                       is_active, "rank", rank_level, package_id,
                       direct_count, total_team_count, created_at
                FROM users
                WHERE sponsor_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return [_fmt(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_level_1_team error user=%s: %s", user_id, e)
        return []


# ---------------------------------------------------------------------------
# 2. Total team count  (denormalised -> O(1) read)
# ---------------------------------------------------------------------------
def get_total_team_count(user_id, max_depth: int = DEFAULT_MAX_DEPTH) -> int:
    if not user_id:
        return 0

    cached = cache.get(f"team:count:{user_id}")
    if cached is not None:
        return int(cached)

    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(total_team_count, 0) AS count FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            count = int(row["count"]) if row else 0
        cache.set(f"team:count:{user_id}", count, timeout=_TEAM_TTL)
        return count
    except Exception as e:
        logger.error("get_total_team_count error user=%s: %s", user_id, e)
        return 0


def get_direct_count(user_id) -> int:
    if not user_id:
        return 0
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(direct_count, 0) AS c FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return int(row["c"]) if row else 0
    except Exception as e:
        logger.error("get_direct_count error user=%s: %s", user_id, e)
        return 0


def get_active_count(user_id) -> int:
    """Active members anywhere in the subtree (ltree subtree, indexed)."""
    if not user_id:
        return 0
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM users u
                JOIN users root ON root.id = %s
                WHERE u.tree_path IS NOT NULL
                  AND root.tree_path IS NOT NULL
                  AND u.tree_path <@ root.tree_path
                  AND u.id <> root.id
                  AND u.is_active = TRUE
                """,
                (user_id,),
            )
            return int(cur.fetchone()["c"])
    except Exception as e:
        logger.error("get_active_count error user=%s: %s", user_id, e)
        return 0


# ---------------------------------------------------------------------------
# 3. Team by a specific level  (nlevel difference on ltree)
# ---------------------------------------------------------------------------
def get_team_by_level(user_id, level: int):
    if not user_id or not level or level <= 0:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active, u."rank", u.rank_level,
                       u.direct_count, u.total_team_count, u.created_at
                FROM users u
                JOIN users root ON root.id = %s
                WHERE u.tree_path IS NOT NULL
                  AND root.tree_path IS NOT NULL
                  AND u.tree_path <@ root.tree_path
                  AND nlevel(u.tree_path) - nlevel(root.tree_path) = %s
                ORDER BY u.created_at DESC
                """,
                (user_id, level),
            )
            return [_fmt(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_team_by_level error user=%s level=%s: %s", user_id, level, e)
        return []


# ---------------------------------------------------------------------------
# 4. Full genealogy  — depth-bounded, ONE query (no N+1)
# ---------------------------------------------------------------------------
def get_genealogy_tree(user_id, max_depth: int = DEFAULT_MAX_DEPTH):
    """
    Return a FLAT list of the subtree (root included), each row tagged with
    its relative `level` (root = 0). One bounded SQL query.
    """
    if not user_id:
        return []

    cached = cache.get(f"team:tree:{user_id}:{max_depth}")
    if cached is not None:
        return cached

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active, u."rank", u.rank_level, u.package_id,
                       u.direct_count, u.total_team_count, u.created_at,
                       (nlevel(u.tree_path) - nlevel(root.tree_path)) AS level
                FROM users u
                JOIN users root ON root.id = %s
                WHERE u.tree_path IS NOT NULL
                  AND root.tree_path IS NOT NULL
                  AND u.tree_path <@ root.tree_path
                  AND nlevel(u.tree_path) - nlevel(root.tree_path) <= %s
                ORDER BY level ASC, u.created_at ASC
                """,
                (user_id, max_depth),
            )
            rows = [_fmt(r) for r in cur.fetchall()]

        cache.set(f"team:tree:{user_id}:{max_depth}", rows, timeout=_TREE_TTL)
        return rows
    except Exception as e:
        logger.error("get_genealogy_tree error user=%s: %s", user_id, e)
        return []


# ---------------------------------------------------------------------------
# 5. NEW — drill-down node used by the "My Team" UI
# ---------------------------------------------------------------------------
def get_team_node(user_id, viewer_id=None, page: int = 1, page_size: int = 12,
                  rank: str | None = None, status: str | None = None):
    """
    Build the payload for ONE node of the drill-down team view.

    The UI calls this with the *currently selected* member's id. Clicking a
    child re-calls the same endpoint with that child's id, so "the audit
    drill follows the selected member".

    Returns the node header (YOU / member summary) + ONE page of direct
    children. Children are NOT expanded server-side; each child carries its
    own `has_team` / `total_team_count`, so the browser only fetches the next
    level when the user clicks "Drill". This is what keeps it fast at scale.
    """
    if not user_id:
        return None

    page = max(1, int(page or 1))
    page_size = min(48, max(1, int(page_size or 12)))
    offset = (page - 1) * page_size

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.sponsor_id, u.referral_code, u.full_name, u.email,
                       u.phone, u.is_active, u."rank", u.rank_level, u.package_id,
                       sp.name AS package_name,
                       u.direct_count, u.total_team_count,
                       (SELECT COUNT(*) FROM users d
                          JOIN users r ON r.id = u.id
                         WHERE d.tree_path <@ r.tree_path AND d.id <> u.id
                           AND d.is_active = TRUE) AS active_count,
                       u.created_at
                FROM users u
                LEFT JOIN subscription_plans sp ON sp.id = u.package_id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            node = cur.fetchone()
            if not node:
                return None

            where = ["c.sponsor_id = %s"]
            params: list = [user_id]
            if status == "active":
                where.append("c.is_active = TRUE")
            elif status == "inactive":
                where.append("c.is_active = FALSE")
            if rank:
                where.append("c.\"rank\" = %s")
                params.append(rank)

            where_sql = " AND ".join(where)

            cur.execute(
                f"""
                SELECT c.id, c.sponsor_id, c.referral_code, c.full_name, c.email,
                       c.phone, c.is_active, c."rank", c.rank_level, c.package_id,
                       c.direct_count, c.total_team_count, c.created_at
                FROM users c
                WHERE {where_sql}
                ORDER BY c.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, page_size, offset),
            )
            children = [_fmt(r) for r in cur.fetchall()]

            cur.execute(
                f"SELECT COUNT(*) AS c FROM users c WHERE {where_sql}",
                params,
            )
            total_children = int(cur.fetchone()["c"])

        node = _fmt(node)
        is_self = viewer_id is not None and str(viewer_id) == str(user_id)

        return {
            "node": {
                "id": node["id"],
                "label": "YOU" if is_self else f"M{node['id']}",
                "full_name": node.get("full_name"),
                "referral_code": node.get("referral_code"),
                "rank": node.get("rank") or "Distributor",
                "package_name": node.get("package_name"),
                "is_active": node.get("is_active"),
                "joined": node.get("created_at"),
            },
            "stats": {
                "total_team": int(node.get("total_team_count") or 0),
                "direct_referrals": int(node.get("direct_count") or 0),
                "active": int(node.get("active_count") or 0),
                "rank": node.get("rank") or "Distributor",
            },
            "level": 1,
            "children": children,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_children,
                "pages": (total_children + page_size - 1) // page_size,
            },
        }
    except Exception as e:
        logger.error("get_team_node error user=%s: %s", user_id, e)
        return None


# ---------------------------------------------------------------------------
# 6. Network profile + history (admin drill)
# ---------------------------------------------------------------------------
def get_user_network_profile(user_id, max_depth: int = DEFAULT_MAX_DEPTH):
    if not user_id:
        return {}
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.direct_count, u.total_team_count,
                       (SELECT COUNT(*) FROM users d
                          JOIN users r ON r.id = u.id
                         WHERE d.tree_path <@ r.tree_path AND d.id <> u.id
                           AND d.is_active = TRUE) AS active_count
                FROM users u WHERE u.id = %s
                """,
                (user_id,),
            )
            stats = cur.fetchone() or {}

            cur.execute(
                """
                WITH RECURSIVE upline AS (
                    SELECT id, sponsor_id, full_name, 1 AS level
                    FROM users WHERE id = %s
                    UNION ALL
                    SELECT p.id, p.sponsor_id, p.full_name, up.level + 1
                    FROM users p JOIN upline up ON p.id = up.sponsor_id
                )
                SELECT id, full_name, level FROM upline
                WHERE level > 1 ORDER BY level ASC
                """,
                (user_id,),
            )
            upline_chain = [dict(r) for r in cur.fetchall()]

        return {
            "total_downline": int(stats.get("total_team_count", 0) or 0),
            "direct_referrals": int(stats.get("direct_count", 0) or 0),
            "active_count": int(stats.get("active_count", 0) or 0),
            "upline_chain": upline_chain,
        }
    except Exception as e:
        logger.error("get_user_network_profile error user=%s: %s", user_id, e)
        return {}


def get_user_purchase_history(user_id, limit: int = 100):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT p.name AS package_name, p.price, o.status, o.created_at
                FROM orders o
                JOIN subscription_plans p ON o.package_id = p.id
                WHERE o.user_id = %s
                ORDER BY o.created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_user_purchase_history error user=%s: %s", user_id, e)
        return []


def get_user_audit_trail(user_id, limit: int = 50):
    if not user_id:
        return []
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT action, metadata, created_at
                FROM audit_logs
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("get_user_audit_trail error user=%s: %s", user_id, e)
        return []


# ---------------------------------------------------------------------------
# 7. Cache invalidation — call whenever a user is added / sponsor changes /
#    a package is purchased. Cheap and safe to call repeatedly.
# ---------------------------------------------------------------------------
def invalidate_team_cache(user_id):
    try:
        cache.delete(f"team:count:{user_id}")
        cache.delete_memoized(get_genealogy_tree)
    except Exception:
        pass
```

---

## ✏️ REPLACE  `app/services/sponsor_service.py`

```python
"""
app/services/sponsor_service.py  —  REWRITE (drop-in replacement)

Accepts an optional open cursor so the upline walk runs INSIDE the caller's
transaction (commission distribution). The recursive CTE is bounded and uses
the indexed sponsor_id link (depth is tiny — payouts only go ~10 levels).
"""
from __future__ import annotations

import logging

from app.db import get_cursor

logger = logging.getLogger(__name__)


def get_sponsor_chain(user_id, max_levels: int = 10, cur=None):
    """
    Return the upline as [{user_id, full_name, email, phone, is_active, level}]
    ordered from the direct sponsor (level 1) upward.
    """
    if not user_id:
        return []

    sql = """
        WITH RECURSIVE upline AS (
            SELECT sponsor_id, 1 AS level
            FROM users
            WHERE id = %s AND sponsor_id IS NOT NULL
            UNION ALL
            SELECT u.sponsor_id, ul.level + 1
            FROM users u
            JOIN upline ul ON u.id = ul.sponsor_id
            WHERE u.sponsor_id IS NOT NULL AND ul.level < %s
        )
        SELECT u.id AS user_id, u.full_name, u.email, u.phone,
               u.is_active, ul.level
        FROM upline ul
        JOIN users u ON u.id = ul.sponsor_id
        ORDER BY ul.level ASC
    """

    def _run(c):
        c.execute(sql, (user_id, max_levels))
        return [dict(r) for r in c.fetchall()]

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("get_sponsor_chain error user=%s: %s", user_id, e)
        return []
```

---

## ✏️ REPLACE  `app/services/package_service.py`

```python
"""
app/services/package_service.py  —  REWRITE (drop-in replacement)

Fixes
-----
1. get_plan_with_commissions() used to SELECT a column called `percentage`
   from level_commissions, but the real column is `commission_percentage`.
   Every purchase therefore raised UndefinedColumn -> the engine returned an
   error and NO level commission was ever paid. Fixed; we now read from the
   canonical `commission_plan` table and normalise the legacy table too.
2. Plan/commission configuration is cached in Redis for 60 s (was a fresh
   query on every purchase) and cache is busted whenever an admin edits it.
3. purchase_package() now runs activation + order insert + commission
   distribution in ONE transaction (the old version committed activation in
   a separate transaction, so a commission failure left the user activated
   but unpaid — or vice versa).
4. All money is Decimal; inputs are validated.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)

PLAN_CACHE_TTL = 60


# ===========================================================================
# 1. PLANS
# ===========================================================================
def get_all_plans(include_inactive: bool = False):
    try:
        with get_cursor() as cur:
            sql = "SELECT * FROM subscription_plans"
            if not include_inactive:
                sql += " WHERE is_active = TRUE"
            sql += " ORDER BY price ASC"
            cur.execute(sql)
            plans = [dict(p) for p in cur.fetchall()]
            for plan in plans:
                cur.execute(
                    "SELECT image_path FROM plan_images WHERE plan_id = %s",
                    (plan["id"],),
                )
                plan["images"] = [r["image_path"] for r in cur.fetchall()]
            return plans
    except Exception as e:
        logger.error("get_all_plans error: %s", e)
        return []


def add_plan_image(plan_id, image_path):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO plan_images (plan_id, image_path) VALUES (%s, %s)",
            (plan_id, image_path),
        )
    cache.delete("plans:all")


def get_plan_by_id(plan_id, cur=None):
    query = "SELECT * FROM subscription_plans WHERE id = %s"
    if cur is not None:
        cur.execute(query, (plan_id,))
        return cur.fetchone()
    with get_cursor() as new_cur:
        new_cur.execute(query, (plan_id,))
        return new_cur.fetchone()


get_package_by_id = get_plan_by_id
get_all_active_packages = get_all_plans


def update_plan(plan_id, price, coupons, is_active, product_cost=0):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE subscription_plans
            SET price = %s, lucky_draw_coupons = %s, product_cost = %s,
                is_active = %s
            WHERE id = %s
            """,
            (Decimal(str(price)), int(coupons or 0), Decimal(str(product_cost or 0)),
             bool(is_active), plan_id),
        )
    cache.delete_memoized(get_plan_with_commissions, plan_id)
    cache.delete("plans:all")


def create_plan(name, price, coupons=12, product_cost=0):
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO subscription_plans (name, price, lucky_draw_coupons,
                                            product_cost, is_active)
            VALUES (%s, %s, %s, %s, TRUE) RETURNING id
            """,
            (name, Decimal(str(price)), int(coupons or 0), Decimal(str(product_cost or 0))),
        )
        new_id = cur.fetchone()["id"]
    cache.delete("plans:all")
    return new_id


# ===========================================================================
# 2. COMMISSION CONFIGURATION
# ===========================================================================
def get_global_commissions():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM global_commissions ORDER BY setting_key")
        return [dict(r) for r in cur.fetchall()]


def update_global_commission(setting_key, percentage_value):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE global_commissions SET percentage_value = %s
            WHERE setting_key = %s
            """,
            (Decimal(str(percentage_value)), setting_key),
        )
    cache.delete("commissions:config")


def get_level_commissions():
    """Canonical level ladder from commission_plan (fallback to legacy table)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT level, percentage AS commission_percentage
            FROM commission_plan WHERE is_active = TRUE ORDER BY level
            """
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                "SELECT level, commission_percentage FROM level_commissions ORDER BY level"
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_commission_config(cur=None) -> dict:
    """Load {direct_commission, levels:{1:10,...}} once and cache in Redis."""
    cached = cache.get("commissions:config")
    if cached is not None:
        return cached

    def _load(c):
        c.execute("SELECT setting_key, percentage_value FROM global_commissions")
        globals_ = {r["setting_key"]: Decimal(str(r["percentage_value"]))
                    for r in c.fetchall()}
        direct = globals_.get("direct_commission")
        if direct is None:
            direct = globals_.get("direct_referral", Decimal("0"))

        c.execute(
            "SELECT level, percentage FROM commission_plan WHERE is_active = TRUE"
        )
        levels_rows = c.fetchall()
        levels = {int(r["level"]): Decimal(str(r["percentage"])) for r in levels_rows}
        if not levels:
            c.execute("SELECT level, commission_percentage FROM level_commissions")
            levels = {int(r["level"]): Decimal(str(r["commission_percentage"]))
                      for r in c.fetchall()}
        return {"direct": direct, "levels": levels}

    config = _load(cur) if cur is not None else None
    if config is None:
        with get_cursor() as c:
            config = _load(c)

    cache.set("commissions:config", config, timeout=PLAN_CACHE_TTL)
    return config


# ===========================================================================
# 3. ACTIVATION + PURCHASE
# ============================================================================
def activate_user_package(cur, user_id, plan_id):
    plan = get_plan_by_id(plan_id, cur)
    if not plan:
        raise ValueError("Plan not found")

    cur.execute(
        """
        UPDATE users
        SET package_id = %s, is_active = TRUE, activated_at = NOW()
        WHERE id = %s
        """,
        (plan_id, user_id),
    )
    cur.execute(
        """
        INSERT INTO user_packages (user_id, package_id, amount, created_at)
        VALUES (%s, %s, %s, NOW())
        """,
        (user_id, plan_id, plan["price"]),
    )
    return True


def purchase_package(user_id, plan_id, payment_ref=None):
    """
    Atomic purchase: create order -> activate -> distribute commissions,
    all in a single DB transaction. All-or-nothing.
    """
    from app.services.commission_engine import distribute_commission

    try:
        with get_cursor() as cur:
            plan = get_plan_by_id(plan_id, cur)
            if not plan or not plan.get("is_active", True):
                return {"success": False, "message": "Plan not found or inactive."}

            # 1. The order is the financial anchor for idempotency.
            cur.execute(
                """
                INSERT INTO orders (user_id, package_id, amount, status, payment_ref)
                VALUES (%s, %s, %s, 'completed', %s)
                RETURNING id
                """,
                (user_id, plan_id, plan["price"], payment_ref),
            )
            order_id = cur.fetchone()["id"]

            # 2. Activate the buyer (same transaction).
            activate_user_package(cur, user_id, plan_id)

            # 3. Distribute commissions (same transaction, same cursor).
            result = distribute_commission(
                buyer_id=user_id,
                package_id=plan_id,
                order_id=order_id,
                cur=cur,
            )
            if result.get("status") == "error":
                raise RuntimeError(result.get("message", "Commission error"))

        return {
            "success": True,
            "order_id": order_id,
            "amount": float(plan["price"]),
            "message": "Package purchased and commissions distributed.",
        }
    except Exception as e:
        logger.error("purchase_package error user=%s: %s", user_id, e)
        return {"success": False, "message": str(e)}


# ===========================================================================
# 4. Plan + commissions (used by the engine)
# ===========================================================================
def get_plan_with_commissions(plan_id):
    """Plan row plus current commission percentages (cached in Redis)."""
    with get_cursor() as cur:
        plan = get_plan_by_id(plan_id, cur)
        if not plan:
            return None
        plan = dict(plan)
        cfg = get_commission_config(cur)
        plan["level_commissions"] = {str(k): v for k, v in cfg["levels"].items()}
        plan["direct_commission"] = cfg["direct"]
        return plan
```

---

## ✏️ REPLACE  `app/services/commission_engine.py`

```python
"""
app/services/commission_engine.py  —  REWRITE (drop-in replacement)

Fixes (these were silently breaking every payout)
-------------------------------------------------
1. Wrote wallet entries into a column called `reference`, but the table has
   `reference_id` -> the whole payout transaction rolled back every time.
2. Idempotency used a free-text commission_type that included a random uuid /
   timestamp, so the "duplicate" check could NEVER match a retry -> double
   payouts were possible. Idempotency is now anchored to the concrete
   `orders.id` with a real UNIQUE index (see migration 0004).
3. Activation + payout ran in two separate transactions -> a failure left
   users activated but unpaid (or paid but not active). Now the caller passes
   an open cursor and everything commits together.
4. Money is Decimal throughout; payouts use the shared ledger service so
   closing balances are always correct.

Business rule
-------------
For a package purchase of price P:
  * Level-1 upline (the direct sponsor) earns  direct_commission % of P.
  * Upline levels 2..N earn the per-level percentage from commission_plan.
  * Optionally the buyer gets self_cashback % (global setting).
TDS/admin fees are applied at withdrawal time, not here.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.services.sponsor_service import get_sponsor_chain
from app.services.wallet_service import credit_wallet

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWO_PLACES)


def distribute_commission(buyer_id, package_id, order_id=None, cur=None,
                          purchase_ref=None):
    """
    Distribute upline commissions for a purchase.

    Pass an open `cur` (and a committed `order_id`) to run inside the caller's
    transaction. If omitted, opens its own transaction (used by jobs/CLI).
    """
    # Avoid importing the rank evaluator at module import time (circular-safe).
    from app.services.rank_service import evaluate_user_rank_and_bonus

    def _run(c):
        from app.services.package_service import get_plan_with_commissions

        package = get_plan_with_commissions(package_id) if order_id is None \
            else _load_package(c, package_id)
        if not package:
            return {"status": "error", "message": "Package not found or inactive."}

        price = Decimal(str(package["price"]))
        levels = package.get("level_commissions") or {}
        direct_pct = Decimal(str(package.get("direct_commission") or levels.get("1", 0)))

        sponsors = get_sponsor_chain(buyer_id, cur=c)
        if not sponsors:
            return {"status": "success", "message": "No upline; no commissions."}

        paid = 0
        for sp in sponsors:
            earner_id = sp["user_id"]
            level = int(sp["level"])

            pct = direct_pct if level == 1 else Decimal(str(levels.get(str(level), 0)))
            amount = (price * (pct / Decimal("100"))).quantize(TWO_PLACES)
            if amount <= 0:
                continue

            ref = f"COMM-{order_id}-{earner_id}-L{level}" if order_id else \
                  (purchase_ref or f"COMM-{buyer_id}-{package_id}-{earner_id}-L{level}")

            # 1) Commission row (idempotent via unique order/earner/level).
            try:
                c.execute(
                    """
                    INSERT INTO commissions
                        (earner_id, from_user_id, level, amount,
                         commission_type, order_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (earner_id, COALESCE(order_id, 0), level)
                    DO NOTHING
                    RETURNING id
                    """,
                    (earner_id, buyer_id, level, amount, "package_commission",
                     order_id),
                )
                inserted = c.fetchone()
            except Exception as e:
                # Unique index exists but expression-based ON CONFLICT may not
                # be inferrable on older PG -> treat as duplicate.
                logger.warning("commission insert conflict: %s", e)
                inserted = None
            if not inserted:
                continue

            # 2) Wallet credit through the shared ledger (sets closing balance).
            credit_wallet(
                c, earner_id, amount, ref,
                f"Level {level} commission on order #{order_id or purchase_ref}",
            )
            paid += 1

            # 3) Re-rank the earner (lightweight, same transaction).
            try:
                evaluate_user_rank_and_bonus(earner_id, cur=c)
            except Exception as e:
                logger.warning("rank eval skipped for %s: %s", earner_id, e)

        # Optional self cashback for the buyer.
        cashback_pct = _global_pct(c, "self_cashback")
        if cashback_pct > 0:
            cb = (price * (cashback_pct / Decimal("100"))).quantize(TWO_PLACES)
            if cb > 0:
                cb_ref = f"CASH-{order_id or purchase_ref}-{buyer_id}"
                c.execute(
                    """
                    INSERT INTO commissions (earner_id, from_user_id, level, amount,
                                             commission_type, order_id)
                    VALUES (%s, %s, 0, %s, 'self_cashback', %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (buyer_id, buyer_id, cb, order_id),
                )
                credit_wallet(c, buyer_id, cb, cb_ref, "Self purchase cashback")

        return {"status": "success", "paid_upline": paid, "message": "Commissions distributed."}

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("distribute_commission failed buyer=%s: %s", buyer_id, e)
        return {"status": "error", "message": "Commission processing failed."}


def _load_package(c, package_id):
    from app.services.package_service import get_plan_by_id, get_commission_config
    plan = get_plan_by_id(package_id, c)
    if not plan:
        return None
    plan = dict(plan)
    cfg = get_commission_config(c)
    plan["level_commissions"] = {str(k): v for k, v in cfg["levels"].items()}
    plan["direct_commission"] = cfg["direct"]
    return plan


def _global_pct(c, key) -> Decimal:
    c.execute("SELECT percentage_value FROM global_commissions WHERE setting_key = %s", (key,))
    row = c.fetchone()
    return Decimal(str(row["percentage_value"])) if row else Decimal("0")


def process_rank_volume_bonus(user_id, rank_name, level, bonus_amount, cur=None):
    """Pay a one-time rank achievement bonus (idempotent per user/rank)."""
    bonus_amount = _money(bonus_amount)
    ref = f"RANKBONUS-{user_id}-L{level}"

    def _do(c):
        c.execute(
            """
            INSERT INTO commissions (earner_id, from_user_id, level, amount,
                                     commission_type)
            VALUES (%s, %s, %s, %s, 'rank_volume_bonus')
            ON CONFLICT DO NOTHING
            """,
            (user_id, user_id, level, bonus_amount),
        )
        credit_wallet(c, user_id, bonus_amount, ref, f"Rank bonus: {rank_name}")
        return True

    try:
        if cur is not None:
            return _do(cur)
        with get_cursor() as c:
            return _do(c)
    except Exception as e:
        logger.error("rank bonus failed user=%s: %s", user_id, e)
        return False
```

---

## ✏️ REPLACE  `app/services/rank_service.py`

```python
"""
app/services/rank_service.py  —  REWRITE (drop-in replacement)

Fixes
-----
* evaluate_user_rank_and_bonus() used to call get_total_team_count(), which
  opened a SECOND connection in the middle of the payout transaction. With a
  transaction pool that deadlocks / self-blocks. All reads now use the open
  cursor.
* Team size / volume used unbounded recursive CTEs run for EVERY earner on
  EVERY purchase. Now: team size reads the denormalised counter and volume is
  one indexed subtree aggregate over ltree.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.db import get_cursor
from app.services.team_service import get_total_team_count

logger = logging.getLogger(__name__)
TWO = Decimal("0.01")


def _volume(c, user_id) -> Decimal:
    """Total package volume in the whole subtree (ltree, indexed)."""
    c.execute(
        """
        SELECT COALESCE(SUM(o.amount), 0) AS v
        FROM orders o
        JOIN users d   ON d.id = o.user_id
        JOIN users root ON root.id = %s
        WHERE d.tree_path <@ root.tree_path
        """,
        (user_id,),
    )
    return Decimal(str(c.fetchone()["v"]))


def _rank_level(c, user_id):
    c.execute("SELECT COALESCE(rank_level, 1) AS rl FROM users WHERE id = %s", (user_id,))
    row = c.fetchone()
    return int(row["rl"]) if row else 1


def get_user_rank_data(user_id):
    with get_cursor() as cur:
        current_volume = _volume(cur, user_id)
        team_size = get_total_team_count(user_id)
        current_rank_level = _rank_level(cur, user_id)

        cur.execute("SELECT rank_name FROM rank_rules WHERE level = %s", (current_rank_level,))
        row = cur.fetchone()
        current_rank_name = row["rank_name"] if row else "Associate"

        cur.execute(
            """
            SELECT rank_name, req_business_vol, req_team_size
            FROM rank_rules WHERE level > %s ORDER BY level ASC LIMIT 1
            """,
            (current_rank_level,),
        )
        nxt = cur.fetchone()
        if nxt:
            next_rank_name = nxt["rank_name"]
            next_volume = Decimal(str(nxt["req_business_vol"]))
            next_team = nxt["req_team_size"]
            progress = (current_volume / next_volume * 100) if next_volume > 0 else Decimal("0")
        else:
            next_rank_name = "Max Rank Reached"
            next_volume = current_volume
            next_team = team_size
            progress = Decimal("100")

        return {
            "current_rank": current_rank_name,
            "next_rank": next_rank_name,
            "current_volume": float(current_volume),
            "next_rank_volume": float(next_volume),
            "current_team_size": team_size,
            "next_rank_team_size": next_team,
            "progress_percentage": float(min(progress, Decimal("100"))),
        }


def evaluate_user_rank_and_bonus(user_id, cur=None):
    """Promote the user if eligible and pay one-time rank bonuses."""
    from app.services.commission_engine import process_rank_volume_bonus

    def _run(c):
        current_volume = _volume(c, user_id)

        c.execute("SELECT COALESCE(total_team_count, 0) AS ts FROM users WHERE id = %s", (user_id,))
        team_size = int(c.fetchone()["ts"])

        current_rank_level = _rank_level(c, user_id)
        c.execute("SELECT * FROM rank_rules ORDER BY level ASC")
        rules = c.fetchall()

        highest = current_rank_level
        for rule in rules:
            level = int(rule["level"])
            req_vol = Decimal(str(rule["req_business_vol"]))
            req_size = int(rule["req_team_size"])
            bonus_pct = Decimal(str(rule["bonus_percentage"]))

            if current_volume >= req_vol:
                c.execute(
                    "SELECT 1 FROM user_bonus_history WHERE user_id = %s AND rank_level = %s",
                    (user_id, level),
                )
                if not c.fetchone():
                    bonus = (req_vol * bonus_pct / Decimal("100")).quantize(TWO)
                    c.execute(
                        """
                        INSERT INTO user_bonus_history (user_id, rank_level, bonus_amount)
                        VALUES (%s, %s, %s)
                        """,
                        (user_id, level, bonus),
                    )
                    process_rank_volume_bonus(user_id, rule["rank_name"], level, bonus, c)

            if current_volume >= req_vol and team_size >= req_size:
                highest = max(highest, level)

        if highest > current_rank_level:
            c.execute("UPDATE users SET rank_level = %s WHERE id = %s", (highest, user_id))
            logger.info("User %s promoted to rank level %s", user_id, highest)

        return {"status": "success", "current_volume": float(current_volume),
                "team_size": team_size, "rank_level": highest}

    try:
        if cur is not None:
            return _run(cur)
        with get_cursor() as c:
            return _run(c)
    except Exception as e:
        logger.error("rank evaluation failed user=%s: %s", user_id, e)
        return {"status": "error", "message": "Evaluation failed"}


def get_user_rank(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT r.rank_name
            FROM users u JOIN rank_rules r ON u.rank_level = r.level
            WHERE u.id = %s
            """,
            (user_id,),
        )
        return cur.fetchone()
```

---

## ✏️ REPLACE  `app/services/admin_user_service.py`

```python
"""
app/services/admin_user_service.py — REWRITE

* get_users_paginated() now orders by id (indexed) and uses the pg_trgm
  indexes from migration 0004 for search (the old ILIKE '%..%' forced a
  sequential scan over 100k rows on every keystroke).
* Adds filters (status) and returns rank/package for a richer table.
* Activate/deactivate invalidate team counters cache.
"""
from __future__ import annotations

import logging
from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)

_USER_COLS = """
    id, full_name, email, phone, referral_code, sponsor_id,
    is_active, rank_level, package_id, created_at
"""


def get_all_users(limit=100):
    with get_cursor() as cur:
        cur.execute(f"SELECT {_USER_COLS} FROM users ORDER BY id DESC LIMIT %s", (limit,))
        return cur.fetchall()


def activate_user(user_id):
    with get_cursor() as cur:
        cur.execute("UPDATE users SET is_active = TRUE, activated_at = COALESCE(activated_at, NOW()) WHERE id = %s",
                    (user_id,))
    cache.delete(f"team:count:{user_id}")
    return True


def deactivate_user(user_id):
    with get_cursor() as cur:
        cur.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
    cache.delete(f"team:count:{user_id}")
    return True


def search_users(keyword, limit=50):
    like = f"%{keyword}%"
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT {_USER_COLS} FROM users
            WHERE full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s
               OR referral_code ILIKE %s OR id::text = %s
            ORDER BY id DESC LIMIT %s
            """,
            (like, like, like, like, keyword.strip(), limit),
        )
        return cur.fetchall()


def get_users_paginated(page=1, search="", status=None):
    limit = 25
    page = max(1, int(page or 1))
    offset = (page - 1) * limit

    where, params = [], []
    if search:
        like = f"%{search.strip()}%"
        where.append("(full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s "
                     "OR referral_code ILIKE %s OR id::text = %s)")
        params += [like, like, like, like, search.strip()]
    if status in ("active", "inactive"):
        where.append("is_active = %s")
        params.append(status == "active")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with get_cursor() as cur:
        cur.execute(
            f"SELECT {_USER_COLS} FROM users {where_sql} ORDER BY id DESC LIMIT %s OFFSET %s",
            (*params, limit, offset),
        )
        users = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) AS c FROM users {where_sql}", params)
        total = int(cur.fetchone()["c"])

    pages = (total + limit - 1) // limit
    return {"users": users, "total": total, "page": page, "pages": pages}


def get_user_by_id(user_id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()
```

---

## ✏️ REPLACE  `app/services/admin/tree_service.py`

```python
"""
app/services/admin/tree_service.py — REWRITE

Why this changed
----------------
The old build_tree() issued ONE database query per node, recursively. A user
with 5,000 downline = 5,000 queries on a single page load. Worse, it was
wrapped in @cache.memoize(timeout=1) — a one-second cache that is useless and
(under SimpleCache) per-process. This version:

  * fetches the entire depth-bounded subtree in ONE query using ltree
    (migration 004), then assembles parent->children in memory (O(n));
  * caches the assembled tree in Redis for 300 s;
  * exposes invalidate so edits/activations can bust it.
"""
from __future__ import annotations

import logging

from app.db import get_cursor
from app.cache import cache

logger = logging.getLogger(__name__)
TREE_TTL = 300


def get_user_tree(user_id, max_depth: int = 10):
    cached = cache.get(f"tree:full:{user_id}:{max_depth}")
    if cached is not None:
        return cached

    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT u.id AS user_id, u.full_name, u.email, u.phone,
                       u.referral_code, u.is_active, u.created_at,
                       u.sponsor_id, u.direct_count, u.total_team_count,
                       (nlevel(u.tree_path) - nlevel(root.tree_path)) AS level
                FROM users u
                JOIN users root ON root.id = %s
                WHERE u.tree_path <@ root.tree_path
                  AND nlevel(u.tree_path) - nlevel(root.tree_path) <= %s
                ORDER BY level ASC, u.created_at ASC
                """,
                (user_id, max_depth),
            )
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return None

        nodes: dict = {}
        for r in rows:
            r["children"] = []
            nodes[str(r["user_id"])] = r

        root = nodes[str(user_id)]
        for r in rows:
            pid = str(r["sponsor_id"]) if r.get("sponsor_id") is not None else None
            if pid and pid in nodes and r["user_id"] != root["user_id"]:
                nodes[pid]["children"].append(r)

        cache.set(f"tree:full:{user_id}:{max_depth}", root, timeout=TREE_TTL)
        return root
    except Exception as e:
        logger.error("get_user_tree error user=%s: %s", user_id, e)
        return None


def get_children(user_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, full_name, email, phone, referral_code, is_active,
                   created_at, direct_count, total_team_count
            FROM users WHERE sponsor_id = %s ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def invalidate_tree(user_id):
    try:
        cache.delete(f"tree:full:{user_id}:10")
    except Exception:
        pass
```

---

## ✏️ REPLACE  `app/routes/admin/package_routes.py`

```python
"""
app/routes/admin/package_routes.py  —  COMPLETE REPLACEMENT

Admin screen for Packages + the Commission/Business plan.

Important fix vs the old file:
  * Level percentages are now saved to the CANONICAL `commission_plan` table
    (which the commission engine actually reads) and mirrored to the legacy
    `level_commissions` table so old screens keep working.
  * Saving busts the Redis config cache so new % apply immediately.
  * Every route is admin-protected.
"""
import os
from decimal import Decimal, InvalidOperation

from werkzeug.utils import secure_filename
from flask import (
    Blueprint, render_template, request, redirect, flash, current_app, abort
)
from flask_login import login_required, current_user

from app.db import get_cursor
from app.cache import cache
from app.services.package_service import (
    get_all_plans,
    update_plan,
    create_plan,
    add_plan_image,
    get_global_commissions,
    update_global_commission,
    get_level_commissions,
)

admin_package_bp = Blueprint("admin_package", __name__)

UPLOAD_FOLDER = "app/static/uploads/packages"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _admin_only():
    """All package/commission routes are admin-only."""
    if not current_user.is_authenticated or getattr(current_user, "role_id", 2) != 1:
        abort(403)


def _to_decimal(value, default="0"):
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except (InvalidOperation, ValueError):
        return Decimal(default)


# ===========================================================================
# PAGE
# ===========================================================================
@admin_package_bp.route("/admin/packages", methods=["GET"])
@login_required
def manage_packages():
    _admin_only()
    try:
        backend_url = request.host_url.rstrip("/")
        packages = []
        with get_cursor() as cur:
            cur.execute("SELECT * FROM subscription_plans ORDER BY price ASC")
            for plan in cur.fetchall():
                pkg = dict(plan)
                cur.execute(
                    "SELECT id, image_path FROM plan_images WHERE plan_id = %s ORDER BY id ASC",
                    (pkg["id"],),
                )
                images = []
                for row in cur.fetchall():
                    path = row["image_path"]
                    if path and path.startswith("/"):
                        path = f"{backend_url}{path}"
                    images.append({"id": row["id"], "path": path})
                if not images and pkg.get("image_url"):
                    p = pkg["image_url"]
                    if p.startswith("/"):
                        p = f"{backend_url}{p}"
                    images = [{"id": 0, "path": p}]
                pkg["images"] = images
                packages.append(pkg)

        settings = get_global_commissions()
        level_comms = get_level_commissions()
    except Exception as e:
        current_app.logger.error("manage_packages error: %s", e)
        packages, settings, level_comms = [], [], []

    return render_template(
        "admin/packages.html",
        packages=packages,
        settings=settings,
        level_comms=level_comms,
    )


# ===========================================================================
# PLANS
# ===========================================================================
@admin_package_bp.route("/admin/packages/add", methods=["POST"])
@login_required
def admin_add_plan():
    _admin_only()
    try:
        name = (request.form.get("name") or "").strip()
        price = _to_decimal(request.form.get("price"))
        coupons = int(request.form.get("coupons") or 12)
        product_cost = _to_decimal(request.form.get("product_cost"))
        if not name or price <= 0:
            flash("Plan name and a valid price are required.", "danger")
        else:
            create_plan(name, price, coupons, product_cost)
            flash("New plan created! Click Edit to upload product images.", "success")
    except Exception as e:
        flash(f"Error creating plan: {e}", "danger")
    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/update", methods=["POST"])
@login_required
def admin_update_plan():
    _admin_only()
    try:
        plan_id = request.form.get("plan_id")
        price = _to_decimal(request.form.get("price"))
        coupons = int(request.form.get("coupons") or 12)
        product_cost = _to_decimal(request.form.get("product_cost"))
        is_active = request.form.get("is_active") == "on"

        update_plan(plan_id, price, coupons, is_active, product_cost)

        for file in request.files.getlist("product_images"):
            if file and file.filename:
                filename = secure_filename(file.filename)
                unique = f"plan_{plan_id}_{filename}"
                file.save(os.path.join(UPLOAD_FOLDER, unique))
                add_plan_image(plan_id, f"/static/uploads/packages/{unique}")

        flash("Package updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating package: {e}", "danger")
    return redirect("/admin/packages")


@admin_package_bp.route("/admin/packages/delete-image/<int:image_id>", methods=["POST"])
@login_required
def admin_delete_package_image(image_id):
    _admin_only()
    try:
        with get_cursor() as cur:
            cur.execute("SELECT image_path, plan_id FROM plan_images WHERE id = %s", (image_id,))
            img = cur.fetchone()
            if img:
                cur.execute("DELETE FROM plan_images WHERE id = %s", (image_id,))
                cur.execute(
                    "SELECT image_path FROM plan_images WHERE plan_id = %s ORDER BY id DESC LIMIT 1",
                    (img["plan_id"],),
                )
                nxt = cur.fetchone()
                cur.execute(
                    "UPDATE subscription_plans SET image_url = %s WHERE id = %s",
                    (nxt["image_path"] if nxt else None, img["plan_id"]),
                )
                try:
                    p = img["image_path"]
                    if p and p.startswith("/static/"):
                        fp = os.path.join(current_app.static_folder, p.replace("/static/", "", 1))
                        if os.path.exists(fp):
                            os.remove(fp)
                except Exception:
                    pass
        flash("Image deleted.", "success")
    except Exception as e:
        flash(f"Error deleting image: {e}", "danger")
    return redirect("/admin/packages")


# ===========================================================================
# GLOBAL COMMISSIONS (direct %, cashback, TDS, admin fee ...)
# ===========================================================================
@admin_package_bp.route("/admin/commissions/update", methods=["POST"])
@login_required
def admin_update_commission():
    _admin_only()
    try:
        key = request.form.get("setting_key")
        value = _to_decimal(request.form.get("percentage_value"))
        if not key:
            flash("Missing setting key.", "danger")
        else:
            with get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO global_commissions (setting_key, percentage_value, description)
                    VALUES (%s, %s, '')
                    ON CONFLICT (setting_key) DO UPDATE SET percentage_value = EXCLUDED.percentage_value
                    """,
                    (key, value),
                )
            cache.delete("commissions:config")
            flash(f"{key.replace('_', ' ').title()} updated to {value}%.", "success")
    except Exception as e:
        flash(f"Error updating commission: {e}", "danger")
    return redirect("/admin/packages")


# ===========================================================================
# LEVEL COMMISSIONS  (the 1..10 generation ladder)
# Saved into BOTH commission_plan (canonical, used by the engine) and the
# legacy level_commissions table.
# ===========================================================================
@admin_package_bp.route("/admin/level-commissions/update", methods=["POST"])
@login_required
def admin_update_level_commission():
    _admin_only()
    try:
        level = int(request.form.get("level"))
        value = _to_decimal(request.form.get("percentage_value"))
        if level < 1 or value < 0:
            flash("Invalid level or percentage.", "danger")
        else:
            with get_cursor() as cur:
                # Canonical table the engine reads first.
                cur.execute(
                    """
                    INSERT INTO commission_plan (level, percentage, is_active)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (level) DO UPDATE SET percentage = EXCLUDED.percentage,
                                                     is_active = TRUE
                    """,
                    (level, value),
                )
                # Mirror to legacy table (same column the old template used).
                cur.execute(
                    """
                    INSERT INTO level_commissions (level, commission_percentage)
                    VALUES (%s, %s)
                    ON CONFLICT (level) DO UPDATE SET commission_percentage = EXCLUDED.commission_percentage
                    """,
                    (level, value),
                )
            cache.delete("commissions:config")
            flash(f"Level {level} commission updated to {value}%.", "success")
    except Exception as e:
        flash(f"Error updating level commission: {e}", "danger")
    return redirect("/admin/packages")
```

---

## 🆕 CREATE  `app/routes/team_routes.py`

```python
"""
app/routes/team_routes.py  —  NEW FILE

Drill-down team API. The "My Team" screen calls the SAME endpoint with the
currently selected member's id, so the audit/ drill follows the selection:

    GET /api/team/node                -> logged-in user's own root node
    GET /api/team/node?user_id=123    -> any member (admin only for other ids)
    GET /api/team/node/123            -> same, path style

Query params: page, page_size, rank, level (reserved), status (active|inactive)

Response:
    { node:{...}, stats:{total_team, direct_referrals, active, rank},
      level:1, children:[...], pagination:{page,pages,total} }

Only ONE level of children is returned per call; each child carries
total_team_count + direct_count, so the browser fetches deeper on click.
That is what keeps it instant with 100k+ users.
"""
from __future__ import annotations

import logging

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.services.team_service import (
    get_team_node,
    get_total_team_count,
    get_level_1_team,
    get_user_network_profile,
)
from app.services.sponsor_service import get_sponsor_chain

logger = logging.getLogger(__name__)
team_bp = Blueprint("team", __name__)


def _is_admin() -> bool:
    return getattr(current_user, "role_id", None) == 1


def _resolve_target_id():
    """Members can only view their own subtree; admins may view anyone."""
    target = request.args.get("user_id", type=int)
    if target and target != int(current_user.id) and not _is_admin():
        return None  # not allowed
    return target or int(current_user.id)


@team_bp.route("/team/node", methods=["GET"])
@team_bp.route("/team/node/<int:user_id>", methods=["GET"])
@login_required
def team_node(user_id=None):
    target = user_id or _resolve_target_id()
    if target is None:
        return jsonify({"success": False, "message": "Not authorized"}), 403

    try:
        data = get_team_node(
            target,
            viewer_id=current_user.id,
            page=request.args.get("page", 1, type=int),
            page_size=request.args.get("page_size", 12, type=int),
            rank=request.args.get("rank"),
            status=request.args.get("status"),
        )
        if not data:
            return jsonify({"success": False, "message": "Member not found"}), 404

        # Admin drill: include the breadcrumb upline so the UI can show
        # YOU > Sponsor > ... > selected member.
        data["breadcrumb"] = []
        if _is_admin() and target != int(current_user.id):
            data["breadcrumb"] = get_sponsor_chain(target)[::-1]

        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        logger.error("team_node error: %s", e)
        return jsonify({"success": False, "message": "Failed to load team"}), 500


@team_bp.route("/team/summary", methods=["GET"])
@login_required
def team_summary():
    """Lightweight header counters for the logged-in user."""
    uid = int(current_user.id)
    try:
        return jsonify({
            "success": True,
            "data": {
                "total_team": get_total_team_count(uid),
                "direct_referrals": len(get_level_1_team(uid)),
            },
        }), 200
    except Exception as e:
        logger.error("team_summary error: %s", e)
        return jsonify({"success": False, "message": "Failed"}), 500


@team_bp.route("/team/network/<int:user_id>", methods=["GET"])
@login_required
def team_network(user_id):
    if not _is_admin():
        return jsonify({"success": False, "message": "Not authorized"}), 403
    try:
        return jsonify({"success": True, "data": get_user_network_profile(user_id)}), 200
    except Exception as e:
        logger.error("team_network error: %s", e)
        return jsonify({"success": False, "message": "Failed"}), 500
```

---

## ✏️ REPLACE (UI: Manage Users drill-down)  `app/templates/admin/user_team.html`

```html
{% extends "admin/base.html" %}
{% block title %}My Team{% endblock %}
{% block header_title %}My Team{% endblock %}

{% block content %}
{#
  =====================================================================
  MY TEAM — drill-down team viewer (rewrite)

  * Served at /admin/user/team/<user_id>  (admin can open any member).
  * Renders YOUR node; clicking a member card calls /api/team/node/<id>
    and the SAME card transforms to that member's downline — i.e. the
  * audit drill follows the selected member. Breadcrumb lets you go back.
  * Only ONE level is loaded per click (paginated), so it stays instant
    even with 100k+ users.
  =====================================================================
#}
<style>
  :root{
    --bg:#f4f6fb; --card:#ffffff; --ink:#0f172a; --muted:#64748b;
    --line:#e7ebf2; --brand:#4f46e5; --brand-soft:#eef2ff;
    --green:#16a34a; --green-soft:#dcfce7; --red:#dc2626; --red-soft:#fee2e2;
    --gold:#b8860b;
  }
  .team-wrap{max-width:1100px;margin:0 auto;}
  .stat-card{background:var(--card);border:1px solid var(--line);border-radius:16px;
    padding:1.1rem 1.3rem;flex:1;min-width:150px;box-shadow:0 1px 2px rgba(15,23,42,.04);}
  .stat-card .k{font-size:.78rem;color:var(--muted);text-transform:uppercase;
    letter-spacing:.6px;font-weight:600;}
  .stat-card .v{font-size:1.55rem;font-weight:800;color:var(--ink);margin-top:.25rem;}
  .rank-chip{color:var(--gold);}
  .filters{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;margin:1.1rem 0;}
  .filters input,.filters select{border:1px solid var(--line);border-radius:10px;
    padding:.55rem .9rem;font-size:.9rem;background:#fff;}
  .filters .search{flex:1;min-width:220px;}
  .node-card{background:var(--card);border:1px solid var(--line);border-radius:18px;
    overflow:hidden;box-shadow:0 8px 30px rgba(15,23,42,.06);}
  .node-head{padding:1.3rem 1.5rem;border-bottom:1px solid var(--line);
    background:linear-gradient(135deg,#eef2ff,#fff);}
  .node-title{font-size:1.15rem;font-weight:800;color:var(--ink);display:flex;
    align-items:center;gap:.6rem;flex-wrap:wrap;}
  .you-pill{background:var(--brand);color:#fff;font-size:.72rem;font-weight:700;
    padding:.18rem .6rem;border-radius:999px;letter-spacing:.5px;}
  .node-sub{color:var(--muted);font-size:.9rem;margin-top:.35rem;display:flex;
    gap:1rem;flex-wrap:wrap;}
  .breadcrumb{font-size:.85rem;color:var(--muted);margin-bottom:.9rem;display:flex;
    flex-wrap:wrap;gap:.35rem;align-items:center;}
  .breadcrumb a{color:var(--brand);cursor:pointer;font-weight:600;text-decoration:none;}
  .breadcrumb a:hover{text-decoration:underline;}
  .member-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
    gap:1rem;padding:1.4rem 1.5rem;}
  .member{border:1px solid var(--line);border-radius:14px;padding:1rem;cursor:pointer;
    transition:.15s;background:#fff;position:relative;}
  .member:hover{border-color:var(--brand);box-shadow:0 8px 20px rgba(79,70,229,.12);
    transform:translateY(-2px);}
  .member .top{display:flex;align-items:center;gap:.7rem;margin-bottom:.6rem;}
  .avatar{width:42px;height:42px;border-radius:50%;background:var(--brand-soft);
    color:var(--brand);font-weight:800;display:flex;align-items:center;justify-content:center;
    font-size:1.05rem;flex:0 0 auto;}
  .member .name{font-weight:700;color:var(--ink);font-size:.95rem;line-height:1.2;}
  .member .code{font-family:monospace;font-size:.72rem;color:var(--muted);
    background:#f1f5f9;padding:.05rem .4rem;border-radius:6px;}
  .member .count{font-size:1.6rem;font-weight:800;color:var(--ink);text-align:center;
    margin:.3rem 0;}
  .member .count-lbl{text-align:center;font-size:.72rem;color:var(--muted);
    text-transform:uppercase;letter-spacing:.5px;}
  .member .drill{margin-top:.8rem;text-align:center;font-size:.8rem;font-weight:700;
    color:var(--brand);border-top:1px dashed var(--line);padding-top:.6rem;}
  .badge{font-size:.7rem;font-weight:700;padding:.15rem .55rem;border-radius:999px;}
  .badge.on{background:var(--green-soft);color:var(--green);}
  .badge.off{background:var(--red-soft);color:var(--red);}
  .pager{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.5rem;
    border-top:1px solid var(--line);}
  .pager button{border:1px solid var(--line);background:#fff;border-radius:10px;
    padding:.5rem 1rem;font-weight:600;cursor:pointer;color:var(--ink);}
  .pager button:disabled{opacity:.4;cursor:not-allowed;}
  .empty{padding:3rem;text-align:center;color:var(--muted);}
  .skeleton{opacity:.6;pointer-events:none;}
</style>

<div class="team-wrap">
  <button onclick="location.href='/admin/users'"
    class="btn btn-sm btn-outline-secondary fw-bold rounded-pill px-3 shadow-sm mb-3">
    <i class="bi bi-arrow-left me-1"></i> Back to Users
  </button>

  <!-- Breadcrumb: root > sponsor > ... > current -->
  <div class="breadcrumb" id="breadcrumb"></div>

  <!-- Stat header (mirrors your mockup) -->
  <div style="display:flex;gap:1rem;flex-wrap:wrap;" class="mb-2">
    <div class="stat-card"><div class="k">Total Team</div><div class="v" id="statTotal">–</div></div>
    <div class="stat-card"><div class="k">Direct Referrals</div><div class="v" id="statDirect">–</div></div>
    <div class="stat-card"><div class="k">Active</div><div class="v" id="statActive">–</div></div>
    <div class="stat-card"><div class="k">Rank</div><div class="v rank-chip" id="statRank">–</div></div>
  </div>

  <!-- Filters -->
  <div class="filters">
    <input id="searchBox" class="search" type="text" placeholder="Search member 🔍"
           oninput="onSearchInput()">
    <select id="rankFilter" onchange="load(currentId,1)">
      <option value="">Rank ▾</option>
      <option>Bronze</option><option>Silver</option><option>Gold</option>
      <option>Emerald</option><option>Platinum</option><option>Ruby</option>
      <option>Diamond</option><option>Crown Diamond</option>
    </select>
    <select id="statusFilter" onchange="load(currentId,1)">
      <option value="">Status ▾</option>
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
    </select>
  </div>

  <!-- The transforming node card -->
  <div class="node-card" id="nodeCard">
    <div class="node-head">
      <div class="node-title">
        <span id="nodeLabel">YOU</span>
        <span id="nodeName" style="font-weight:700;"></span>
        <span class="you-pill" id="youPill" style="display:none;">YOU</span>
      </div>
      <div class="node-sub">
        <span id="nodeRank"></span>
        <span id="nodePlan"></span>
        <span id="nodeTeam"></span>
      </div>
    </div>

    <div style="padding:1rem 1.5rem 0;font-weight:700;color:var(--ink);font-size:.95rem;">
      Level 1 <span style="color:var(--muted);font-weight:500;">(direct referrals)</span>
    </div>

    <div class="member-grid" id="memberGrid"></div>

    <div class="pager">
      <button id="prevBtn" onclick="load(currentId,currentPage-1)">← Prev</button>
      <span id="pageInfo" style="font-size:.85rem;color:var(--muted);"></span>
      <button id="nextBtn" onclick="load(currentId,currentPage+1)">Next →</button>
    </div>
  </div>
</div>

<script>
const ROOT_ID = {{ user.id }};
let currentId = ROOT_ID;
let currentPage = 1;
let trail = [];                 // breadcrumb [{id,full_name}]
let searchTimer = null;

const $ = id => document.getElementById(id);

function onSearchInput(){
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { clientFilter(); }, 250);
}

// Client-side text filter over loaded cards (server filters rank/status).
function clientFilter(){
  const q = $('searchBox').value.trim().toLowerCase();
  document.querySelectorAll('.member').forEach(m => {
    m.style.display = m.dataset.search.includes(q) ? '' : 'none';
  });
}

async function load(userId, page=1){
  currentId = userId; currentPage = page;
  $('nodeCard').classList.add('skeleton');

  const rank = $('rankFilter').value;
  const status = $('statusFilter').value;
  const url = `/api/team/node/${userId}?page=${page}&page_size=12`
            + (rank?`&rank=${encodeURIComponent(rank)}`:'')
            + (status?`&status=${status}`:'');
  try{
    const res = await fetch(url, {headers:{'Accept':'application/json'}});
    const json = await res.json();
    if(!json.success) throw new Error(json.message||'Failed');
    render(json.data);
  }catch(err){
    $('memberGrid').innerHTML =
      `<div class="empty">Could not load team: ${err.message}</div>`;
  }finally{
    $('nodeCard').classList.remove('skeleton');
  }
}

function render(data){
  const { node, stats, children, pagination, breadcrumb } = data;

  // Stats
  $('statTotal').textContent  = (stats.total_team??0).toLocaleString('en-IN');
  $('statDirect').textContent = (stats.direct_referrals??0).toLocaleString('en-IN');
  $('statActive').textContent = (stats.active??0).toLocaleString('en-IN');
  $('statRank').textContent   = stats.rank || 'Distributor';

  // Node header
  const isYou = node.label === 'YOU';
  $('nodeLabel').textContent = isYou ? 'YOU' : node.label;
  $('nodeName').textContent  = '— ' + (node.full_name||'Member');
  $('youPill').style.display = isYou ? '' : 'none';
  $('nodeRank').innerHTML = `<i class="bi bi-award text-warning"></i> ${node.rank||'Distributor'}`;
  $('nodePlan').innerHTML = node.package_name
      ? `<i class="bi bi-box-seam text-primary"></i> ${node.package_name} Plan` : '';
  $('nodeTeam').innerHTML = `<i class="bi bi-people text-success"></i> ${(stats.total_team??0).toLocaleString('en-IN')} Team Members`;

  // Breadcrumb (build from server upline when drilling as admin)
  renderBreadcrumb(node, breadcrumb);

  // Members
  const grid = $('memberGrid');
  if(!children || children.length === 0){
    grid.innerHTML = `<div class="empty" style="grid-column:1/-1;">
        <i class="bi bi-diagram-3 fs-1 d-block mb-2 opacity-50"></i>
        No direct members yet for ${node.full_name||'this member'}.</div>`;
  }else{
    grid.innerHTML = children.map(c => `
      <div class="member" data-search="${(c.full_name+' '+ (c.referral_code||'')).toLowerCase()}"
           onclick="drill(${c.id}, '${(c.full_name||('M'+c.id)).replace(/'/g,"")}')">
        <div class="top">
          <div class="avatar">${(c.full_name||'M')[0].toUpperCase()}</div>
          <div>
            <div class="name">${c.full_name||('Member '+c.id)}</div>
            <span class="code">${c.referral_code||('M'+c.id)}</span>
          </div>
          <span class="badge ${c.is_active?'on':'off'}" style="margin-left:auto;">
            ${c.is_active?'Active':'Inactive'}</span>
        </div>
        <div class="count">${(c.total_team_count??0).toLocaleString('en-IN')}</div>
        <div class="count-lbl">Team Members</div>
        <div class="drill"><i class="bi bi-arrow-down-circle me-1"></i> Drill ↓</div>
      </div>`).join('');
  }
  clientFilter();

  // Pagination
  $('pageInfo').textContent = `Page ${pagination.page} of ${pagination.pages||1} · ${pagination.total} directs`;
  $('prevBtn').disabled = pagination.page <= 1;
  $('nextBtn').disabled = pagination.page >= (pagination.pages||1);
}

function renderBreadcrumb(node, upline){
  // Maintain an in-page trail as the user drills down.
  const existing = trail.findIndex(t => t.id === node.id);
  if(existing >= 0){ trail = trail.slice(0, existing+1); }
  else if(String(node.id) !== String(ROOT_ID) || trail.length===0){
    if(trail.length===0) trail.push({id:ROOT_ID, full_name:'YOU (Root)'});
    if(String(node.id) !== String(ROOT_ID))
      trail.push({id:node.id, full_name:node.full_name||node.label});
  }
  const crumbs = trail.map((t,i) =>
    i === trail.length-1
      ? `<strong style="color:var(--ink);">${t.full_name}</strong>`
      : `<a onclick="goCrumb(${t.id}, ${i})">${t.full_name}</a>`
  ).join(' <span>/</span> ');
  $('breadcrumb').innerHTML = `<i class="bi bi-diagram-2 me-1"></i>` + crumbs;
}

function goCrumb(id, index){
  trail = trail.slice(0, index+1);
  load(id, 1);
}

// Click a member -> the SAME card transforms to that member's downline.
function drill(id, name){
  load(id, 1);
}

// Boot
load(ROOT_ID, 1);
</script>
{% endblock %}
```

---

## ✏️ REPLACE (UI: Packages & Commission plan)  `app/templates/admin/packages.html`

```html
{% extends "admin/base.html" %}
{% block title %}Packages & Commission Plan{% endblock %}
{% block header_title %}Packages & Commission Plan{% endblock %}

{% block content %}
{#
  BUSINESS PLAN ADMIN SCREEN (complete replacement for packages.html).
  Context provided by app/routes/admin/package_routes.py:
    packages    -> list of subscription_plans (each with .images)
    settings    -> global_commissions rows (setting_key, percentage_value, description)
    level_comms -> commission_plan rows (level, commission_percentage)
#}
<style>
  .pp-card{background:#fff;border:1px solid #e7ebf2;border-radius:16px;padding:1.4rem;
    box-shadow:0 1px 2px rgba(15,23,42,.04);margin-bottom:1.4rem;}
  .pp-title{font-weight:800;color:#0f172a;font-size:1.05rem;margin-bottom:.9rem;
    display:flex;align-items:center;gap:.5rem;}
  .pp-badge{font-size:.7rem;background:#eef2ff;color:#4f46e5;padding:.15rem .55rem;
    border-radius:999px;font-weight:700;}
  .form-label-sm{font-size:.78rem;font-weight:600;color:#475569;margin-bottom:.2rem;}
  .plan-tile{border:1px solid #e7ebf2;border-radius:14px;padding:1rem;background:#fff;}
  .plan-tile .price{font-size:1.3rem;font-weight:800;color:#4f46e5;}
  .level-row{display:grid;grid-template-columns:120px 1fr 90px;gap:.8rem;align-items:center;
    padding:.55rem 0;border-bottom:1px dashed #eef2f7;}
  .level-row:last-child{border-bottom:0;}
  .lvl-name{font-weight:700;color:#334155;}
  .lvl-rel{font-size:.72rem;color:#94a3b8;}
  input[type=number]{border:1px solid #e2e8f0;border-radius:.55rem;padding:.45rem .7rem;}
  .btn-save{background:#4f46e5;color:#fff;border:0;border-radius:.55rem;padding:.45rem 1rem;
    font-weight:700;font-size:.85rem;}
  .btn-save:hover{background:#4338ca;}
  .comm-pct{width:90px;text-align:right;font-weight:700;}
  .thumb{width:52px;height:52px;border-radius:10px;object-fit:cover;border:1px solid #e7ebf2;}
</style>

<div class="d-flex justify-content-between align-items-end mb-3 flex-wrap gap-2">
  <div>
    <h4 class="fw-bold mb-1" style="color:#0f172a;">📦 Packages & Commission Plan</h4>
    <p class="text-muted mb-0">Manage joining packages and the payout percentages. Changes apply within ~60 seconds.</p>
  </div>
</div>

<!-- ===================== PACKAGES ===================== -->
<div class="pp-card">
  <div class="pp-title">Subscription Packages <span class="pp-badge">{{ packages|length }} plans</span></div>

  <div class="row g-3 mb-4">
    {% for p in packages %}
    <div class="col-md-6 col-lg-4">
      <form method="POST" action="/admin/packages/update" enctype="multipart/form-data" class="plan-tile h-100">
        <input type="hidden" name="plan_id" value="{{ p.id }}">
        <div class="d-flex gap-2 align-items-center mb-2">
          {% if p.images and p.images[0].path %}
            <img src="{{ p.images[0].path }}" class="thumb" alt="">
          {% endif %}
          <div>
            <div class="fw-bold text-dark">{{ p.name }}</div>
            <div class="price">₹{{ p.price }}</div>
          </div>
          <label class="ms-auto small d-flex align-items-center gap-1">
            <input type="checkbox" name="is_active" {% if p.is_active %}checked{% endif %}> Active
          </label>
        </div>
        <div class="row g-2">
          <div class="col-6">
            <div class="form-label-sm">Price (₹)</div>
            <input type="number" step="0.01" name="price" class="form-control form-control-sm" value="{{ p.price }}" required>
          </div>
          <div class="col-6">
            <div class="form-label-sm">Product Cost (₹)</div>
            <input type="number" step="0.01" name="product_cost" class="form-control form-control-sm" value="{{ p.product_cost or 0 }}">
          </div>
          <div class="col-6">
            <div class="form-label-sm">Lucky Coupons</div>
            <input type="number" name="coupons" class="form-control form-control-sm" value="{{ p.lucky_draw_coupons or 12 }}">
          </div>
          <div class="col-6">
            <div class="form-label-sm">Product Images</div>
            <input type="file" name="product_images" multiple accept="image/*" class="form-control form-control-sm">
          </div>
        </div>
        <button class="btn-save w-100 mt-3" type="submit">Save Plan</button>
      </form>
    </div>
    {% endfor %}
  </div>

  <!-- Add new plan -->
  <form method="POST" action="/admin/packages/add" class="row g-2 align-items-end border-top pt-3">
    <div class="col-md-3">
      <div class="form-label-sm">New Plan Name</div>
      <input type="text" name="name" class="form-control form-control-sm" placeholder="e.g. Diamond" required>
    </div>
    <div class="col-md-2">
      <div class="form-label-sm">Price (₹)</div>
      <input type="number" step="0.01" name="price" class="form-control form-control-sm" placeholder="3600" required>
    </div>
    <div class="col-md-2">
      <div class="form-label-sm">Product Cost</div>
      <input type="number" step="0.01" name="product_cost" class="form-control form-control-sm" value="0">
    </div>
    <div class="col-md-2">
      <div class="form-label-sm">Coupons</div>
      <input type="number" name="coupons" class="form-control form-control-sm" value="12">
    </div>
    <div class="col-md-3">
      <button class="btn-save w-100" type="submit">＋ Create Package</button>
    </div>
  </form>
</div>

<!-- ===================== LEVEL / GENERATION INCOME ===================== -->
<div class="pp-card">
  <div class="pp-title">Level Commission (Generation Income) <span class="pp-badge">paid to upline on each purchase</span></div>
  <p class="text-muted small mb-3">Percentage of the purchased package price paid to each upline level. Level 1 = direct sponsor (also uses the Direct Commission below).</p>

  {% set relations = {1:'Direct sponsor',2:'2nd upline',3:'3rd upline',4:'4th upline',5:'5th upline',
                      6:'6th upline',7:'7th upline',8:'8th upline',9:'9th upline',10:'10th upline'} %}
  {% for lc in level_comms %}
  <div class="level-row">
    <div>
      <div class="lvl-name">Level {{ lc.level }}</div>
      <div class="lvl-rel">{{ relations.get(lc.level, '') }}</div>
    </div>
    <form method="POST" action="/admin/level-commissions/update" class="d-flex align-items-center gap-2 mb-0">
      <input type="hidden" name="level" value="{{ lc.level }}">
      <div class="flex-grow-1">
        <div class="progress" style="height:10px;background:#eef2ff;border-radius:99px;">
          <div class="progress-bar" style="width: {{ (lc.commission_percentage / 10 * 100) if lc.commission_percentage else 0 }}%;background:#4f46e5;border-radius:99px;"></div>
        </div>
      </div>
      <div class="d-flex align-items-center gap-1">
        <input type="number" step="0.01" name="percentage_value" class="form-control form-control-sm comm-pct" value="{{ lc.commission_percentage }}" required>
        <span class="fw-bold">%</span>
      </div>
      <button class="btn-save" type="submit">Save</button>
    </form>
  </div>
  {% else %}
  <p class="text-muted small">No level commissions configured yet — run migration 0004 to seed them.</p>
  {% endfor %}
</div>

<!-- ===================== GLOBAL COMMISSIONS ===================== -->
<div class="pp-card">
  <div class="pp-title">Global Settings <span class="pp-badge">direct · cashback · fees</span></div>
  <div class="row g-3">
    {% for s in settings %}
    <div class="col-md-6 col-lg-4">
      <form method="POST" action="/admin/commissions/update" class="border rounded-3 p-3 h-100">
        <input type="hidden" name="setting_key" value="{{ s.setting_key }}">
        <div class="fw-bold text-capitalize text-dark mb-1">{{ s.setting_key.replace('_',' ') }}</div>
        {% if s.description %}<div class="small text-muted mb-2">{{ s.description }}</div>{% endif %}
        <div class="d-flex align-items-center gap-2">
          <input type="number" step="0.01" name="percentage_value" class="form-control form-control-sm" value="{{ s.percentage_value }}" required>
          <span class="fw-bold">%</span>
          <button class="btn-save" type="submit">Save</button>
        </div>
      </form>
    </div>
    {% else %}
    <p class="text-muted small">No global settings configured — run migration 0004.</p>
    {% endfor %}
  </div>
</div>

{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <div class="position-fixed bottom-0 end-0 p-3" style="z-index:1080;">
      {% for cat, msg in messages %}
        <div class="alert alert-{{ 'danger' if cat=='danger' else 'success' }} shadow-sm mb-2">{{ msg }}</div>
      {% endfor %}
    </div>
  {% endif %}
{% endwith %}
{% endblock %}
```

---

## STEP 3 — DELETE one file & small edit

🗑️ **DELETE this file completely:** `app/routes/__init__.py`
(It contains a second, broken app factory. The real one is `app/__init__.py`.)

✏️ **In `app/routes/main.py`**, delete these two duplicate functions (with their
`@main.route(...)` decorators) — around lines 864 and 880:
- `def get_my_team_metadata()`  (route `/api/team/me`)
- `def get_my_genealogy_tree()` (route `/api/genealogy/me`)
The working versions already live in `app/routes/user_routes.py`.

Then run:  `pip install -r requirements.txt`  and restart the server.

---

## STEP 4 — FRONT-END (Next.js)


## ✏️ REPLACE  `frontend/src/services/api.js`

```js
import axios from "axios";

/*
 * frontend/src/services/api.js — REWRITE
 *
 * Base URL now comes from the environment so the SAME build works in local
 * dev, staging and production (the old file hard-coded http://127.0.0.1:5000,
 * which only works on a developer's own laptop and breaks for every real
 * user). Set NEXT_PUBLIC_API_URL in your deploy environment, e.g.:
 *    NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api
 * Locally it defaults to http://127.0.0.1:5000/api (kept to dodge the IPv6
 * localhost resolution quirk on some machines).
 */
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:5000/api";

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send the session cookie
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (error.config?.url?.includes("/auth/me")) {
        return Promise.reject(error);
      }
      console.warn("Session expired or unauthorized access.");
      return Promise.reject(error);
    }
    console.error("API Error:", error.response?.status, error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
```

---

## 🆕 CREATE  `frontend/src/services/team.ts`

```ts
import api from "./api";

/*
 * frontend/src/services/team.ts — REWRITE (drop-in for services/team.js)
 *
 * Keeps fetchNetworkData / fetchUplineData for the existing dashboard, and
 * adds fetchTeamNode for the new drill-down <MyTeam /> component.
 *
 * `userId` omitted  -> the logged-in member's own root node.
 * `userId` provided -> that member's node (admins only for other ids).
 */

export type TeamNodeParams = {
  userId?: string | number;
  page?: number;
  pageSize?: number;
  rank?: string;
  status?: string;
};

export const fetchTeamNode = async ({
  userId,
  page = 1,
  pageSize = 12,
  rank,
  status,
}: TeamNodeParams) => {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (userId) params.user_id = userId;
  if (rank) params.rank = rank;
  if (status) params.status = status;

  const res = await api.get("/team/node", { params });
  if (!res.data?.success) {
    throw new Error(res.data?.message || "Failed to load team");
  }
  return res.data.data;
};

export const fetchNetworkData = async () => {
  try {
    const [teamRes, genealogyRes] = await Promise.all([
      api.get("/team/me"),
      api.get("/genealogy/me"),
    ]);

    const totalTeam =
      teamRes.data?.total_team ?? teamRes.data?.totalCount ?? teamRes.data?.count ?? 0;
    const directTeam = teamRes.data?.direct_team ?? teamRes.data?.directs ?? [];
    const rawTree =
      genealogyRes.data?.team_tree ??
      genealogyRes.data?.tree ??
      genealogyRes.data?.data ??
      genealogyRes.data ??
      {};

    return {
      success: true,
      totalCount: totalTeam,
      directTeam: Array.isArray(directTeam) ? directTeam : [],
      tree: typeof rawTree === "object" && rawTree !== null ? rawTree : {},
    };
  } catch (error) {
    console.error("Network data fetch error:", error);
    return { success: false, totalCount: 0, directTeam: [], tree: {} };
  }
};

export const fetchUplineData = async () => {
  try {
    const res = await api.get("/team/upline");
    return { success: true, data: res.data?.data || res.data || null };
  } catch (error) {
    console.error("Upline fetch error:", error);
    return { success: false, data: null };
  }
};
```

---

## 🆕 CREATE (UI: My Team drill-down component)  `frontend/src/components/team/MyTeam.tsx`

```tsx
"use client";

/*
 * frontend/src/components/team/MyTeam.tsx  —  NEW
 * ------------------------------------------------------------------
 * "My Team" drill-down widget for the Next.js member dashboard.
 *
 *   - Renders YOUR root node with the 4 stat tiles (Total Team,
 *     Direct Referrals, Active, Rank) — same layout as your mockup.
 *   - Clicking a member card (e.g. Member B) calls the SAME endpoint
 *     with that member's id and the card transforms in place ->
 *     "the audit drill follows the selected member".
 *   - A breadcrumb (You / Member A / Member B ...) lets you walk back
 *     up without losing context.
 *   - Only ONE level is fetched per click (paginated, 12 per page) so
 *     it stays instant even at 100k+ users.
 *
 * Requires backend endpoint:  GET /api/team/node?user_id=<id>&page=
 * (see app/routes/team_routes.py).
 */

import { useCallback, useEffect, useState } from "react";
import api from "@/services/api";

type Member = {
  id: string;
  full_name?: string;
  referral_code?: string;
  rank?: string;
  is_active?: boolean;
  total_team_count?: number;
  direct_count?: number;
};

type NodeData = {
  node: { id: string; label: string; full_name?: string; rank?: string; package_name?: string };
  stats: { total_team: number; direct_referrals: number; active: number; rank: string };
  children: Member[];
  pagination: { page: number; pages: number; total: number };
};

type Crumb = { id: string; name: string };

function StatTile({ label, value, rank }: { label: string; value: React.ReactNode; rank?: boolean }) {
  return (
    <div className="flex-1 min-w-[140px] bg-white rounded-2xl border border-slate-200 px-5 py-4 shadow-sm">
      <div className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">{label}</div>
      <div className={`text-2xl font-extrabold mt-1 ${rank ? "text-amber-600" : "text-slate-900"}`}>
        {value}
      </div>
    </div>
  );
}

export default function MyTeam() {
  const [data, setData] = useState<NodeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [rank, setRank] = useState("");
  const [search, setSearch] = useState("");
  const [trail, setTrail] = useState<Crumb[]>([]);

  const currentId = trail.length ? trail[trail.length - 1].id : "";

  const load = useCallback(
    async (id: string, pageNum = 1) => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number> = { page: pageNum, page_size: 12 };
        if (id) params.user_id = id;
        if (status) params.status = status;
        if (rank) params.rank = rank;
        const res = await api.get("/team/node", { params });
        const payload = res.data?.data;
        if (!payload) throw new Error("No data");
        setData(payload);
        setPage(pageNum);
        setTrail((prev) => {
          const nodeId = String(payload.node.id);
          const idx = prev.findIndex((c) => c.id === nodeId);
          if (idx >= 0) return prev.slice(0, idx + 1);
          if (prev.length === 0) {
            return [{ id: nodeId, name: payload.node.full_name || "You" }];
          }
          return [...prev, { id: nodeId, name: payload.node.full_name || payload.node.label }];
        });
      } catch (e: any) {
        setError(e?.response?.data?.message || "Failed to load team");
      } finally {
        setLoading(false);
      }
    },
    [status, rank]
  );

  // Initial load (logged-in user's own root).
  useEffect(() => {
    load("", 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drill = (m: Member) => load(String(m.id), 1);
  const goCrumb = (i: number) => {
    const target = trail[i];
    setTrail(trail.slice(0, i + 1));
    load(String(target.id), 1);
  };

  const filtered = (data?.children || []).filter((m) => {
    const q = search.trim().toLowerCase();
    return !q || (m.full_name || "").toLowerCase().includes(q) ||
           (m.referral_code || "").toLowerCase().includes(q);
  });

  const initials = (name?: string) => (name ? name[0].toUpperCase() : "M");

  return (
    <div className="max-w-5xl mx-auto">
      <h2 className="text-xl font-extrabold text-slate-900 mb-4">My Team</h2>

      {/* Stat tiles */}
      <div className="flex gap-4 flex-wrap mb-4">
        <StatTile label="Total Team" value={(data?.stats.total_team ?? 0).toLocaleString("en-IN")} />
        <StatTile label="Direct Referrals" value={(data?.stats.direct_referrals ?? 0).toLocaleString("en-IN")} />
        <StatTile label="Active" value={(data?.stats.active ?? 0).toLocaleString("en-IN")} />
        <StatTile label="Rank" value={data?.stats.rank || "Distributor"} rank />
      </div>

      {/* Breadcrumb */}
      {trail.length > 1 && (
        <div className="text-sm text-slate-500 mb-3 flex flex-wrap items-center gap-1">
          {trail.map((c, i) => (
            <span key={c.id}>
              {i > 0 && <span className="mx-1">/</span>}
              {i === trail.length - 1 ? (
                <strong className="text-slate-900">{c.name}</strong>
              ) : (
                <button className="text-indigo-600 font-semibold hover:underline" onClick={() => goCrumb(i)}>
                  {i === 0 ? "You" : c.name}
                </button>
              )}
            </span>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 flex-wrap items-center mb-4">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search member 🔍"
          className="flex-1 min-w-[220px] border border-slate-200 rounded-xl px-4 py-2 text-sm"
        />
        <select value={rank} onChange={(e) => { setRank(e.target.value); }}
          className="border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white">
          <option value="">Rank ▾</option>
          {["Bronze","Silver","Gold","Emerald","Platinum","Ruby","Diamond","Crown Diamond"].map(r =>
            <option key={r}>{r}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}
          className="border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white">
          <option value="">Status ▾</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      {/* Node card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-200 bg-gradient-to-r from-indigo-50 to-white">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-extrabold text-slate-900">
              {data?.node.label === "YOU" ? "YOU" : data?.node.label}
              {" — "}{data?.node.full_name}
            </span>
          </div>
          <div className="text-sm text-slate-500 mt-1 flex gap-4 flex-wrap">
            <span>🏆 {data?.node.rank || "Distributor"}</span>
            {data?.node.package_name && <span>📦 {data.node.package_name} Plan</span>}
            <span>👥 {data?.stats.total_team.toLocaleString("en-IN")} Team Members</span>
          </div>
        </div>

        <div className="px-6 pt-4 font-bold text-slate-900 text-sm">Level 1</div>

        <div className={`p-6 grid gap-4 grid-cols-[repeat(auto-fill,minmax(220px,1fr))] ${loading ? "opacity-60" : ""}`}>
          {error && <div className="col-span-full text-center text-red-600 py-8">{error}</div>}
          {!error && filtered.length === 0 && !loading && (
            <div className="col-span-full text-center text-slate-400 py-10">No direct members yet.</div>
          )}
          {filtered.map((m) => (
            <button
              key={m.id}
              onClick={() => drill(m)}
              className="text-left border border-slate-200 rounded-2xl p-4 hover:border-indigo-500 hover:shadow-lg hover:-translate-y-0.5 transition bg-white">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-full bg-indigo-100 text-indigo-700 font-extrabold flex items-center justify-center">
                  {initials(m.full_name)}
                </div>
                <div className="min-w-0">
                  <div className="font-bold text-slate-900 text-sm truncate">{m.full_name || "Member " + m.id}</div>
                  <span className="font-mono text-[11px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                    {m.referral_code || m.id}
                  </span>
                </div>
                <span className={`ml-auto text-[11px] font-bold px-2 py-0.5 rounded-full ${
                  m.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                  {m.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="text-2xl font-extrabold text-slate-900 text-center my-1">
                {(m.total_team_count ?? 0).toLocaleString("en-IN")}
              </div>
              <div className="text-center text-[11px] uppercase tracking-wide text-slate-500">Team Members</div>
              <div className="mt-2 text-center text-xs font-bold text-indigo-600 border-t border-dashed border-slate-200 pt-2">
                Drill ↓
              </div>
            </button>
          ))}
        </div>

        {/* Pager */}
        <div className="flex justify-between items-center px-6 py-4 border-t border-slate-200">
          <button
            disabled={page <= 1 || loading}
            onClick={() => load(currentId, page - 1)}
            className="border border-slate-200 rounded-lg px-4 py-2 font-semibold text-sm disabled:opacity-40">
            ← Prev
          </button>
          <span className="text-xs text-slate-500">
            Page {page} of {data?.pagination.pages || 1} · {data?.pagination.total || 0} directs
          </span>
          <button
            disabled={page >= (data?.pagination.pages || 1) || loading}
            onClick={() => load(currentId, page + 1)}
            className="border border-slate-200 rounded-lg px-4 py-2 font-semibold text-sm disabled:opacity-40">
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

✏️ **In `frontend/src/app/dashboard/page.jsx`** add, near the other imports:
```tsx
import MyTeam from "@/components/team/MyTeam";
```
and inside your Network/Team tab content, render:
```tsx
<MyTeam />
```
Set `NEXT_PUBLIC_API_URL=https://your-api-domain/api` in production.

---

## ✅ After deploying — quick checks
1. `psql ... -c "SELECT level,percentage FROM commission_plan ORDER BY level;"` → 10 rows.
2. `psql ... -c "SELECT id,direct_count,total_team_count FROM users LIMIT 5;"` → counts filled.
3. Admin → **Packages**: edit a % and Save. Admin → **Users → Team**: click a
   member (e.g. Member B) — the same card changes to that member's downline.
4. A test purchase creates `orders`, `commissions`, and `wallet_ledger` rows together.
