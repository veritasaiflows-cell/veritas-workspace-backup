import json, sqlite3

db = sqlite3.connect('state/finance/finance-canon.sqlite')
db.row_factory = sqlite3.Row

# Get Tier A tickers from universe_membership
tier_a = db.execute("SELECT ticker, tier, sql_tier, sql_tier_state, tier_decision_scope, decision_grade_eligible FROM universe_membership WHERE tier = 'A' OR sql_tier = 'A' ORDER BY ticker").fetchall()
print(f"Tier A tickers from universe_membership: {len(tier_a)}")
for r in tier_a:
    print(f"  {r['ticker']}: tier={r['tier']}, sql_tier={r['sql_tier']}, sql_tier_state={r['sql_tier_state']}, decision_grade_eligible={r['decision_grade_eligible']}")

tickers = [r['ticker'] for r in tier_a]
print("\n" + "="*80)

# For each Tier A ticker, get routing state, reference levels, and evidence freshness
for t in tickers:
    print(f"\n{'='*80}")
    print(f"TICKER: {t}")
    print(f"{'='*80}")
    
    # Routing state
    rs = db.execute("SELECT * FROM tier_routing_state WHERE ticker = ?", (t,)).fetchone()
    if rs:
        print("\nRouting:")
        print(f"  auto_tier: {rs['auto_tier']}")
        print(f"  auto_state: {rs['auto_state']}")
        print(f"  route_reason: {rs['route_reason']}")
        print(f"  route_priority: {rs['route_priority']}")
        print(f"  data_confidence_rating: {rs['data_confidence_rating']}")
        print(f"  fundamentals_confidence: {rs['fundamentals_confidence']}")
        print(f"  tier_a_confidence_status: {rs['tier_a_confidence_status']}")
        print(f"  critical_data_conflict_count: {rs['critical_data_conflict_count']}")
        print(f"  capital_deployment_approved: {rs['capital_deployment_approved']}")
        print(f"  trade_or_execution_approved: {rs['trade_or_execution_approved']}")
    
    # Reference levels
    rl = db.execute("SELECT * FROM reference_levels WHERE ticker = ?", (t,)).fetchone()
    if rl:
        print("\nReference Levels:")
        cols = rl.keys()
        for c in cols:
            if c != 'ticker' and rl[c] is not None:
                print(f"  {c}: {rl[c]}")
    
    # Evidence freshness
    ef = db.execute("SELECT * FROM evidence_freshness WHERE ticker = ?", (t,)).fetchone()
    if ef:
        print("\nEvidence Freshness:")
        cols = ef.keys()
        for c in cols:
            if c != 'ticker' and ef[c] is not None:
                print(f"  {c}: {ef[c]}")
    
    # Securities info
    sec = db.execute("SELECT * FROM securities WHERE ticker = ?", (t,)).fetchone()
    if sec:
        print("\nSecurities:")
        cols = sec.keys()
        for c in cols:
            if c != 'ticker' and sec[c] is not None:
                val = str(sec[c])
                if len(val) > 200:
                    val = val[:200] + "..."
                print(f"  {c}: {val}")

db.close()