import json
import datetime
from pathlib import Path

p = json.loads(Path('tmp/band-proposals.json').read_text(encoding='utf-8'))
rows = []
for x in p.get('proposals', []):
    if x.get('ticker') == 'ETN':
        continue
    eligible = x.get('canonical_apply_eligible') is True
    needs = x.get('needs_review') is True
    if eligible and needs:
        rec = 'APPROVE_CANDIDATE'
    elif eligible and not needs:
        rec = 'OPTIONAL_WITHIN_TOLERANCE'
    else:
        rec = 'DO_NOT_APPROVE_FOR_CANON'
    rows.append({
        'ticker': x.get('ticker'),
        'recommendation': rec,
        'eligible': eligible,
        'lane': x.get('coverage_lane'),
        'workflow_state': x.get('workflow_state'),
        'entry_policy': x.get('entry_policy'),
        'band_status': x.get('band_status'),
        'earnings_state': x.get('earnings_state'),
        'current': {'low': x.get('current_band_low'), 'high': x.get('current_band_high'), 'stop': x.get('current_stop')},
        'proposed': {'low': x.get('suggested_band_low'), 'high': x.get('suggested_band_high'), 'stop': x.get('suggested_stop')},
        'reason_summary': x.get('reasons') or [],
    })

out = {
    'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'manual owner review proposal for non-ETN entry bands; no changes applied',
    'authority': {
        'trade_or_account_authority': False,
        'owner_approval_inferred': False,
        'sizing_sleeve_cash_risk_rule_authority': False,
        'canon_update_requires_randall_reply': True,
    },
    'rows': rows,
}
Path('tmp/manual-entry-band-canon-update-proposal.json').write_text(json.dumps(out, indent=2), encoding='utf-8')

lines = [
    '# Manual Entry-Band Canon Update Proposal',
    '',
    f"Generated: {out['generated_at_utc']}",
    '',
    'Scope: non-ETN entry-band proposals from `tmp/band-proposals.json`. No changes applied.',
    '',
    'Authority: review proposal only; no trades, sizing, sleeve/cash/risk-rule, execution entitlement, or owner approval inferred.',
    '',
    '| Ticker | Recommendation | Current band / stop | Proposed band / stop | Why |',
    '|---|---|---:|---:|---|',
]
for r in rows:
    why = '; '.join(r['reason_summary']) or f"{r['band_status']} / {r['workflow_state']}"
    why = why.replace('|', '/').replace('\n', ' ')[:240]
    lines.append(
        f"| {r['ticker']} | {r['recommendation']} | "
        f"{r['current']['low']}-{r['current']['high']} / {r['current']['stop']} | "
        f"{r['proposed']['low']}-{r['proposed']['high']} / {r['proposed']['stop']} | {why} |"
    )
Path('tmp/manual-entry-band-canon-update-proposal.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('wrote tmp/manual-entry-band-canon-update-proposal.json')
print('wrote tmp/manual-entry-band-canon-update-proposal.md')
