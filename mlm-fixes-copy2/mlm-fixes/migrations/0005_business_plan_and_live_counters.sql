-- ============================================================================
--  RK TRENDZ MLM :: 0005 — LIVE TEAM COUNTERS + CANONICAL BUSINESS PLAN
--  Idempotent. Safe to run on a live database. Data is preserved.
-- ----------------------------------------------------------------------------
--  Does two things:
--   (A) Adds a trigger so that EVERY new registration automatically updates the
--       sponsor's direct_count and the WHOLE upline's total_team_count. This is
--       what guarantees the genealogy chain keeps growing and never breaks or
--       shows stale counts for new joiners. (0004 built the columns/tree for
--       existing users; this keeps them correct forever.)
--   (B) Seeds/upserts the EXACT business plan from the RK Trendz PDF:
--         - 5 subscription packages
--         - global commissions (direct 10%, self/repurchase cashback 5%,
--           repurchase referral 10%, admin fee 10%, TDS 10%)
--         - level generation income L1=10% (direct) + L2..L10 = 15% pool
--         - 8 dynamic ranks Bronze -> Crown Diamond
-- ============================================================================

-- ===========================================================================
-- (A) LIVE COUNTER MAINTENANCE ON EVERY NEW SIGNUP
-- ===========================================================================
CREATE OR REPLACE FUNCTION public.after_user_insert_counters()
RETURNS TRIGGER AS $fn$
BEGIN
    -- +1 direct referral for the immediate sponsor
    IF NEW.sponsor_id IS NOT NULL THEN
        UPDATE public.users
           SET direct_count = direct_count + 1
         WHERE id = NEW.sponsor_id;
    END IF;

    -- +1 total team for EVERY ancestor (the whole upline chain), using ltree.
    -- NEW.tree_path <@ u.tree_path  => u is an ancestor of the new user.
    IF NEW.tree_path IS NOT NULL THEN
        UPDATE public.users u
           SET total_team_count = total_team_count + 1
         WHERE u.tree_path IS NOT NULL
           AND NEW.tree_path <@ u.tree_path
           AND u.id <> NEW.id;
    END IF;

    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_insert_counters ON public.users;
CREATE TRIGGER trg_user_insert_counters
    AFTER INSERT ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.after_user_insert_counters();

-- Recalculate every counter once so current data is correct.
SELECT public.refresh_user_counters();

-- ===========================================================================
-- (B) CANONICAL BUSINESS PLAN (per the supplied PDF) — UPSERT, idempotent
-- ===========================================================================

-- ---- B1. Subscription packages ----
INSERT INTO public.subscription_plans (id, name, price, lucky_draw_coupons, is_active, product_cost)
VALUES
    (1, 'Starter',   1800.00,  12, TRUE, 0),
    (2, 'Bronze',    3600.00,  12, TRUE, 0),
    (3, 'Silver',    7200.00,  12, TRUE, 0),
    (4, 'Gold',     14400.00,  12, TRUE, 0),
    (5, 'Platinum', 28800.00,  12, TRUE, 0)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    price = EXCLUDED.price,
    lucky_draw_coupons = EXCLUDED.lucky_draw_coupons,
    is_active = TRUE;
SELECT setval(pg_get_serial_sequence('public.subscription_plans','id'),
              (SELECT COALESCE(MAX(id),1) FROM public.subscription_plans));

-- ---- B2. Global commissions ----
INSERT INTO public.global_commissions (setting_key, percentage_value, description) VALUES
    ('direct_commission',    10.00, 'Direct sponsor commission (%) on package purchase'),
    ('direct_referral',      10.00, 'Direct referral income (Level 1)'),
    ('self_cashback',         5.00, 'Cashback to buyer on own purchase'),
    ('repurchase_cashback',   5.00, 'Cashback on repurchases'),
    ('repurchase_referral',  10.00, 'Sponsor commission on repurchase'),
    ('admin_fee_percentage', 10.00, 'Admin/processing fee on withdrawal'),
    ('tds_percentage',       10.00, 'TDS deducted on withdrawal')
ON CONFLICT (setting_key) DO UPDATE
SET percentage_value = EXCLUDED.percentage_value,
    description = EXCLUDED.description;

-- ---- B3. Level generation income ----
-- The original commission_plan table may predate the is_active column; add it.
ALTER TABLE public.commission_plan ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- L1 = 10% direct. L2..L10 = 3 / 2.5 / 2 / 1.5 / 1.5 / 1.5 / 1 / 1 / 1 (15% pool).
INSERT INTO public.commission_plan (level, percentage, is_active) VALUES
    (1, 10.00, TRUE),
    (2,  3.00, TRUE),
    (3,  2.50, TRUE),
    (4,  2.00, TRUE),
    (5,  1.50, TRUE),
    (6,  1.50, TRUE),
    (7,  1.50, TRUE),
    (8,  1.00, TRUE),
    (9,  1.00, TRUE),
    (10, 1.00, TRUE)
ON CONFLICT (level) DO UPDATE
SET percentage = EXCLUDED.percentage, is_active = TRUE;

-- Mirror into the legacy level_commissions table (same column the UI reads).
INSERT INTO public.level_commissions (level, commission_percentage) VALUES
    (1,10.00),(2,3.00),(3,2.50),(4,2.00),(5,1.50),
    (6,1.50),(7,1.50),(8,1.00),(9,1.00),(10,1.00)
ON CONFLICT (level) DO UPDATE
SET commission_percentage = EXCLUDED.commission_percentage;

-- ---- B4. Dynamic rank rules (Bronze -> Crown Diamond) ----
DELETE FROM public.rank_rules a
USING public.rank_rules b
WHERE a.level = b.level AND a.ctid < b.ctid;
CREATE UNIQUE INDEX IF NOT EXISTS uq_rank_rules_level ON public.rank_rules (level);

INSERT INTO public.rank_rules (level, rank_name, req_team_size, req_business_vol, bonus_percentage) VALUES
    (1, 'Bronze',         10,   50000.00, 2.00),
    (2, 'Silver',         25,  200000.00, 1.50),
    (3, 'Gold',          100,  500000.00, 1.00),
    (4, 'Emerald',       200,  700000.00, 1.00),
    (5, 'Platinum',      250,  850000.00, 1.00),
    (6, 'Ruby',          350, 1000000.00, 1.00),
    (7, 'Diamond',       450, 1200000.00, 1.00),
    (8, 'Crown Diamond', 550, 1500000.00, 1.00)
ON CONFLICT (level) DO UPDATE
SET rank_name       = EXCLUDED.rank_name,
    req_team_size   = EXCLUDED.req_team_size,
    req_business_vol= EXCLUDED.req_business_vol,
    bonus_percentage= EXCLUDED.bonus_percentage;

-- ---- B5. Extra member profile fields (from the team/architecture reference) ----
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS dob          date;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS address      text;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS city         character varying(80);
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS state        character varying(80);
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS pincode      character varying(12);
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS designation  character varying(60);

-- ===========================================================================
-- VERIFY:
--   SELECT name, price FROM subscription_plans ORDER BY id;            -- 5 rows
--   SELECT level, percentage FROM commission_plan ORDER BY level;      -- 10 rows
--   SELECT level, rank_name, req_team_size, req_business_vol FROM rank_rules ORDER BY level; -- 8
--   -- trigger test: insert a test user under a sponsor, sponsor's direct_count rises by 1
-- ===========================================================================
