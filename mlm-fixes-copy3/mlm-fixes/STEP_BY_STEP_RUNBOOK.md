# Step-by-Step Runbook — what to Create, Update, Delete, and how to migrate the live DB

This is the exact order to follow. Your existing data is **not erased** — the
migration only *adds* columns/tables/indexes and *back-fills* missing pieces.
Read the whole thing once before touching anything.

Legend: 🆕 **CREATE** · ✏️ **UPDATE (replace contents)** · 🗑️ **DELETE** · 🗄️ **DATABASE**

---

## PHASE 0 — Prepare (no risk, nothing live changes)

1. 🗄️ **Take a full backup first (mandatory):**
   ```bash
   pg_dump -U postgres -d rk_trendz_mlm -f backup_before_0004.sql
   ```
   Keep that file somewhere safe. If anything looks wrong you can restore with:
   ```bash
   psql -U postgres -d rk_trendz_mlm -f backup_before_0004.sql
   ```

2. Make sure these PostgreSQL extensions are available (they are standard in
   Postgres; on managed hosts like RDS/Supabase they are usually already
   enabled — the migration runs `CREATE EXTENSION IF NOT EXISTS`, so it is
   harmless):
   - `ltree`  (used for the fast team tree)
   - `pg_trgm` (used for fast search)
   You (or your host) need the Postgres contrib package; on a normal server:
   ```bash
   sudo apt-get install postgresql-contrib
   ```

3. Copy the whole `mlm-fixes` folder next to your repo so the paths line up.

---

## PHASE 1 — Run the DATABASE migration (additive, keeps your data)

The file is **`migrations/0004_enterprise_scale_and_plan.sql`**.

It does **not** drop or truncate anything. It:
- creates the missing `orders` table and back-fills it from `user_packages`;
- adds columns to `users` (`tree_path`, `direct_count`, `total_team_count`)
  and back-fills them from your existing sponsor links;
- adds indexes (this can take a minute or two on a large table — run during
  **low traffic**);
- seeds packages/commissions only where rows are missing (`ON CONFLICT DO
  NOTHING`) — your existing prices/percentages are **not overwritten**;
- adds a synced `reference` column to `wallet_ledger` so old and new code both
  work.

▶️ **Run it inside a transaction so it either fully succeeds or fully rolls
back (nothing half-applied):**
```bash
psql -U postgres -d rk_trendz_mlm -v ON_ERROR_STOP=1 --single-transaction \
     -f migrations/0004_enterprise_scale_and_plan.sql
```
`-v ON_ERROR_STOP=1 --single-transaction` = if any single statement fails, the
entire migration is rolled back and your DB is untouched. Fix the error and
re-run (it is idempotent — safe to run again).

✅ **Verify after migration:**
```sql
SELECT level, percentage FROM commission_plan ORDER BY level;          -- 10 rows
SELECT id, full_name, direct_count, total_team_count, tree_path FROM users LIMIT 5;
SELECT COUNT(*) FROM orders;                                           -- back-filled
```
The `tree_path` for your top/admin user looks like `1`; a downline member looks
like `1.5`, etc. If any `tree_path` is NULL for a real member, see Troubleshooting.

> Note on large networks: building the indexes/`tree_path` on hundreds of
> thousands of rows can lock/write-heavy for a short while. Low-traffic window
> is best. The `refresh_user_counters()` call updates every user once.

---

## PHASE 2 — Backend Python files

### 🆕 CREATE these new files (copy from `mlm-fixes` into your repo, same path)

| New file in your repo | Purpose |
|---|---|
| `app/routes/team_routes.py` | The drill-down API `/api/team/node` |

(Everything else in `mlm-fixes/app/...` is a replacement for an existing file.)

### ✏️ UPDATE (open your existing file, replace its entire contents with the new one)

| Replace this file | With `mlm-fixes/...` |
|---|---|
| `app/config/config.py` | `app/config/config.py` |
| `app/cache.py` | `app/cache.py` |
| `app/db.py` | `app/db.py` |
| `app/__init__.py` | `app/__init__.py` |
| `run.py` | `run.py` |
| `app/services/team_service.py` | same |
| `app/services/sponsor_service.py` | same |
| `app/services/package_service.py` | same |
| `app/services/commission_engine.py` | same |
| `app/services/rank_service.py` | same |
| `app/services/admin_user_service.py` | same |
| `app/services/admin/tree_service.py` | same |
| `app/templates/admin/user_team.html` | same |
| `requirements.txt` | same |

> Tip: keep a copy of each original file first, e.g.
> `cp app/db.py app/db.py.bak` — or rely on git (`git checkout -- <file>` to
> revert).

### 🗑️ DELETE this file

- **`app/routes/__init__.py`** — it contains a second, broken `create_app()`
  that references an undefined `rank_bp`. It is not the real app factory (the
  real one is `app/__init__.py`). Delete it.
  ```bash
  git rm app/routes/__init__.py      # or:  rm app/routes/__init__.py
  ```

### ✏️ SMALL EDIT inside `app/routes/main.py` (do NOT replace the whole file)

Delete these two duplicate route blocks (they clash with the canonical ones in
`app/routes/user_routes.py`):

1. The block starting at **line ~864**:
   ```python
   @main.route("/api/team/me", methods=["GET"])
   @login_required
   def get_my_team_metadata():
       ...
   ```
   (delete from the `@main.route("/api/team/me" ...)` line down to the line
   just before the next `@main.route`).

2. The block starting at **line ~880**:
   ```python
   @main.route("/api/genealogy/me", methods=["GET"])
   @login_required
   def get_my_genealogy_tree():
       ...
   ```
   (same — delete the whole function up to the next decorator).

After the edit, `main.py` must still end with the `/api/payment/create-order`
route. A quick check:
```bash
grep -n "def create_app" -r app          # should appear ONLY in app/__init__.py
grep -n "/api/team/me\|/api/genealogy/me" app/routes/main.py   # should return NOTHING
```

---

## PHASE 3 — Install dependencies & restart backend

```bash
# in your backend folder (use your venv)
pip install -r requirements.txt
```
This adds **redis**, **gunicorn**, **gevent**.

Set environment variables (see `deploy/.env.example`). Minimum new ones:
```bash
export REDIS_URL="redis://127.0.0.1:6379/0"     # required for scale; install redis-server
export DB_PORT=5432                               # use 6432 only once PgBouncer is set up
```
- **Locally without Redis?** The app still boots and falls back to in-process
  cache (a warning is logged). Install Redis for any real/multi-user use:
  `sudo apt-get install redis-server`.
- PgBouncer/Nginx/gunicorn are for production rollout — follow
  `deploy/deployment.md`. They are **not** required to test the features.

Restart the API (dev):
```bash
python run.py
```
✅ Smoke test:
```bash
curl http://127.0.0.1:5000/healthz                 # -> {"status":"ok"}
curl http://127.0.0.1:5000/api/team/node          # after logging in, or test from UI
```

---

## PHASE 4 — Frontend (Next.js)

### ✏️ UPDATE
- Replace `frontend/src/services/api.js` with `frontend/src/services/api.js`.
  (It now reads `NEXT_PUBLIC_API_URL`; locally it still defaults to
  `127.0.0.1:5000/api`.)

### 🆕 CREATE
- `frontend/src/components/team/MyTeam.tsx` — the drill-down widget.
- `frontend/src/services/team.ts` — adds `fetchTeamNode`.
  - Your existing file is `team.js`. You can either:
    **(a)** keep both (`.ts` new, `.js` old) and import the new helper from the
    new component, or
    **(b)** delete `team.js` and use `team.ts` everywhere (the new file keeps
    the old `fetchNetworkData` / `fetchUplineData` exports).
    Option (a) is the safest one-step move.

### ✏️ WIRE INTO DASHBOARD (one small edit)
In `frontend/src/app/dashboard/page.jsx`, in the **Network/Team** tab area:
```tsx
import MyTeam from "@/components/team/MyTeam";
// ...inside the Network tab's JSX:
<MyTeam />
```
Set the API URL for the frontend build (production):
```bash
export NEXT_PUBLIC_API_URL="https://api.yourdomain.com/api"
```
Restart the Next dev server / redeploy.

---

## PHASE 5 — Final verification checklist

- [ ] Admin → **Packages**: percentages and levels show correctly.
- [ ] Admin → **Users → Team**: the “My Team” card loads; clicking **Member B**
      changes the same card to Member B’s downline; breadcrumb walks back.
- [ ] A test purchase (or redemption) creates an `orders` row AND commission
      rows AND wallet credits in one go:
      ```sql
      SELECT * FROM orders ORDER BY id DESC LIMIT 1;
      SELECT * FROM commissions WHERE order_id = <that id>;
      SELECT * FROM wallet_ledger WHERE reference_id LIKE 'COMM-<that id>%';
      ```
- [ ] `/healthz` returns ok; no tracebacks in logs.

---

## Troubleshooting (safe, data-preserving)

| Symptom | Fix |
|---|---|
| Migration errors on `CREATE EXTENSION ltree/pg_trgm` | Install `postgresql-contrib`, or ask your managed-DB host to enable the extension; then re-run (rolls back cleanly). |
| Some `users.tree_path` are NULL after migration | Re-run the back-fill for the tree path only — it is the `WITH RECURSIVE build_path ... UPDATE users SET tree_path ...` block in the migration (safe to re-run). NULL usually means a sponsor points to a missing/looping parent. |
| Counts look stale after a purchase | They are maintained by triggers; you can also force a refresh any time with:  `SELECT public.refresh_user_counters();` |
| App logs “REDIS_URL not set → SimpleCache” | Fine for local dev; install/set Redis for production. |
| Changed commission %, still seeing old value for up to ~1 min | That’s the 60-second config cache by design; it also clears immediately when you save via Admin → Packages. |
| Want to roll the code back | Restore the original Python files (`git checkout -- <file>` or your `.bak` copies) and restart. The DB migration is additive — old code still works with it. |

### Order matters — remember:
**Backup → run migration (Phase 1) → replace backend files + delete the 1 file +
edit main.py (Phase 2) → pip install + restart (Phase 3) → frontend (Phase 4).**
Deploying the migration *before* the new code is intentional and safe: the
schema changes are additive, so the old code keeps running until you restart.
