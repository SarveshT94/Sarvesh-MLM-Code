#!/usr/bin/env python3
"""
Auto-wire the My Team drill-down widget into the Next.js dashboard.

- Adds:  import MyTeam from "@/components/team/MyTeam";
- Renders <MyTeam /> on the "My Network Tree" tab (above the existing content).
- Removes the OLD services/team.js so it can't clash with the new team.ts
  (team.ts keeps the same exports, so the existing import keeps working).

Backs up every file it touches. Idempotent (safe to run twice).
"""
import os, re, sys, time, shutil

DASH = "frontend/src/app/dashboard/page.jsx"
OLD_TEAM_JS = "frontend/src/services/team.js"
IMPORT_LINE = 'import MyTeam from "@/components/team/MyTeam";'
RENDER_NEEDLE = '{activeTab === "My Network Tree" && <NetworkTab />}'
RENDER_REPL = ('{activeTab === "My Network Tree" && '
               '<><MyTeam /><NetworkTab /></>}')


def backup(path):
    shutil.copy(path, f"{path}.bak-{int(time.time())}")


def main(proj):
    dash = os.path.join(proj, DASH)
    if not os.path.exists(dash):
        print(f"  ! dashboard not found at {DASH} - skipped wiring.")
        return

    with open(dash, "r", encoding="utf-8") as f:
        src = f.read()
    original = src

    # 1) Import
    if "components/team/MyTeam" not in src:
        # insert after the existing team-services import, else after first import
        m = re.search(r'^import .*@/services/team.*$', src, flags=re.M)
        if m:
            idx = m.end()
            src = src[:idx] + "\n" + IMPORT_LINE + src[idx:]
        else:
            src = IMPORT_LINE + "\n" + src
        print("  - added MyTeam import")
    else:
        print("  - MyTeam import already present")

    # 2) Render in the Network tab
    if "<MyTeam />" not in src:
        if RENDER_NEEDLE in src:
            src = src.replace(RENDER_NEEDLE, RENDER_REPL)
            print("  - mounted <MyTeam /> in the My Network Tree tab")
        else:
            print("  ! could not find the Network tab render line - "
                  "add <MyTeam /> manually.")
    else:
        print("  - <MyTeam /> already rendered")

    if src != original:
        backup(dash)
        with open(dash, "w", encoding="utf-8") as f:
            f.write(src)

    # 3) Remove old team.js (team.ts replaces it with identical exports)
    old = os.path.join(proj, OLD_TEAM_JS)
    if os.path.exists(old):
        backup(old)
        os.remove(old)
        print("  - removed old services/team.js (replaced by team.ts)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
