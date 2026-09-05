#!/usr/bin/env python3
"""Add the Store links to the admin sidebar (app/templates/admin/base.html). Idempotent."""
import sys, os, re, shutil, time
target = sys.argv[1] if len(sys.argv) > 1 else "."
path = os.path.join(target, "app/templates/admin/base.html")
if not os.path.exists(path):
    print("  ! admin base.html not found - skipped"); sys.exit(0)
s = open(path, encoding="utf-8").read()
if "/admin/store" in s:
    print("  - store links already present"); sys.exit(0)
links = ('            <a href="/admin/store" class="{% if request.path == \'/admin/store\' %}active{% endif %}">\n'
         '                <i class="bi bi-shop"></i> Store Dashboard\n            </a>\n'
         '            <a href="/admin/store/products" class="{% if request.path.startswith(\'/admin/store/products\') %}active{% endif %}">\n'
         '                <i class="bi bi-box-seam"></i> Products & Categories\n            </a>\n'
         '            <a href="/admin/store/orders" class="{% if request.path.startswith(\'/admin/store/orders\') %}active{% endif %}">\n'
         '                <i class="bi bi-truck"></i> Store Orders & Tracking\n            </a>\n')
# insert right after the packages/plans <a>...</a> block if present, else before the logout link
m = re.search(r'^[ \t]*<a href="/admin/packages".*?</a>[ \t]*\n', s, re.M | re.S)
if m:
    s = s[:m.end()] + links + s[m.end():]
else:
    m = re.search(r'^[ \t]*<a href="/admin/logout"', s, re.M)
    if not m:
        print("  ! could not find an anchor point in sidebar - add links manually"); sys.exit(0)
    s = s[:m.start()] + links + s[m.start():]
shutil.copy(path, path + f".bak-{int(time.time())}")
open(path, "w", encoding="utf-8").write(s)
print("  - store links added to admin sidebar")
