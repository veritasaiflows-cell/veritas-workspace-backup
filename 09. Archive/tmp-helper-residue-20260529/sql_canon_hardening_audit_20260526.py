import json, sqlite3, hashlib
from pathlib import Path
DB=Path('tmp/veritas-canon-cache.sqlite')
out=Path('tmp/sql-canon-hardening-audit-2026-05-26.json')
con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
rows=[dict(r) for r in con.execute('select * from canon_cache_fields order by scope, field_name')]
meta={r['key']:r['value'] for r in con.execute('select key,value from canon_cache_meta')}
fields={}
for r in rows:
    fields[r['field_name']]=fields.get(r['field_name'],0)+1
boundaries={}
for r in rows:
    boundaries[r['authority_boundary']]=boundaries.get(r['authority_boundary'],0)+1
entry_fields={'reference_price_low','reference_price_high','reference_invalidation_level','reference_level_source_timestamp','reference_level_source_sha256','reference_level_owner_source_path'}
entry_rows=[r for r in rows if r['field_name'] in entry_fields]
tickers=sorted({r['scope'] for r in entry_rows})
by_ticker={t:{r['field_name']:r['field_value'] for r in entry_rows if r['scope']==t} for t in tickers}
report={
 'schema_version':'sql_canon_hardening_audit.v1',
 'db_path':str(DB).replace('\\','/'),
 'row_count':len(rows),
 'meta':meta,
 'field_counts':fields,
 'authority_boundary_counts':boundaries,
 'entry_stop_reference':{'ticker_count':len(tickers),'key_count':len(entry_rows),'fields':sorted(entry_fields),'tickers':tickers,'ETN':by_ticker.get('ETN')},
 'low_risk_or_other_key_count':len(rows)-len(entry_rows),
 'authority_false_flags':{'portfolio_mutation_allowed':False,'owner_approval_inferred':False,'trade_or_account_action_allowed':False,'paper_or_live_execution_allowed':False},
 'source_hash': hashlib.sha256(DB.read_bytes()).hexdigest(),
}
out.write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
print(json.dumps({'status':'ok','row_count':len(rows),'entry_stop_key_count':len(entry_rows),'ticker_count':len(tickers),'ETN':report['entry_stop_reference']['ETN'],'output':str(out)},indent=2))
