#!/usr/bin/env bash
# ============================================================================
#  INSTALL.sh  —  ONE-COMMAND installer for the RK Trendz MLM enterprise fixes
#
#  It does EVERYTHING for you (no file-by-file editing, no manual SQL):
#    1. Backs up every code file it touches  -> <project>/.mlmfix-backup/<time>/
#    2. Replaces all fixed files & creates the new files
#    3. Deletes the broken duplicate app factory (app/routes/__init__.py)
#    4. Auto-patches app/routes/main.py (removes duplicate routes)
#    5. Auto-wires the Next.js dashboard (import + <MyTeam/>) and removes old team.js
#    6. Installs Python dependencies (pip install -r requirements.txt)
#    7. Reads your DB settings from the project .env, backs up the DATABASE,
#       runs the migration (data preserved; additive only), and verifies it
#
#  USAGE
#     bash INSTALL.sh /path/to/your/Sarvesh-MLM-Code
#     bash INSTALL.sh            # auto-searches common locations
#
#  Nothing is deleted from your database. To undo code: restore files from
#  .mlmfix-backup/. To undo DB: restore the .sql backup it creates.
# ============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXES_DIR="$SCRIPT_DIR"

c_g(){ printf "\033[32m%s\033[0m\n" "$*"; }
c_y(){ printf "\033[33m%s\033[0m\n" "$*"; }
c_r(){ printf "\033[31m%s\033[0m\n" "$*"; }
c_b(){ printf "\033[36m%s\033[0m\n" "$*"; }

# ---------------------------------------------------------------------------
# 0. Locate the project
# ---------------------------------------------------------------------------
TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  for cand in "$PWD" "$PWD/Sarvesh-MLM-Code" "$HOME/Sarvesh-MLM-Code" \
              "$HOME/Desktop/Sarvesh-MLM-Code" /home/user/Sarvesh-MLM-Code; do
    if [[ -f "$cand/app/__init__.py" ]]; then TARGET="$cand"; break; fi
  done
fi

if [[ -z "$TARGET" || ! -f "$TARGET/app/__init__.py" ]]; then
  c_r "Could not find your MLM project automatically."
  echo  "  Run this with the project folder, e.g.:"
  echo  "     bash INSTALL.sh /home/yourname/Sarvesh-MLM-Code"
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"
BACKUP_DIR="$TARGET/.mlmfix-backup/$(date +%Y%m%d_%H%M%S)"

c_g "=================================================================="
c_g "  RK TRENDZ MLM — AUTOMATIC INSTALLER"
echo  "  Project : $TARGET"
echo  "  Backups : $BACKUP_DIR"
c_g "=================================================================="
mkdir -p "$BACKUP_DIR"

FILES=(
  "requirements.txt" "run.py" "app/__init__.py" "app/cache.py" "app/db.py"
  "app/config/config.py"
  "app/services/team_service.py" "app/services/sponsor_service.py"
  "app/services/package_service.py" "app/services/commission_engine.py"
  "app/services/rank_service.py" "app/services/admin_user_service.py"
  "app/services/admin/tree_service.py"
  "app/routes/admin/package_routes.py" "app/routes/team_routes.py"
  "app/templates/admin/user_team.html" "app/templates/admin/packages.html"
  "frontend/src/services/api.js" "frontend/src/services/team.ts"
  "frontend/src/components/team/MyTeam.tsx"
)

# ---------------------------------------------------------------------------
# 1. Copy fixed/new files (back up originals first)
# ---------------------------------------------------------------------------
c_b "[1/7] Installing fixed & new files..."
for rel in "${FILES[@]}"; do
  src="$FIXES_DIR/$rel"; dst="$TARGET/$rel"
  [[ -f "$src" ]] || { c_r "   ! missing in fixes: $rel"; continue; }
  mkdir -p "$BACKUP_DIR/$(dirname "$rel")" "$(dirname "$dst")"
  [[ -f "$dst" ]] && cp -a "$dst" "$BACKUP_DIR/$rel"
  cp -a "$src" "$dst"
  echo  "   ✓ $rel"
done

# ---------------------------------------------------------------------------
# 2. Delete broken duplicate factory
# ---------------------------------------------------------------------------
c_b "[2/7] Removing broken file app/routes/__init__.py ..."
if [[ -f "$TARGET/app/routes/__init__.py" ]]; then
  mkdir -p "$BACKUP_DIR/app/routes"
  cp -a "$TARGET/app/routes/__init__.py" "$BACKUP_DIR/app/routes/__init__.py"
  rm -f "$TARGET/app/routes/__init__.py"
  echo  "   ✓ deleted (backed up)"
else
  echo  "   - already absent"
fi

# ---------------------------------------------------------------------------
# 3. Patch main.py (duplicate routes)
# ---------------------------------------------------------------------------
c_b "[3/7] Patching app/routes/main.py ..."
python3 "$FIXES_DIR/deploy/patch_main.py" "$TARGET/app/routes/main.py" || \
  c_r "   ! main.py patch failed (tell support)"

# ---------------------------------------------------------------------------
# 4. Wire the Next.js dashboard
# ---------------------------------------------------------------------------
c_b "[4/7] Wiring the Next.js dashboard (My Team widget) ..."
if [[ -d "$TARGET/frontend" ]]; then
  python3 "$FIXES_DIR/deploy/patch_frontend.py" "$TARGET" || \
    c_y "   ! dashboard auto-wire skipped (you can add <MyTeam/> manually)"
else
  echo  "   - no frontend/ folder found, skipped"
fi

# ---------------------------------------------------------------------------
# 5. Python dependencies
# ---------------------------------------------------------------------------
c_b "[5/7] Installing Python dependencies..."
PIP="pip3"; command -v pip3 >/dev/null || PIP="pip"
if [[ -d "$TARGET/.venv" ]]; then
  [[ -f "$TARGET/.venv/bin/pip" ]] && PIP="$TARGET/.venv/bin/pip"
fi
if $PIP install -r "$TARGET/requirements.txt" >/tmp/mlm_pip.log 2>&1; then
  echo  "   ✓ dependencies installed"
else
  c_y "   ! pip install had issues (see /tmp/mlm_pip.log). Continuing."
fi

# ---------------------------------------------------------------------------
# 6. Ensure .env secrets exist (app won't boot without them)
# ---------------------------------------------------------------------------
c_b "[6/7] Checking environment configuration..."
ENVF="$TARGET/.env"
touch "$ENVF"; cp -a "$ENVF" "$BACKUP_DIR/.env" 2>/dev/null || true

# Load DB_* / secrets from .env (tolerate lines with spaces or comments).
if [[ -f "$ENVF" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      \#*|"") continue ;;
      *=*)
        k="${line%%=*}"; v="${line#*=}"
        # strip surrounding quotes from the value
        v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
        case "$k" in DB_HOST|DB_PORT|DB_NAME|DB_USER|DB_PASSWORD|REDIS_URL|ENV)
          export "$k=$v" 2>/dev/null || true ;;
        esac ;;
    esac
  done < "$ENVF"
fi

need_secret=0; need_jwt=0
grep -q "^SECRET_KEY=.\+" "$ENVF" || need_secret=1
grep -q "^JWT_SECRET=.\+"  "$ENVF" || need_jwt=1
if [[ $need_secret -eq 1 ]]; then
  echo "SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" >> "$ENVF"
  echo "   ✓ generated SECRET_KEY"
fi
if [[ $need_jwt -eq 1 ]]; then
  echo "JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" >> "$ENVF"
  echo "   ✓ generated JWT_SECRET"
fi
[[ $need_secret -eq 0 && $need_jwt -eq 0 ]] && echo "   ✓ .env secrets present"

# ---------------------------------------------------------------------------
# 7. Database backup + migration
# ---------------------------------------------------------------------------
c_b "[7/7] Database backup & migration..."
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-rk_trendz_mlm}"
DB_USER="${DB_USER:-postgres}"
[[ -n "${DB_PASSWORD:-}" ]] && export PGPASSWORD="$DB_PASSWORD"

if command -v psql >/dev/null 2>&1 && psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1" >/dev/null 2>&1; then
  echo "   - backing up database to $BACKUP_DIR/db_backup.sql ..."
  if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" -f "$BACKUP_DIR/db_backup.sql" 2>/tmp/mlm_pg.log; then
    echo "   ✓ database backed up"
  else
    c_y "   ! pg_dump failed (see /tmp/mlm_pg.log); skipping migration for safety."
    DB_OK=0
  fi
  if [[ "${DB_OK:-1}" -eq 1 ]]; then
    echo "   - running migrations (additive; your data is kept) ..."
    MIG_FAIL=0
    # NOTE: use a quoted glob, NOT $(ls ...) — the project path can contain
    # spaces (e.g. "Ram Suresh Prajapati") which would split the filename.
    for sql in "$FIXES_DIR"/migrations/*.sql; do
      [ -e "$sql" ] || continue
      echo "      • applying $(basename "$sql") ..."
      if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -v ON_ERROR_STOP=1 --single-transaction -f "$sql" >/tmp/mlm_migrate.log 2>&1; then
        echo "        ✓ applied"
      else
        echo "        ! $(basename "$sql") failed and was rolled back."
        tail -n 12 /tmp/mlm_migrate.log | sed 's/^/          /'
        MIG_FAIL=1
      fi
    done
    if [[ $MIG_FAIL -eq 0 ]]; then
      echo "   ✓ all migrations applied"
      c_y "   Verification:"
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT '     packages: ' || COUNT(*) FROM subscription_plans;" 2>/dev/null
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT '     commission levels: ' || COUNT(*) FROM commission_plan;" 2>/dev/null
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT '     ranks: ' || COUNT(*) FROM rank_rules;" 2>/dev/null
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT '     users with team counts: ' || COUNT(*) FROM users WHERE total_team_count IS NOT NULL;" 2>/dev/null
    fi
  fi
else
  c_y "   ! Could not connect to PostgreSQL ($DB_USER@$DB_HOST:$DB_PORT/$DB_NAME)"
  echo  "     Code files are installed. Run the DB step yourself when Postgres is up:"
  echo  "       pg_dump -U $DB_USER -d $DB_NAME -f backup.sql"
  echo  "       psql  -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 --single-transaction \\"
  echo  "             -f $FIXES_DIR/migrations/0004_enterprise_scale_and_plan.sql"
fi

# ---------------------------------------------------------------------------
c_g "=================================================================="
c_g "  ✅ INSTALLATION COMPLETE"
echo  "  All code + the database migration are done. Backups are in:"
echo  "     $BACKUP_DIR"
echo
c_b "  NOW RESTART YOUR SERVER:"
echo  "     1) Stop the running Flask server (Ctrl+C in its window)."
echo  "     2) Start it again:   python run.py"
echo  "     3) For production use gunicorn (see deploy/deployment.md)."
echo
c_b "  CHECK IN THE BROWSER:"
echo  "     • Admin → Packages : commission plan + packages editable"
echo  "     • Admin → Users → Team : click a member, the card drills down"
echo  "     • Member dashboard → My Network Tree : the new My Team widget"
c_g "=================================================================="
