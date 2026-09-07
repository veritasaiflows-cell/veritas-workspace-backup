import sqlite3
con=sqlite3.connect('tmp/veritas-canon-cache.sqlite')
con.row_factory=sqlite3.Row
rows=con.execute("select scope,field_name,field_value,source_artifact_path,last_reconciled_at_utc,authority_boundary,validator_status from canon_cache_fields where scope=? order by field_name", ('ETN',)).fetchall()
print(len(rows))
for r in rows:
    print(dict(r))
