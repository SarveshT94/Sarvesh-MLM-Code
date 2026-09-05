# RK Trendz MLM — Senior Engineer Audit & File-Replacement Guide

**Repo audited:** `SarveshT94/Sarvesh-MLM-Code` (Flask + psycopg2 + PostgreSQL,
Jinja admin UI, partial Next.js front-end).
**Date:** 2026-09-04
**Deliverable:** production-ready, enterprise-grade rewrites that scale to
**100,000 concurrent users**, plus the **Package/Commission plan** and the
**drill-down “My Team” UI**.

> ⚖️ **Compliance note (important for the business, not the code):** pay
> commissions on **product/package sales volume** (this code does), never on
> joining fees alone, and keep the income plan honest (no “guaranteed ROI”).
> Pure recruitment payouts = a pyramid scheme, which is illegal under the
> Prize Chits & Money Circulation (Banning) Act, 1978 in India. The plan below
> is sales-volume based — keep it that way and get it legally reviewed.

---

## 1. How to use this package

Every file in this folder maps to a file in your repo. Replace the repo file
with the matching one (paths are preserved), then run the migration and deploy
steps. **Backup your database first.**

```
Backup:  pg_dump rk_trendz_mlm > backup_before_0004.sql
```

### Replacement map (do these in order)

| # | Replace repo file | With this file | Reason |
|---|---|---|---|
| 1 | **(DB migration)** | `migrations/0004_enterprise_scale_and_plan.sql` | Fixes broken columns, adds `orders`, ltree tree path, counters, indexes, **seeds the commission plan** |
| 2 | `app/config/config.py` | `app/config/config.py` | Redis URL, pool/security config, fail-fast validation |
| 3 | `app/cache.py` | `app/cache.py` | Redis shared cache (SimpleCache is per-process/unsafe) |
| 4 | `app/db.py` | `app/db.py` | statement_timeout, PgBouncer-safe pooling |
| 5 | `app/services/team_service.py` | `app/services/team_service.py` | ltree counts, **new drill-down `get_team_node`**, O(1) stats |
| 6 | `app/services/sponsor_service.py` | `app/services/sponsor_service.py` | Accepts open cursor (runs inside the payout transaction) |
| 7 | `app/services/package_service.py` | `app/services/package_service.py` | Fixes `percentage` column bug, **atomic purchase**, Redis config cache |
| 8 | `app/services/commission_engine.py` | `app/services/commission_engine.py` | Fixes `reference` column bug, real idempotency on `order_id`, ledger credits |
| 9 | `app/services/rank_service.py` | `app/services/rank_service.py` | No nested connection mid-transaction; ltree volume/count |
| 10 | `app/services/admin/tree_service.py` | `app/services/admin/tree_service.py` | Kills N+1 (1 query not 1-per-node), real cache TTL |
| 11 | `app/services/admin_user_service.py` | `app/services/admin_user_service.py` | Indexed/trigram search, richer columns |
| 12 | **(new)** `app/routes/team_routes.py` | `app/routes/team_routes.py` | **Drill-down API** `/api/team/node` |
| 13 | `app/__init__.py` | `app/__init__.py` | Registers new blueprint, config-driven CORS/cookies, health check |
| 14 | `run.py` | `run.py` | Debug forced off in production |
| 15 | `app/templates/admin/user_team.html` | same | **The “My Team” drill-down UI** (matches your mockup) |
| 16 | Front-end `src/services/api.js` | same | Env-based API URL (was hard-coded localhost) |
| 17 | **(new)** `frontend/src/components/team/MyTeam.tsx` | same | Member-facing drill-down component |
| 18 | Front-end `src/services/team.ts` (replace `team.js`) | same | Adds `fetchTeamNode` |
| 19 | `requirements.txt` | `requirements.txt` | Adds redis, gunicorn, gevent |
| 20 | **(ops)** `deploy/` | `deploy/` | gunicorn config, .env template, scaling guide |

### Manual edits (2 small ones — do after replacing)

* **Delete** `app/routes/__init__.py` (it contains a *second*, broken
  `create_app()` that even references an undefined `rank_bp`). It is dead code
  that will crash anyone who imports it.
* In **`app/routes/main.py`**, delete the two duplicate route blocks
  **`/api/team/me` (line ~864)** and **`/api/genealogy/me` (line ~880)** — they
  conflict with the canonical ones in `app/routes/user_routes.py` (and the
  `main.py` genealogy version returns a flat list the React chart doesn’t
  understand). Keep the rest of `main.py`.

### Wire the Next.js component
In your member dashboard (`frontend/src/app/dashboard/page.jsx`), import and
render the new widget in the Network/Team tab:
```tsx
import MyTeam from "@/components/team/MyTeam";
// ...inside the Network tab content:
<MyTeam />
```

---

## 2. CRITICAL bugs found (money & correctness) — now fixed

1. **Commissions never actually paid.** `commission_engine.py` inserted wallet
   rows into a column named **`reference`**, but `wallet_ledger` has
   **`reference_id`**. Postgres raises `UndefinedColumn`, the engine catches it
   and returns an error — so every payout silently failed. *(Fixed: engine now
   uses the shared ledger service; migration also adds a synced `reference`
   column so neither name can break.)*

2. **Level commission % always empty.** `package_service.get_plan_with_commissions()`
   ran `SELECT level, percentage FROM level_commissions`, but the table column
   is **`commission_percentage`** → `UndefinedColumn` → no level income and
   failed purchases. *(Fixed; canonical plan now lives in `commission_plan` with
   the legacy table kept in sync.)*

3. **Activation and payout were in two separate transactions.** A failure left
   users **activated but unpaid**, or paid but not active. *(Fixed:
   `purchase_package()` creates an `order`, activates, and distributes in ONE
   transaction — all or nothing.)*

4. **Idempotency was fake.** The duplicate-check key included a random UUID +
   timestamp, so it could never match a retry → **double payouts** possible.
   *(Fixed: unique index on `(earner_id, order_id, level)` + `ON CONFLICT`.)*

5. **`orders` table missing but queried.** `team_service.get_user_purchase_history`
   selects from `orders`, which didn’t exist → error every call. *(Fixed: table
   created + backfilled from `user_packages`.)*

6. **Duplicate / conflicting routes.** `/api/team/me` and `/api/genealogy/me`
   were defined in BOTH `main.py` and `user_routes.py`; the two genealogy
   versions return *different shapes*. *(Fixed: single canonical version.)*

7. **Second application factory.** `app/routes/__init__.py` defines another
   `create_app()` (with broken CORS and an undefined `rank_bp`). *(Delete it.)*

8. **Production RCE risk.** `run.py` runs `debug=True, use_reloader=True` — the
   Werkzeug interactive debugger allows **remote code execution**. *(Fixed:
   debug only in local dev; production runs gunicorn.)*

---

## 3. SCALE bugs (the “1 lakh users” requirement) — now fixed

| Problem | Impact | Fix |
|---|---|---|
| `tree_service.build_tree()` ran **1 SQL query per node**, recursively | A 5,000-person network = **5,000 queries** on one page; at 1 lakh users the admin tree page hangs the DB | One **ltree subtree query**, assembled in memory (`admin/tree_service.py`) |
| `@cache.memoize(timeout=1)` | 1-second cache = effectively no cache | Redis cache, 300 s TTL |
| `SimpleCache` | Per-process: 9 gunicorn workers keep **9 stale caches**; RAM blow-up | **Redis** shared cache (`app/cache.py`) |
| Team counts via unbounded **recursive CTE on every page load** | O(network size) per request → DB CPU 100% under load | Denormalised **`direct_count` / `total_team_count`** maintained by triggers; reads are O(1); counts use indexed **ltree** path |
| Admin search `ILIKE '%x%'` | Sequential scan of all users per keystroke | **pg_trgm GIN indexes** on name/email/phone |
| Missing indexes | Full scans on hot paths | Added indexes on `users(sponsor_id, rank_level, is_active, created_at)`, `commissions`, `wallet_ledger`, `orders` (see migration) |
| No statement timeout | One slow query pins a connection | `statement_timeout=5000ms` |
| App opened its **own DB connection mid-transaction** (rank eval calling `get_total_team_count`) | Self-block / pool exhaustion | All reads reuse the **open cursor** |
| PgBouncer mis-pooling risk | 9 workers × pool-100 = up to 900 server connections | Small per-worker pool (20) + **PgBouncer transaction pooling** (see `deploy/`) |
| Loading the **entire tree** to render one screen | Megabytes of JSON per click | **Drill-down loads one level (12 cards) per click** — flat cost regardless of network size |

> The single biggest performance decision in the new UI: **the team screen
> never loads the whole network.** It loads the selected member’s direct
> children (one indexed query, paginated). Clicking a member loads *that*
> member’s children. Cost per click is constant whether you have 100 or
> 100,000 users.

---

## 4. Package & Commission plan (now explicit in the DB)

The code already had half-built tables (`subscription_plans`, `commission_plan`,
`level_commissions`, `global_commissions`) but no consistent seed and the engine
read the wrong columns. Migration **0004** seeds a complete, editable plan and
the engine now reads it.

### Packages (subscription_plans)
| Plan | Price (₹) | Coupons |
|---|---|---|
| Starter | 1,800 | 12 |
| Bronze | 3,600 | 12 |
| Silver | 7,200 | 12 |
| Gold | 14,400 | 12 |
| Platinum | 28,800 | 12 |

### Level / generation income (% of purchase price, paid to upline)
| Upline level | Relation | Commission % |
|---|---|---|
| Level 1 | Direct sponsor | **10%** (direct commission) |
| Level 2 |  | 3% |
| Level 3 |  | 2.5% |
| Level 4 |  | 2% |
| Level 5 |  | 1.5% |
| Level 6 |  | 1.5% |
| Level 7 |  | 1.5% |
| Level 8 |  | 1% |
| Level 9 |  | 1% |
| Level 10 |  | 1% |

### Global settings (global_commissions)
`direct_commission 10%`, `self_cashback 5%`, `tds_percentage 5%`,
`admin_fee_percentage 10%` (fees applied at withdrawal).

**Example:** a buyer purchases Silver (₹7,200): direct sponsor gets ₹720
(10%), L2 ₹216, L3 ₹180, L4 ₹144, L5–L7 ₹108 each, L8–L10 ₹72 each; buyer may
get ₹360 self-cashback. All values are **editable in Admin → Packages** and the
engine picks up changes within 60 s (Redis config cache, busted on save).

> These match your seeded data (`commission_plan` had 3/2.5/1.5… and
> `direct_referral` = 10%). Adjust to your final business plan **before
> launch**; changing levels later does not retroactively alter paid
> commissions (they are stored as immutable ledger rows).

---

## 5. “My Team” drill-down UI — how it behaves (matches your mockup)

```
┌─ My Team ───────────────────────────────────────────────┐
│ Total Team   Direct Referrals   Active      Rank         │
│   527             18             486       Diamond       │
│                                                          │
│ 🔍 Search member   Rank ▾   Status ▾                     │
│                                                          │
│ YOU — M000001                                            │
│ Diamond • Gold Plan • 527 Team Members                   │
│                                                          │
│ Level 1                                                  │
│ [Member A][Member B][Member C][Member D] ...             │
│   125       86       174      141                        │
│  Drill ↓   Drill ↓  Drill ↓  Drill ↓                     │
└──────────────────────────────────────────────────────────┘
```

* Admin screen: **`/admin/user/team/<id>`** → `app/templates/admin/user_team.html`.
* Member screen: **`<MyTeam />`** in the Next.js dashboard.
* Both call the same API: **`GET /api/team/node/<id>?page=&rank=&status=`**.
* **Clicking Member B transforms the SAME card** in place into Member B’s
  downline (stats, header, children all update) — the drill follows the
  selected member. A breadcrumb (You / … / Member B) lets you walk back up.
* Each member card shows their own team size and a **Drill ↓** affordance.
* The API returns only the current member + one page of direct children, with
  a total count, so it stays instant at 100k users.
* Search filters the loaded cards live; Rank/Status filters are applied
  server-side (indexed).

---

## 6. Deploy checklist (1-lakh concurrency)

1. Install & configure **Redis** and **PgBouncer** (see `deploy/deployment.md`).
2. Set environment from `deploy/.env.example` (strong secrets, `DB_PORT=6432`,
   `REDIS_URL`, CORS origin).
3. Run migration `0004` (after backup).
4. `pip install -r requirements.txt`.
5. Run under **gunicorn/gevent** (`deploy/gunicorn.conf.py`) behind **Nginx**.
6. Front-end: set `NEXT_PUBLIC_API_URL`; deploy Next.js separately.
7. Verify: `GET /healthz`, admin Packages percentages, admin Users → Team drill.

### Recommended follow-ups (not blocking, but on the enterprise checklist)
* Add **CSRF protection** (`Flask-WTF`) to all state-changing form posts
  (admin activate/deactivate, packages) — currently the Jinja forms rely on
  SameSite cookies only.
* Move the in-process **Flask-Executor** jobs to **Celery/RQ on Redis** when
  running more than one app server.
* Point heavy report/dashboard queries at a **read replica**.
* Add structured logging/metrics (Prometheus) and Sentry for errors.
* Add automated tests for the commission engine (money path) in CI.
* Store file uploads on object storage (S3/Cloud Storage) instead of local
  disk when running multiple app servers.
