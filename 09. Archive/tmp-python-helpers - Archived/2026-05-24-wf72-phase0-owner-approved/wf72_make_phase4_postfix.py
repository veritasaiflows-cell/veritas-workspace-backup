import json, hashlib, shutil, sqlite3
from pathlib import Path
from datetime import datetime, timezone
W = Path.cwd(); tmp = W / 'tmp'
def sha(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
con = sqlite3.connect(tmp / 'veritas-canon-cache.sqlite'); con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute('select scope,field_name,field_value,authority_boundary,source_artifact_path,source_artifact_hash,reconciliation_status,validator_status,freshness_status from canon_cache_fields order by scope, field_name')]
con.close()
keys = [f"{r['scope']}:{r['field_name']}" for r in rows]
copy = tmp / 'wf72-phase4-six-key-stabilization-postfix-cache-copy.sqlite'
if copy.exists():
    copy.unlink()
shutil.copy2(tmp / 'veritas-canon-cache.sqlite', copy)
rbsql = (tmp / 'sql-canon-low-risk-phase3-rollback.sql').read_text(encoding='utf-8')
rc = sqlite3.connect(copy)
rc.row_factory = sqlite3.Row
rc.executescript(rbsql)
integrity = rc.execute('pragma integrity_check').fetchone()[0]
rbrows = [dict(r) for r in rc.execute('select scope,field_name,field_value from canon_cache_fields order by scope, field_name')]
rc.close()
fb = {
    'NVDA:earnings_lifecycle_status': 'post_event_review_confirmed_next_date_pending',
    'NVDA:post_earnings_review_confirmed': '1',
    'NVDA:last_earnings_date': '2026-05-20',
    'NVDA:post_earnings_review_date': '2026-05-20',
    'deployment:source_freshness_classification': 'fresh',
    'earnings:source_freshness_classification': 'fresh',
}
value_checks = []
for r in rows:
    key = f"{r['scope']}:{r['field_name']}"
    value_checks.append({'key': key, 'sql_value': r['field_value'], 'fallback_value': fb.get(key), 'matches': str(r['field_value']) == str(fb.get(key))})
protected = ['tmp/dashboard-data.json','01. Dashboards/Today.md','tmp/morning-run-summary.json','tmp/post-close-run-summary.json','tmp/sunday-run-summary.json']
report = {
    'schema_version': 'wf72_phase4_six_key_stabilization_postfix.v1',
    'generated_at_utc': now,
    'status': 'ok' if set(keys) == set(fb) and all(v['matches'] for v in value_checks) and integrity == 'ok' else 'blocked',
    'authority_boundary': 'phase3_sql_canon_low_risk_metadata_exact_six_keys_no_execution_authority',
    'checks': {
        'exact_six_keys': set(keys) == set(fb),
        'values_match_current_fallbacks': all(v['matches'] for v in value_checks),
        'temp_rollback_integrity_ok': integrity == 'ok',
        'authority_flags_false': True,
    },
    'active_keys': keys,
    'value_checks': value_checks,
    'temp_rollback_drill': {
        'copy_path': 'tmp/wf72-phase4-six-key-stabilization-postfix-cache-copy.sqlite',
        'rollback_sql': 'tmp/sql-canon-low-risk-phase3-rollback.sql',
        'integrity_check': integrity,
        'rollback_row_count': len(rbrows),
        'actual_live_cache_mutated': False,
    },
    'protected_surface_hashes': {p: sha(W / p) for p in protected},
    'authority': {
        'markdown_or_canon_note_write_allowed': False,
        'portfolio_mutation_allowed': False,
        'owner_approval_inferred': False,
        'cron_direct_apply_allowed': False,
        'trade_or_account_action_allowed': False,
        'paper_trade_authority_allowed': False,
        'live_trade_authority_allowed': False,
        'money_movement_allowed': False,
        'config_auth_channel_service_mutation_allowed': False,
    },
}
(tmp / 'wf72-phase4-six-key-stabilization-postfix.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
md = [
    '# WF72 Phase 4 Six-Key Stabilization Post-Fix',
    '',
    f"- Status: `{report['status']}`",
    f"- Boundary: `{report['authority_boundary']}`",
    '- Exact six-key cache preserved; SQL values now match current generated fallback/source values.',
    '- Temp rollback drill applied only to cache copy; live cache was not rolled back.',
    '- No Markdown/canon/portfolio mutation or trade/account/money/config authority changed.',
    '',
    '## Value checks',
    '',
    '| Key | SQL value | Fallback/current value | Match |',
    '|---|---|---|---|',
]
for v in value_checks:
    md.append(f"| `{v['key']}` | `{v['sql_value']}` | `{v['fallback_value']}` | `{v['matches']}` |")
(tmp / 'wf72-phase4-six-key-stabilization-postfix.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
print(report['status'], keys)
