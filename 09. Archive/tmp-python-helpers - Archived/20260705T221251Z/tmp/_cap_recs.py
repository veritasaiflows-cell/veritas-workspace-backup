import json

with open('tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json') as f:
    d = json.load(f)

print(f"Generated: {d['generated_at_utc']}")
print(f"Status: {d['status']}")
print(f"Window: {json.dumps(d.get('window',{}), default=str)}")
print(f"Proposal count: {d['proposal_count']}")
print(f"Canonical note mutation allowed: {d['canonical_note_mutation_allowed']}")
print(f"Owner approval granted: {d['owner_approval_granted']}")
print(f"Portfolio mutation allowed: {d['portfolio_mutation_allowed']}")
print(f"Apply allowed: {d['apply_allowed']}")
print(f"Proposal apply allowed: {d['proposal_apply_allowed']}")
print(f"Trade/account action allowed: {d['trade_or_account_action_allowed']}")
print(f"Main session final action required: {d['main_session_final_action_required']}")
print(f"\nAuthority: {json.dumps(d.get('authority',{}), indent=2, default=str)}")
print(f"\nStop lines: {json.dumps(d.get('stop_lines',[]), indent=2)}")
print()

for i, p in enumerate(d.get('proposals', [])):
    print(f"\n{'='*80}")
    print(f"PROPOSAL {i+1}")
    print(f"{'='*80}")
    # Print without the huge raw_json fields
    clean = {k: v for k, v in p.items() if k not in ('raw_json', 'source_raw_json', 'evidence_raw')}
    print(json.dumps(clean, indent=2, default=str))