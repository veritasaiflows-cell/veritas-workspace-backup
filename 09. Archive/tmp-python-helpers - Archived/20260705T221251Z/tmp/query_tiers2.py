import sqlite3, json

db_path = "state/finance/finance-canon.sqlite"
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

# Get tier counts
print("=== TIER COUNTS (universe_membership) ===")
for r in db.execute("SELECT tier, COUNT(*) as cnt FROM universe_membership GROUP BY tier ORDER BY tier").fetchall():
    print(f"  {r['tier']}: {r['cnt']}")

# Get reference_levels columns
print("\n=== reference_levels columns ===")
cols = [r[1] for r in db.execute("PRAGMA table_info(reference_levels)").fetchall()]
print(cols)

# Get sample reference_levels
print("\n=== reference_levels sample ===")
for r in db.execute("SELECT * FROM reference_levels LIMIT 3").fetchall():
    print(json.dumps(dict(r), default=str))

# Get securities columns
print("\n=== securities columns ===")
cols2 = [r[1] for r in db.execute("PRAGMA table_info(securities)").fetchall()]
print(cols2)

# Get evidence_freshness columns
print("\n=== evidence_freshness columns ===")
cols3 = [r[1] for r in db.execute("PRAGMA table_info(evidence_freshness)").fetchall()]
print(cols3)

# Get answer_path_scope columns
print("\n=== answer_path_scope columns ===")
cols4 = [r[1] for r in db.execute("PRAGMA table_info(answer_path_scope)").fetchall()]
print(cols4)

# Get sample answer_path_scope
print("\n=== answer_path_scope sample ===")
for r in db.execute("SELECT * FROM answer_path_scope LIMIT 3").fetchall():
    print(json.dumps(dict(r), default=str))

# Get evidence_status columns
print("\n=== evidence_status columns ===")
cols5 = [r[1] for r in db.execute("PRAGMA table_info(evidence_status)").fetchall()]
print(cols5)

# Get sample evidence_status
print("\n=== evidence_status sample ===")
for r in db.execute("SELECT * FROM evidence_status LIMIT 3").fetchall():
    print(json.dumps(dict(r), default=str))