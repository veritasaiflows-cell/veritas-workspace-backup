import sqlite3, json, os
from pathlib import Path
root=Path('.')
dbs=['tmp/veritas-artifact-index.sqlite','tmp/veritas-canon-cache.sqlite','tmp/workspace-index.sqlite']
out={}
for db in dbs:
    p=Path(db)
    info={'exists':p.exists(),'size_bytes':p.stat().st_size if p.exists() else None}
    if p.exists():
        con=sqlite3.connect(f'file:{p}?mode=ro', uri=True)
        con.row_factory=sqlite3.Row
        info['pragma']={}
        for pr in ['journal_mode','foreign_keys','user_version','schema_version','page_count','page_size']:
            try: info['pragma'][pr]=con.execute(f'PRAGMA {pr}').fetchone()[0]
            except Exception as e: info['pragma'][pr]=repr(e)
        objs=con.execute("select type,name,tbl_name,sql from sqlite_master where type in ('table','view','index','trigger') order by type,name").fetchall()
        info['objects']=[dict(r) for r in objs]
        counts={}
        for r in objs:
            if r['type'] in ('table','view') and not r['name'].startswith('sqlite_'):
                try: counts[r['name']]=con.execute(f"select count(*) from [{r['name']}]").fetchone()[0]
                except Exception as e: counts[r['name']]=f'ERR:{e}'
        info['row_counts']=counts
        idx=[]
        for r in objs:
            if r['type']=='table' and not r['name'].startswith('sqlite_'):
                try:
                    idx.append({'table':r['name'],'columns':[dict(x) for x in con.execute(f'PRAGMA table_info([{r["name"]}])').fetchall()]})
                except Exception: pass
        info['tables']=idx
        con.close()
    out[db]=info
Path('tmp/sql-audit-probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:{'exists':v['exists'],'size_bytes':v['size_bytes'],'objects':len(v.get('objects',[])),'row_counts':v.get('row_counts',{})} for k,v in out.items()},indent=2))
