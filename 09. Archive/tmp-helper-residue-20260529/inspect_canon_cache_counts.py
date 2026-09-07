import json
import sqlite3
from pathlib import Path
p = Path('tmp/veritas-canon-cache.sqlite')
con = sqlite3.connect(p)
cur = con.cursor()
tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table' order by name").fetchall()]
counts = {}
for t in tables:
    counts[t] = cur.execute(f'select count(*) from "{t}"').fetchone()[0]
print(json.dumps({'db': str(p), 'tables': tables, 'row_counts': counts}, indent=2))
