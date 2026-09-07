import sqlite3
from pathlib import Path
p=Path('tmp/veritas-canon-cache.sqlite')
print('exists', p.exists(), 'mtime_ns', p.stat().st_mtime_ns if p.exists() else None)
con=sqlite3.connect(p)
con.row_factory=sqlite3.Row
print('tables')
for row in con.execute("select name from sqlite_master where type='table' order by name"):
    print('-', row['name'])
print('columns')
for row in con.execute("pragma table_info(canon_cache)"):
    print(dict(row))
print('ETN rows')
try:
    rows=con.execute("select * from canon_cache where scope like ? or cache_key like ? or entity like ? limit 50", ('%ETN%','%ETN%','%ETN%')).fetchall()
except Exception as e:
    print('query_error', e)
    rows=[]
for row in rows:
    print(dict(row))
