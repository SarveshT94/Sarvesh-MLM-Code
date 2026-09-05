#!/usr/bin/env bash
# ============================================================================
# apply.sh — ONE-COMMAND installer for the RK Trendz MLM enterprise fixes.
#
# It backs up every file it touches, then copies the corrected/new files into
# your project, deletes the one broken file, and patches main.py automatically.
# You do NOT open or edit files by hand (except the 2-line <MyTeam/> wiring in
# the Next.js dashboard, which it prints at the end).
#
# USAGE
#   bash deploy/apply.sh /path/to/your/Sarvesh-MLM-Code [options]
#
# OPTIONS
#   --with-pip    also run:  pip install -r requirements.txt
#   --with-db     also run the PostgreSQL migration (uses your .env / env vars)
#   --dry-run     show what it WOULD do, change nothing
#
# Examples:
#   bash deploy/apply.sh ../Sarvesh-MLM-Code --dry-run
#   bash deploy/apply.sh ../Sarvesh-MLM-Code
#   bash deploy/apply.sh ../Sarvesh-MLM-Code --with-pip
# ============================================================================
set -euo pipefail

# ---- Resolve the folder that CONTAINS the fixed files (this repo) --------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # = mlm-fixes/

TARGET="${1:-}"
DRY=0; WITH_PIP=0; WITH_DB=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --with-pip) WITH_PIP=1 ;;
    --with-db) WITH_DB=1 ;;
  esac
done

c_g(){ printf "\033[32m%s\033[0m\n" "$*"; }
c_y(){ printf "\033[33m%s\033[0m\n" "$*"; }
c_r(){ printf "\033[31m%s\033[0m\n" "$*"; }

if [[ -z "$TARGET" ]]; then
  c_r "ERROR: give the path to your MLM project, e.g."
  echo "  bash deploy/apply.sh /home/you/Sarvesh-MLM-Code"
  exit 1
fi
TARGET="$(cd "$TARGET" 2>/dev/null && pwd)" || { c_r "Target folder not found: $1"; exit 1; }

if [[ ! -f "$TARGET/app/__init__.py" ]]; then
  c_r "That doesn't look like the MLM project (no app/__init__.py)."
  echo "  Path given: $TARGET"
  exit 1
fi

BACKUP_DIR="$TARGET/.mlmfix-backup/$(date +%Y%m%d_%H%M%S)"

# Files to REPLACE or CREATE (paths relative to project root)
FILES=(
  "requirements.txt"
  "run.py"
  "app/__init__.py"
  "app/cache.py"
  "app/db.py"
  "app/config/config.py"
  "app/services/team_service.py"
  "app/services/sponsor_service.py"
  "app/services/package_service.py"
  "app/services/commission_engine.py"
  "app/services/rank_service.py"
  "app/services/admin_user_service.py"
  "app/services/admin/tree_service.py"
  "app/routes/admin/package_routes.py"
  "app/routes/team_routes.py"
  "app/templates/admin/user_team.html"
  "app/templates/admin/packages.html"
  "frontend/src/services/api.js"
  "frontend/src/services/team.ts"
  "frontend/src/components/team/MyTeam.tsx"
)
# File to DELETE (broken duplicate app factory)
DELETE_FILE="app/routes/__init__.py"
# File to auto-patch (remove duplicate routes)
PATCH_FILE="app/routes/main.py"

c_g "=============================================================="
c_g " MLM fixes installer"
echo "  Project target : $TARGET"
echo "  Fixes source   : $FIXES_DIR"
echo "  Backup folder  : $BACKUP_DIR"
[[ $DRY -eq 1 ]] && c_y "  DRY RUN — nothing will be changed."
c_g "=============================================================="

run(){ if [[ $DRY -eq 1 ]]; then echo "  DRY: $*"; else eval "$*"; fi; }

# ---- 1. Backup + copy every file ------------------------------------------
echo
c_y "[1/5] Copying fixed & new files (originals are backed up first)..."
for rel in "${FILES[@]}"; do
  src="$FIXES_DIR/$rel"
  dst="$TARGET/$rel"
  if [[ ! -f "$src" ]]; then
    c_r "  ! missing in fixes folder: $rel (skipped)"; continue
  fi
  # Backup the original if it exists
  if [[ -f "$dst" ]]; then
    run "mkdir -p \"$BACKUP_DIR/$(dirname "$rel")\" && cp -a \"$dst\" \"$BACKUP_DIR/$rel\""
  fi
  run "mkdir -p \"$(dirname "$dst")\" && cp -a \"$src\" \"$dst\""
  echo "    ✓ $rel"
done

# ---- 2. Delete the broken duplicate factory -------------------------------
echo
c_y "[2/5] Removing broken file: $DELETE_FILE"
if [[ -f "$TARGET/$DELETE_FILE" ]]; then
  run "mkdir -p \"$BACKUP_DIR/app/routes\" && cp -a \"$TARGET/$DELETE_FILE\" \"$BACKUP_DIR/$DELETE_FILE\""
  run "rm -f \"$TARGET/$DELETE_FILE\""
  echo "    ✓ deleted (backup kept)"
else
  echo "    - already absent"
fi

# ---- 3. Patch main.py (remove duplicate routes) ----------------------------
echo
c_y "[3/5] Patching $PATCH_FILE (removing duplicate /api/team/me & /api/genealogy/me)..."
run "python3 \"$FIXES_DIR/deploy/patch_main.py\" \"$TARGET/$PATCH_FILE\""

# ---- 4. (optional) pip install ---------------------------------------------
echo
if [[ $WITH_PIP -eq 1 ]]; then
  c_y "[4/5] Installing Python dependencies..."
  run "cd \"$TARGET\" && pip install -r requirements.txt"
else
  c_y "[4/5] Skipping pip install (re-run with --with-pip, or run manually):"
  echo "      pip install -r requirements.txt"
fi

# ---- 5. (optional) database migration --------------------------------------
echo
if [[ $WITH_DB -eq 1 ]]; then
  c_y "[5/5] Running database migration (data is preserved; additive only)..."
  SQL="$FIXES_DIR/migrations/0004_enterprise_scale_and_plan.sql"
  c_y "      Backing up database first to $BACKUP_DIR/db_backup.sql ..."
  # reads DB creds from environment/.env; adjust the names if you use different
  run "pg_dump -h \"\${DB_HOST:-127.0.0.1}\" -p \"\${DB_PORT:-5432}\" -U \"\${DB_USER:-postgres}\" \"\${DB_NAME:-rk_trendz_mlm}\" -f \"$BACKUP_DIR/db_backup.sql\""
  run "psql -h \"\${DB_HOST:-127.0.0.1}\" -p \"\${DB_PORT:-5432}\" -U \"\${DB_USER:-postgres}\" -d \"\${DB_NAME:-rk_trendz_mlm}\" -v ON_ERROR_STOP=1 --single-transaction -f \"$SQL\""
else
  c_y "[5/5] Skipping DB migration. Run it AFTER backing up (or re-run with --with-db):"
  echo "      pg_dump -U postgres -d rk_trendz_mlm -f backup.sql"
  echo "      psql -U postgres -d rk_trendz_mlm -v ON_ERROR_STOP=1 --single-transaction \\"
  echo "           -f $FIXES_DIR/migrations/0004_enterprise_scale_and_plan.sql"
fi

echo
c_g "=============================================================="
c_g " DONE"
echo "  Originals backed up in: $BACKUP_DIR"
echo
echo "  ONE MANUAL STEP LEFT (Next.js dashboard) — add these 2 lines in"
echo "  frontend/src/app/dashboard/page.jsx:"
echo
echo "    import MyTeam from \"@/components/team/MyTeam\";   // near other imports"
echo "    <MyTeam />                                         // inside the Network/Team tab"
echo
echo "  Then restart:  stop the Flask server and run  python run.py"
echo "                 (or gunicorn in production — see deploy/deployment.md)"
c_g "=============================================================="
