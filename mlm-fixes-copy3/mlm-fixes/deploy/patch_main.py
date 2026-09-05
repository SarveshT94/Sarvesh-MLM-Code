#!/usr/bin/env python3
"""
Safely remove the DUPLICATE team/genealogy routes from app/routes/main.py.
Backs the file up first. Idempotent (safe to run twice).
"""
import sys, time, shutil, os

path = sys.argv[1] if len(sys.argv) > 1 else "app/routes/main.py"
if not os.path.exists(path):
    print(f"  ! {path} not found - skipped.")
    sys.exit(0)

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

def block_bounds(lines, needle):
    # 1) find the @main.route(...) decorator line that contains `needle`
    start = None
    for i, ln in enumerate(lines):
        if needle in ln and ln.lstrip().startswith("@main.route"):
            start = i
            break
    if start is None:
        return None
    # 2) from start, find the `def ` line (skipping stacked decorators)
    def_line = None
    for j in range(start + 1, min(start + 6, len(lines))):
        if lines[j].lstrip().startswith("def "):
            def_line = j
            break
    if def_line is None:
        return None
    # 3) end = first NON-blank line AFTER def that starts at column 0
    #    (next top-level decorator / banner comment / statement). The
    #    function body is indented, so any col-0 line means we've left it.
    end = len(lines)
    for k in range(def_line + 1, len(lines)):
        s = lines[k]
        if s.strip() == "":
            continue
        if not s[0].isspace():      # column 0 -> left the function body
            end = k
            break
    return start, end

removed = []
for needle in ['"/api/team/me"', '"/api/genealogy/me"']:
    b = block_bounds(lines, needle)
    if b is None:
        print(f"  - route {needle}: already absent")
        continue
    s, e = b
    n = sum(1 for x in lines[s:e] if x.strip())
    removed.append((s, e, n))
    for k in range(s, e):
        lines[k] = ""

if removed:
    shutil.copy(path, path + f".bak-{int(time.time())}")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    for s, e, n in removed:
        print(f"  - removed duplicate route block ({n} code lines) near line {s+1}")
    print("  - backup written next to main.py as main.py.bak-*")
else:
    print("  - nothing to remove (already patched).")
