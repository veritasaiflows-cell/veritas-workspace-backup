import json, sqlite3

db = sqlite3.connect('state/finance/finance-canon.sqlite')
db.row_factory = sqlite3.Row

tickers = ['BRK.B','CME','ETN','GOOG','GS','ITA','JPM','LIN','LMT','META','MSFT','NVDA','PH','VRT','XOM']

print("=== TIER ROUTING STATE ===")
for t in tickers:
    rs = db.execute("SELECT ticker, auto_state, route_reason, route_priority, data_confidence_rating, fundamentals_confidence, tier_a_confidence_status, critical_data_conflict_count, capital_deployment_approved, trade_or_execution_approved FROM tier_routing_state WHERE ticker = ?", (t,)).fetchone()
    if rs:
        print(f"{rs['ticker']}: state={rs['auto_state']} prio={rs['route_priority']} conf={rs['data_confidence_rating']} fund_conf={rs['fundamentals_confidence']} ta_conf={rs['tier_a_confidence_status']} conflicts={rs['critical_data_conflict_count']} cap={rs['capital_deployment_approved']} exec={rs['trade_or_execution_approved']}")

print("\n=== REFERENCE LEVELS ===")
for t in tickers:
    rl = db.execute("SELECT ticker, reference_price_low, reference_price_high, reference_invalidation_level, reference_band_status, source_generated_at_utc FROM reference_levels WHERE ticker = ?", (t,)).fetchone()
    if rl:
        print(f"{rl['ticker']}: low={rl['reference_price_low']} high={rl['reference_price_high']} stop={rl['reference_invalidation_level']} status={rl['reference_band_status']} src_date={rl['source_generated_at_utc']}")

print("\n=== EVIDENCE FRESHNESS ===")
for t in tickers:
    ef = db.execute("SELECT ticker, resolution_state, card_missing_or_stale_count, stale_families_json, card_generated_at_utc FROM evidence_freshness WHERE ticker = ?", (t,)).fetchone()
    if ef:
        print(f"{ef['ticker']}: resolution={ef['resolution_state']} stale_count={ef['card_missing_or_stale_count']} stale_families={ef['stale_families_json']} card_gen={ef['card_generated_at_utc']}")

db.close()