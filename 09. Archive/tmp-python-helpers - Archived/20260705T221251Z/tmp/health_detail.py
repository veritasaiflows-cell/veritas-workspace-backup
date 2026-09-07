import json
from collections import Counter, defaultdict

with open(r'tmp\wf78-ticker-freshness-ledger.json') as f:
    ledger = json.load(f)

with open(r'tmp\wf78-source-open-repair-execution.json') as f:
    src_open = json.load(f)

with open(r'tmp\wf78-position-sizing-integration-proposal.json') as f:
    pos_sizing = json.load(f)

refreshable = [r for r in ledger['rows'] if r['overall_freshness_state'] == 'stale_refreshable']
source_open_rows = [r for r in ledger['rows'] if r['overall_freshness_state'] == 'stale_source_open']

print('=== STALE REFRESHABLE BREAKDOWN ===')
print(f'Total: {len(refreshable)}')
print()

tier_counter = Counter(r['auto_tier'] for r in refreshable)
print('By Tier:')
for t, c in tier_counter.most_common():
    print(f'  {t}: {c}')

fam_counter = Counter()
for r in refreshable:
    for f in r.get('stale_families', []):
        fam_counter[f] += 1
print()
print('Top Stale Families:')
for f, c in fam_counter.most_common(20):
    print(f'  {c:>3}  {f}')

# Which families get auto-freshened vs deferred
print()
print('Family state distribution (from family_states):')
fs_counter = Counter()
for r in refreshable:
    for fs in r.get('family_states', []):
        fs_counter[(fs['family'], fs['state'])] += 1
for k, c in fs_counter.most_common(20):
    print(f'  {c:>3}  {k[0]:<40} -> {k[1]}')

# Route state distribution
print()
print('Route state distribution (refreshable):')
rs_counter = Counter(r['route_state'] for r in refreshable)
for k, c in rs_counter.most_common():
    print(f'  {c:>3}  {k}')

# Per-tier stale families (top 3)
print()
print('Per-tier top stale families:')
tier_fam = defaultdict(Counter)
for r in refreshable:
    for f in r.get('stale_families', []):
        tier_fam[r['auto_tier']][f] += 1
for tier in ['Tier A', 'Tier B', 'Tier C']:
    print(f'  {tier}:')
    for f, c in tier_fam[tier].most_common(5):
        print(f'    {c:>3}  {f}')

print()
print('=== SOURCE-OPEN DETAIL ===')
print(f'Total: {len(source_open_rows)}')
print()

src_tier = Counter(r['auto_tier'] for r in source_open_rows)
print('By Tier:')
for t, c in src_tier.most_common():
    print(f'  {t}: {c}')

disp_counter = Counter(r.get('repair_disposition') for r in source_open_rows)
print()
print('By Repair Disposition:')
for d, c in disp_counter.most_common():
    print(f'  {c:>3}  {d}')

# By stale families
print()
print('Source-Open stale families:')
so_fam = Counter()
for r in source_open_rows:
    for f in r.get('stale_families', []):
        so_fam[f] += 1
for f, c in so_fam.most_common(20):
    print(f'  {c:>3}  {f}')

# By route state
print()
print('Route state (source-open):')
so_rs = Counter(r['route_state'] for r in source_open_rows)
for k, c in so_rs.most_common():
    print(f'  {c:>3}  {k}')

print()
print('=== SLA TARGETS ===')
# Group SLAs by tier
sla_groups = defaultdict(set)
for r in refreshable + source_open_rows:
    sla = r.get('sla', {})
    tier = r['auto_tier']
    state = r['overall_freshness_state']
    sla_groups[(tier, state)] = (sla.get('quote_technical_hours'), sla.get('evidence_hours'), sla.get('source_open_days'))
for k in sorted(sla_groups.keys()):
    print(f'  {k}: quote_tech={sla_groups[k][0]}h evidence={sla_groups[k][1]}h src_open={sla_groups[k][2]}d')

print()
print('=== SOURCE-OPEN REPAIR EXECUTION SUMMARY ===')
if 'summary' in src_open:
    s = src_open['summary']
    for k, v in s.items():
        if not isinstance(v, (list, dict)):
            print(f'  {k}: {v}')
        elif isinstance(v, list):
            print(f'  {k}: {len(v)} items')

print()
print('=== POSITION SIZING INTEGRATION PROPOSAL ===')
if 'summary' in pos_sizing:
    print(json.dumps(pos_sizing['summary'], indent=2)[:3000])
