import json, sqlite3

db = sqlite3.connect('state/finance/finance-canon.sqlite')
db.row_factory = sqlite3.Row

# List all tables
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
table_names = [t['name'] for t in tables]
print("Tables:", table_names)

# Find tier-related tables/columns
for tname in table_names:
    cols = db.execute(f"PRAGMA table_info({tname})").fetchall()
    col_names = [c['name'] for c in cols]
    has_tier = any('tier' in c.lower() for c in col_names)
    if has_tier:
        print(f"\nTable {tname} has tier columns: {[c for c in col_names if 'tier' in c.lower()]}")
        # Count tier A
        try:
            rows = db.execute(f"SELECT * FROM {tname} LIMIT 2").fetchall()
            for r in rows:
                print(json.dumps(dict(r), indent=2, default=str)[:500])
        except Exception as e:
            print(f"  Error reading: {e}")