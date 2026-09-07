import json

with open('tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json') as f:
    d = json.load(f)

print(f"Generated: {d['generated_at_utc']}")
print(f"Window: {d['window']}")
print(f"Proposals: {d['proposal_count']}")
print()

for i, p in enumerate(d.get('proposals', [])):
    t = p.get('ticker','')
    posture = p.get('proposed_state',{}).get('recommendation_posture','')
    review_state = p.get('current_state',{})
    tech = p.get('technical_gate',{})
    catalyst = p.get('catalyst_gate',{})
    thesis = p.get('thesis_gate',{})
    earnings = p.get('official_earnings_gate',{})
    freshness = p.get('source_freshness',{})
    lane = p.get('current_lane_status_tuple',{})
    
    print(f"--- Proposal {i+1}: {t} ---")
    print(f"  Posture: {posture}")
    print(f"  Workflow state: {lane.get('workflow_state','')}")
    print(f"  Recommendation action: {lane.get('recommendation_action','')}")
    print(f"  Daily review state: {review_state.get('daily_review_state','')}")
    print(f"  Band status (live): {tech.get('band_status','')}")
    print(f"  Band status (proposed): {tech.get('proposal_band_status','')}")
    print(f"  Close: {tech.get('close','')} | Band: {tech.get('current_band_low','')}-{tech.get('current_band_high','')} | Distance: {tech.get('distance_to_band_pct','')}%")
    print(f"  In entry band: {tech.get('in_entry_band','')} | Below stop: {tech.get('below_stop','')}")
    print(f"  Thesis: {thesis.get('summary','')}")
    print(f"  Earnings: {earnings.get('status','')} | Next: {catalyst.get('days_to_earnings','')}d | State: {catalyst.get('earnings_state','')}")
    print(f"  Freshness: {freshness.get('overall_classification','')} | Trust: {freshness.get('trust_level','')}")
    print(f"  Owner decision required: {p.get('owner_decision_required','')}")
    print(f"  Apply allowed: {p.get('apply_allowed','')}")
    print()