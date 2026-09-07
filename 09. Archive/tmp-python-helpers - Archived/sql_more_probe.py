import sqlite3,json
from pathlib import Path
p=Path('tmp/finance-stack-snapshot.sqlite')
out={'exists':p.exists(),'size':p.stat().st_size if p.exists() else None}
if p.exists():
 con=sqlite3.connect(f'file:{p}?mode=ro',uri=True); con.row_factory=sqlite3.Row
 objs=con.execute("select type,name,sql from sqlite_master where type in ('table','view','index') order by type,name").fetchall()
 out['objects']=[dict(o) for o in objs]
 out['counts']={}
 for o in objs:
  if o['type'] in ('table','view') and not o['name'].startswith('sqlite_'):
   try: out['counts'][o['name']]=con.execute(f"select count(*) from [{o['name']}]").fetchone()[0]
   except Exception as e: out['counts'][o['name']]=repr(e)
 con.close()
Path('tmp/sql-more-probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'finance_stack_snapshot':{'exists':out['exists'],'size':out['size'],'counts':out.get('counts',{})}},indent=2))