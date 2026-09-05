#!/usr/bin/env python3
"""
Auto-wire the new member features into the Next.js dashboard
(frontend/src/app/dashboard/page.jsx).

  1. My Team drill-down  ->  <MyTeam /> on the "My Network Tree" tab
  2. E-commerce store    ->  "Product Catalog" tab now renders <Storefront />
                             "My Orders & Invoices" tab renders <MyStoreOrders />
                             (menu labels become "Shop" / "My Orders")
  3. Removes the OLD services/team.js (team.ts replaces it, same exports)

Backs up every file it touches. Idempotent (safe to run twice).
"""
import os, re, sys, time, shutil

DASH = "frontend/src/app/dashboard/page.jsx"
OLD_TEAM_JS = "frontend/src/services/team.js"

TEAM_IMPORT = 'import MyTeam from "@/components/team/MyTeam";'
STORE_IMPORTS = ('import Storefront from "@/components/store/Storefront";\n'
                 'import MyStoreOrders from "@/components/store/MyStoreOrders";')

TEAM_NEEDLE = '{activeTab === "My Network Tree" && <NetworkTab />}'
TEAM_REPL = '{activeTab === "My Network Tree" && <><MyTeam /><NetworkTab /></>}'

CATALOG_NEEDLE = '{activeTab === "Product Catalog" && <ProductCatalogTab />}'
CATALOG_REPL = ('{activeTab === "Product Catalog" && '
                '<Storefront onOrderPlaced={() => setActiveTab("My Orders & Invoices")} />}')
ORDERS_NEEDLE = '{activeTab === "My Orders & Invoices" && <OrdersTab />}'
ORDERS_REPL = '{activeTab === "My Orders & Invoices" && <MyStoreOrders />}'

MENU_CATALOG = '{ name: "Product Catalog", icon: ShoppingBag }'
MENU_CATALOG_REPL = '{ name: "Product Catalog", label: "Shop", icon: ShoppingBag }'
MENU_ORDERS = '{ name: "My Orders & Invoices", icon: Receipt }'
MENU_ORDERS_REPL = '{ name: "My Orders & Invoices", label: "My Orders", icon: Receipt }'


def backup(path):
    shutil.copy(path, f"{path}.bak-{int(time.time())}")


def add_import(src, line, marker):
    if marker in src:
        return src, False
    m = re.search(r'^import .*@/services/team.*$', src, flags=re.M)
    if m:
        idx = m.end()
        return src[:idx] + "\n" + line + src[idx:], True
    return line + "\n" + src, True


def main(proj):
    dash = os.path.join(proj, DASH)
    if not os.path.exists(dash):
        print(f"  ! dashboard not found at {DASH} - skipped wiring.")
        return

    with open(dash, "r", encoding="utf-8") as f:
        src = f.read()
    original = src

    # ---- imports
    src, ch = add_import(src, TEAM_IMPORT, "components/team/MyTeam")
    print("  - added MyTeam import" if ch else "  - MyTeam import already present")
    src, ch = add_import(src, STORE_IMPORTS, "components/store/Storefront")
    print("  - added Storefront/MyStoreOrders imports" if ch else "  - store imports already present")

    # ---- My Team
    if "<MyTeam />" not in src:
        if TEAM_NEEDLE in src:
            src = src.replace(TEAM_NEEDLE, TEAM_REPL)
            print("  - mounted <MyTeam /> in the My Network Tree tab")
        else:
            print("  ! Network tab render line not found - add <MyTeam /> manually.")
    else:
        print("  - <MyTeam /> already rendered")

    # ---- Store (replaces the old package catalog + orders tabs)
    if "<Storefront" not in src:
        if CATALOG_NEEDLE in src:
            src = src.replace(CATALOG_NEEDLE, CATALOG_REPL)
            print("  - Product Catalog tab now renders <Storefront />")
        else:
            print("  ! Product Catalog render line not found - add <Storefront /> manually.")
    else:
        print("  - <Storefront /> already rendered")

    if "<MyStoreOrders" not in src:
        if ORDERS_NEEDLE in src:
            src = src.replace(ORDERS_NEEDLE, ORDERS_REPL)
            print("  - Orders tab now renders <MyStoreOrders />")
        else:
            print("  ! Orders render line not found - add <MyStoreOrders /> manually.")
    else:
        print("  - <MyStoreOrders /> already rendered")

    # ---- Menu labels (keep the internal tab names so all existing links work)
    if MENU_CATALOG in src:
        src = src.replace(MENU_CATALOG, MENU_CATALOG_REPL)
    if MENU_ORDERS in src:
        src = src.replace(MENU_ORDERS, MENU_ORDERS_REPL)
    # Render label if present: {item.name} -> {item.label || item.name}
    # (only inside the sidebar menu map; conservative regex)
    if "item.label || item.name" not in src:
        new_src, n = re.subn(r'(?<!key=)\{item\.name\}', '{item.label || item.name}', src)
        if n:
            src = new_src
            print(f"  - sidebar shows Shop / My Orders labels ({n} spot(s))")

    # Overview "Upgrade Plan" button text -> Shop now
    src = src.replace('btnText: "Upgrade Plan"', 'btnText: "Shop & Activate"')

    if src != original:
        backup(dash)
        with open(dash, "w", encoding="utf-8") as f:
            f.write(src)

    old = os.path.join(proj, OLD_TEAM_JS)
    if os.path.exists(old):
        backup(old)
        os.remove(old)
        print("  - removed old services/team.js (replaced by team.ts)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
