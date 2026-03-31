from app import create_app

# Initialize your app to load all Blueprints
app = create_app()

print("\n--- RK TRENDZ ROUTE AUDIT ---")
print(f"{'ENDPOINT':<35} {'METHODS':<15} {'URL PATH'}")
print("-" * 80)

# Sort rules by path so it's easy to read
rules = sorted(app.url_map.iter_rules(), key=lambda x: x.rule)

for rule in rules:
    # We skip 'static' because those are just CSS/JS files
    if "static" not in rule.endpoint:
        # Filter out internal Flask methods like OPTIONS/HEAD
        methods = ', '.join(sorted(list(rule.methods - {'OPTIONS', 'HEAD'})))
        print(f"{rule.endpoint:<35} {methods:<15} {rule.rule}")

print("-" * 80)
print(f"Total Logic Routes: {len([r for r in rules if 'static' not in r.endpoint])}\n")
