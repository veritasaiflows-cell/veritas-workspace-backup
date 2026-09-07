import sqlite3, json

db_path = "state/finance/finance-canon.sqlite"
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

# Join universe_membership + securities + reference_levels + tier_routing_state + evidence_freshness
query = """
SELECT 
    um.ticker,
    um.tier,
    s.name,
    s.sector,
    trs.auto_state,
    trs.route_reason,
    trs.route_priority,
    trs.tier_a_confidence_status,
    trs.data_confidence_rating,
    trs.tier_c_attention_score,
    rl.reference_price_low,
    rl.reference_price_high,
    rl.reference_invalidation_level,
    rl.reference_band_status,
    rl.reference_confidence,
    ef.provider_status,
    ef.resolution_state,
    ef.source_confidence_class,
    ef.card_generated_at_utc
FROM universe_membership um
LEFT JOIN securities s ON um.ticker = s.ticker
LEFT JOIN tier_routing_state trs ON um.ticker = trs.ticker
LEFT JOIN reference_levels rl ON um.ticker = rl.ticker
LEFT JOIN evidence_freshness ef ON um.ticker = ef.ticker
ORDER BY um.tier, um.ticker
"""

rows = db.execute(query).fetchall()

# Also parse the raw_json from tier_routing_state for the embedded band_status
tier_a = []
tier_b = []
tier_c = []

for r in rows:
    row = dict(r)
    # Parse raw_json for band_status
    band_status = None
    latest_price = None
    if row.get('reference_band_status') is None and row.get('raw_json'):
        pass
    
    # Use reference_band_status from reference_levels directly, or try to parse from raw_json
    bs = row.get('reference_band_status')
    
    # Try parsing the nested raw_json for sql_canon_reference.reference_band_status
    if not bs:
        try:
            raw = json.loads(row.get('raw_json', '{}')) if row.get('raw_json') else {}
            fis_ref = raw.get('finance_intelligence_state_entry_stop_reference', {})
            sql_ref = fis_ref.get('sql_canon_reference', {})
            bs = sql_ref.get('reference_band_status')
        except:
            pass
    
    entry = {
        'ticker': row['ticker'],
        'name': row.get('name', ''),
        'tier': row['tier'],
        'sector': row.get('sector', ''),
        'auto_state': row.get('auto_state', ''),
        'route_priority': row.get('route_priority'),
        'route_reason': row.get('route_reason', ''),
        'tier_a_confidence': row.get('tier_a_confidence_status'),
        'data_confidence': row.get('data_confidence_rating'),
        'tier_c_score': row.get('tier_c_attention_score'),
        'band_low': row.get('reference_price_low'),
        'band_high': row.get('reference_price_high'),
        'stop': row.get('reference_invalidation_level'),
        'band_status': bs,
        'reference_confidence': row.get('reference_confidence'),
        'provider_status': row.get('provider_status'),
        'resolution_state': row.get('resolution_state'),
        'source_confidence': row.get('source_confidence_class'),
        'card_generated_at': row.get('card_generated_at_utc'),
    }
    
    if row['tier'] == 'A':
        tier_a.append(entry)
    elif row['tier'] == 'B':
        tier_b.append(entry)
    elif row['tier'] == 'C':
        tier_c.append(entry)

# Sort Tier A by route_priority asc, then ticker
tier_a.sort(key=lambda x: (x.get('route_priority') or 999, x['ticker']))
# Sort Tier B by route_priority asc, then ticker  
tier_b.sort(key=lambda x: (x.get('route_priority') or 999, x['ticker']))
# Sort Tier C by tier_c_score desc, then ticker
tier_c.sort(key=lambda x: (-(x.get('tier_c_score') or 0), x['ticker']))

print("=" * 120)
print("TIER A - TOP 5 (by route priority)")
print("=" * 120)
print(f"{'Ticker':<8} {'Name':<25} {'Sector':<20} {'State':<20} {'Band Low':>10} {'Band High':>10} {'Stop':>10} {'Band Status':<15} {'Priority':>8}")
print("-" * 120)
for e in tier_a[:5]:
    print(f"{e['ticker']:<8} {(e['name'] or '')[:25]:<25} {(e['sector'] or '')[:20]:<20} {(e['auto_state'] or '')[:20]:<20} {(str(e['band_low']) or 'N/A'):>10} {(str(e['band_high']) or 'N/A'):>10} {(str(e['stop']) or 'N/A'):>10} {(e['band_status'] or 'N/A'):<15} {(str(e['route_priority']) or 'N/A'):>8}")

print()
print("=" * 120)
print("TIER B - TOP 5 (by route priority)")
print("=" * 120)
print(f"{'Ticker':<8} {'Name':<25} {'Sector':<20} {'State':<20} {'Band Low':>10} {'Band High':>10} {'Stop':>10} {'Band Status':<15} {'Priority':>8}")
print("-" * 120)
for e in tier_b[:5]:
    print(f"{e['ticker']:<8} {(e['name'] or '')[:25]:<25} {(e['sector'] or '')[:20]:<20} {(e['auto_state'] or '')[:20]:<20} {(str(e['band_low']) or 'N/A'):>10} {(str(e['band_high']) or 'N/A'):>10} {(str(e['stop']) or 'N/A'):>10} {(e['band_status'] or 'N/A'):<15} {(str(e['route_priority']) or 'N/A'):>8}")

print()
print("=" * 120)
print("TIER C - TOP 5 (by attention score)")
print("=" * 120)
print(f"{'Ticker':<8} {'Name':<25} {'Sector':<20} {'State':<20} {'Band Low':>10} {'Band High':>10} {'Stop':>10} {'Band Status':<15} {'Att Score':>10}")
print("-" * 120)
for e in tier_c[:5]:
    print(f"{e['ticker']:<8} {(e['name'] or '')[:25]:<25} {(e['sector'] or '')[:20]:<20} {(e['auto_state'] or '')[:20]:<20} {(str(e['band_low']) or 'N/A'):>10} {(str(e['band_high']) or 'N/A'):>10} {(str(e['stop']) or 'N/A'):>10} {(e['band_status'] or 'N/A'):<15} {(str(e['tier_c_score']) or 'N/A'):>10}")

# Print full details as JSON for verification
print()
print("=== FULL JSON ===")
print(json.dumps({
    'tier_a_top5': tier_a[:5],
    'tier_b_top5': tier_b[:5],
    'tier_c_top5': tier_c[:5],
}, indent=2, default=str))