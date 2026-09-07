import sqlite3, json, sys

db_path = "state/finance/finance-canon.sqlite"
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

# List all tables
print("=== TABLES ===")
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
    print(r[0])

# Find tier-related tables
print("\n=== TIER TABLES ===")
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
tier_tables = [t for t in tables if 'tier' in t.lower() or 'routing' in t.lower() or 'universe' in t.lower()]
for t in tier_tables:
    print(f"\n--- {t} ---")
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({t})").fetchall()]
    print("Columns:", cols)
    rows = db.execute(f"SELECT * FROM {t}").fetchall()
    print(f"Row count: {len(rows)}")
    for row in rows[:5]:
        print(json.dumps(dict(row), default=str))