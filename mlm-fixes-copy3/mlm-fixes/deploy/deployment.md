# Deployment & scaling guide — RK Trendz MLM (100,000 concurrent users)

This is the architecture that lets the API handle ~1 lakh concurrent users
**without lag**. The application code rewrite removes the N+1/recursive-query
problems; this file describes the runtime that scales it.

```
                          ┌─────────────┐
   Users (browser/app) ──▶│   NGINX     │  TLS termination, static assets,
                          │  (LB/proxy) │  gzip, rate-limit, request buffering
                          └──────┬──────┘
                ┌───────────────┼────────────────┐
                ▼               ▼                ▼
        ┌────────────┐  ┌────────────┐   ┌────────────┐
        │ Gunicorn   │  │ Gunicorn   │   │ Gunicorn   │   gevent workers
        │ gevent x9  │  │ gevent x9  │   │ gevent x9  │   (worker_connections=1000)
        └─────┬──────┘  └─────┬──────┘   └─────┬──────┘
              └───────────────┼────────────────┘
                     ┌────────┴─────────┐
                     ▼                  ▼
              ┌────────────┐    ┌──────────────┐
              │ PgBouncer  │    │    Redis     │  shared cache / sessions
              │ (txn pool) │    └──────────────┘
              └─────┬──────┘
                    ▼
              ┌────────────┐
              │ PostgreSQL │  (indexes + ltree from migration 0004)
              └────────────┘
```

## 1. Why this handles 1 lakh concurrent users

| Layer | Setting | Why |
|---|---|---|
| **Gunicorn + gevent** | `workers = 2*CPU+1`, `worker_connections=1000` | Each worker is an event loop that holds **thousands** of open sockets with little memory while waiting on the DB. |
| **PgBouncer (transaction mode)** | pool_size 80–100 | The DB only ever sees ~100 *real* connections regardless of how many gunicorn greenlets/servers exist. Without it, 9 workers × 100-pool = 900 Postgres connections → crash. |
| **DB pool in app** | `DB_POOL_MAX=20` per worker | Small local pool; PgBouncer does the multiplexing. |
| **Redis cache** | `REDIS_URL=...` | One shared cache for all workers/servers (team counts, tree, commission config). The old in-process SimpleCache gave every worker its own stale copy. |
| **ltree + counters** | migration 0004 | "Total team / team by level" is an indexed subtree lookup, not a recursive walk. Counters (`direct_count`, `total_team_count`) are maintained by triggers → header stats are O(1). |
| **statement_timeout** | 5000 ms | One runaway query can never pin a connection. |
| **Pagination** | 12–25 rows/page + trigram search | Team/users screens never fetch the whole network. |

## 2. Process (one-time setup on the server)

```bash
# App user + code
sudo useradd -m -s /bin/bash rkapp
# deploy code to /opt/rktrendz, then:
cd /opt/rktrendz
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Environment
cp deploy/.env.example .env
#   -> set strong SECRET_KEY / JWT_SECRET, DB and Redis passwords

# Database: run the hardening migration AFTER taking a backup
pg_dump rk_trendz_mlm > backup_before_0004.sql
psql -d rk_trendz_mlm -f migrations/0004_enterprise_scale_and_plan.sql
```

## 3. PgBouncer (`/etc/pgbouncer/pgbouncer.ini`, key lines)

```ini
[databases]
rk_trendz_mlm = host=127.0.0.1 port=5432 dbname=rk_trendz_mlm

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 5000
default_pool_size = 90
reserve_pool_size = 10
reserve_pool_timeout = 2
server_idle_timeout = 60
ignore_startup_parameters = extra_float_digits
```
Set `DB_PORT=6432` in the app `.env`. Postgres `max_connections = 200` is fine.

## 4. Run the API (systemd) — `/etc/systemd/system/rktrendz.service`

```ini
[Unit]
Description=RK Trendz MLM API
After=network.target postgresql.service pgbouncer.service redis-server.service

[Service]
User=rkapp
WorkingDirectory=/opt/rktrendz
EnvironmentFile=/opt/rktrendz/.env
ExecStart=/opt/rktrendz/.venv/bin/gunicorn -c deploy/gunicorn.conf.py "app:create_app()"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now rktrendz
```

## 5. Nginx site (`/etc/nginx/sites-available/rktrendz`)

```nginx
upstream rk_api { server 127.0.0.1:8000; }
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    # ssl_certificate / ssl_certificate_key ...

    client_max_body_size 10m;
    keepalive_timeout 65;

    # Rate limiting at the edge too
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

    location / {
        limit_req zone=api burst=60 nodelay;
        proxy_pass http://rk_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /static/ { alias /opt/rktrendz/app/static/; expires 30d; }
}
```

## 6. Horizontal scale

* Run N app servers behind Nginx (or a cloud LB); all share **PgBouncer +
  Postgres + Redis**, so the cache is consistent everywhere.
* Put the Next.js front-end on Vercel / Netlify / static hosts; point
  `NEXT_PUBLIC_API_URL` at the API domain.
* Postgres: start with a managed instance (RDS/Cloud SQL) with a read replica;
  move reporting/dashboard reads to the replica if needed.

## 7. Background jobs

* Commissions run **synchronously in the purchase transaction** (correct &
  idempotent), so there is no missing-money window.
* Heavy/rank recalculation and reports should run on a worker (Flask-Executor
  in-process for single node; move to Celery/RQ backed by Redis when you run
  multiple app nodes). The disabled `process_daily_commissions()` stays
  disabled — level income is event-driven on purchase, which is correct.

## 8. Post-deploy verification

```bash
curl -k https://api.yourdomain.com/healthz          # -> {"status":"ok"}
psql -d rk_trendz_mlm -c "SELECT level,percentage FROM commission_plan ORDER BY level;"
psql -d rk_trendz_mlm -c "SELECT id,direct_count,total_team_count FROM users LIMIT 5;"
# Log in as admin -> Packages: confirm percentages; Users -> Team: drill works.
```
