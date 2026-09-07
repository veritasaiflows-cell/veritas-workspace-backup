import json, sqlite3

db = sqlite3.connect('state/finance/finance-canon.sqlite')
db.row_factory = sqlite3.Row

tickers = ['META', 'MSFT', 'NVDA', 'PH', 'VRT', 'XOM']
for t in tickers:
    rs = db.execute("SELECT * FROM tier_routing_state WHERE ticker = ?", (t,)).fetchone()
    rl = db.execute("SELECT * FROM reference_levels WHERE ticker = ?", (t,)).fetchone()
    ef = db.execute("SELECT * FROM evidence_freshness WHERE ticker = ?", (t,)).fetchone()
    sec = db.execute("SELECT * FROM securities WHERE ticker = ?", (t,)).fetchone()
    
    print(f"\n=== {t} ===")
    if rs:
        print(f"  auto_state: {rs['auto_state']}")
        print(f"  route_reason: {rs['route_reason']}")
        print(f"  data_confidence: {rs['data_confidence_rating']}")
        print(f"  fundamentals_confidence: {rs['fundamentals_confidence']}")
        print(f"  tier_a_confidence_status: {rs['tier_a_confidence_status']}")
    if rl:
        print(f"  band_low: {rl['reference_price_low']}")
        print(f"  band_high: {rl['reference_price_high']}")
        print(f"  stop: {rl['reference_invalidation_level']}")
        print(f"  band_status: {rl['reference_band_status']}")
        print(f"  source_date: {rl['source_generated_at_utc']}")
    if ef:
        print(f"  resolution_state: {ef['resolution_state']}")
        print(f"  stale_families: {ef['stale_families_json']}")
        print(f"  card_generated: {ef['card_generated_at_utc']}")
    if sec:
        print(f"  name: {sec['name']}")
        print(f"  sector: {sec['sector']}")
        print(f"  instrument_type: {sec['instrument_type']}")
db.close()