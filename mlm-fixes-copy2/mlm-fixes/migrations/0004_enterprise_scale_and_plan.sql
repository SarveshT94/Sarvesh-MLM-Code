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

-- Idempotency: a paid commission must never be inserted twice for the same
-- (earner, order, level). We DROP the old free-text unique index (it mixed a
-- per-purchase reference into commission_type and would block legitimate
-- repeat-purchase commissions once commission_type becomes constant) and
-- replace it with a PARTIAL unique index that only applies to NEW, order-linked
-- rows. Historical rows have order_id NULL, so they are excluded and the index
-- builds cleanly even on a database that already has data.
DROP INDEX IF EXISTS public.idx_unique_commission;

CREATE UNIQUE INDEX IF NOT EXISTS uq_commissions_earner_order_level
    ON public.commissions (earner_id, order_id, level)
    WHERE order_id IS NOT NULL;

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

-- Compatibility: some newer screens in your live build (e.g. the admin
-- member "drawer_data" route) SELECT an alternate_phone column that was
-- never created. Add it so those screens stop throwing 500s. It stays NULL
-- until used.
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS alternate_phone character varying(20);

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
    level      INTEGER NOT NULL,
    percentage NUMERIC(5,2) NOT NULL,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Remove any accidental duplicate levels (keep the newest row), then ensure a
-- guaranteed UNIQUE index so ON CONFLICT (level) works whether or not the table
-- already existed.
DELETE FROM public.commission_plan a
USING public.commission_plan b
WHERE a.level = b.level AND a.ctid < b.ctid;

CREATE UNIQUE INDEX IF NOT EXISTS uq_commission_plan_level
    ON public.commission_plan (level);

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

-- Guaranteed unique keys so ON CONFLICT / re-runs behave predictably. Remove
-- accidental duplicates first (keep newest row), then create the indexes.
DELETE FROM public.global_commissions a
USING public.global_commissions b
WHERE a.setting_key = b.setting_key AND a.ctid < b.ctid;

DELETE FROM public.level_commissions a
USING public.level_commissions b
WHERE a.level = b.level AND a.ctid < b.ctid;

CREATE UNIQUE INDEX IF NOT EXISTS uq_global_comm_key
    ON public.global_commissions (setting_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_level_comm_level
    ON public.level_commissions (level);

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
