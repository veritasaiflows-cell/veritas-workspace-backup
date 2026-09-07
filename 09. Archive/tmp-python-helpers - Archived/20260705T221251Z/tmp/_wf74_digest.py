import json

# Opportunities
with open('tmp/wf74-improvement-opportunity-queue.json') as f:
    d = json.load(f)
opps = d.get('opportunities', d.get('rows', []))
print(f'=== OPPORTUNITIES ({len(opps)}) ===')
for o in opps:
    print(f'---')
    print(f'ID: {o.get("opportunity_id", o.get("id", "?"))}')
    print(f'Title: {o.get("title", "?")}')
    print(f'Category: {o.get("category", "?")}')
    print(f'Priority: {o.get("priority", "?")}')
    print(f'Proposal gate: {o.get("proposal_gate", "?")}')
    print(f'Problem: {str(o.get("problem", "?"))[:250]}')
    print(f'Expected benefit: {str(o.get("expected_benefit", "?"))[:250]}')
    print()

# Proposals
with open('tmp/wf74-reflection-to-proposal-autopilot.json') as f:
    d = json.load(f)
props = d.get('proposals', d.get('rows', []))
print(f'\n=== PROPOSALS ({len(props)}) ===')
for p in props:
    print(f'---')
    print(f'ID: {p.get("proposal_id", p.get("id", "?"))}')
    print(f'Title: {p.get("title", "?")}')
    print(f'Category: {p.get("category", "?")}')
    print(f'Status: {p.get("status", "?")}')
    print(f'Source opportunity: {p.get("source_opportunity_id", "?")}')
    print(f'Scope: {str(p.get("scope", "?"))[:300]}')
    print(f'Risk class: {p.get("risk_class", "?")}')
    print()

# Patch plans
with open('tmp/wf74-auto-patch-proposer.json') as f:
    d = json.load(f)
plans = d.get('patch_plans', [])
print(f'\n=== PATCH PLANS ({len(plans)}) ===')
for p in plans:
    print(f'---')
    print(f'Plan ID: {p.get("plan_id", "?")}')
    print(f'Title: {p.get("title", "?")}')
    print(f'Category: {p.get("category", "?")}')
    print(f'Route: {p.get("route", "?")}')
    print(f'Priority: {p.get("priority", "?")}')
    print(f'Risk class: {p.get("risk_class", "?")}')
    print(f'Problem: {str(p.get("problem", "?"))[:250]}')
    print(f'Expected benefit: {str(p.get("expected_benefit", "?"))[:250]}')
    print()
