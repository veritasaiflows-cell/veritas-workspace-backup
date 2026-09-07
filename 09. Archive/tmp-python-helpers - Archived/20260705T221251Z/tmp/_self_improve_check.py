import os, json

scripts = [
    'wf74_improvement_opportunity_queue.py',
    'wf74_reflection_to_proposal_autopilot.py',
    'wf74_auto_patch_proposer.py',
    'wf74_decision_docket.py',
    'wf74_learning_loop_eval_harness.py',
    'wf74_autonomy_work_router.py',
    'improvement_ledger.py',
    'response_recommendation_contract_lint.py',
]
base = r'C:\Users\Veritas\.openclaw\workspace\scripts'
for s in scripts:
    p = os.path.join(base, s)
    status = "EXISTS" if os.path.exists(p) else "MISSING"
    size = os.path.getsize(p) if os.path.exists(p) else 0
    print(f"{s}: {status} ({size} bytes)")

ledger = r'C:\Users\Veritas\.openclaw\workspace\tmp\improvement-ledger.json'
if os.path.exists(ledger):
    with open(ledger) as f:
        d = json.load(f)
    s = d.get('summary', {})
    print(f"\nImprovement Ledger: followup_required={s.get('followup_required_open_count','?')}, pending_skills={s.get('pending_skill_proposal_count','?')}")
else:
    print("\nImprovement Ledger: MISSING")

rsp = r'C:\Users\Veritas\.openclaw\workspace\skills\veritas-response-contract\SKILL.md'
print(f"\nveritas-response-contract: {'EXISTS' if os.path.exists(rsp) else 'MISSING'}")

evals = r'C:\Users\Veritas\.openclaw\workspace\data\wf74-learning-loop-evals\cases.json'
print(f"WF74 eval cases: {'EXISTS' if os.path.exists(evals) else 'MISSING'}")

iso = r'C:\Users\Veritas\.openclaw\workspace\skills\veritas-isolated-agent-contract\SKILL.md'
print(f"veritas-isolated-agent-contract: {'EXISTS' if os.path.exists(iso) else 'MISSING'} ({os.path.getsize(iso) if os.path.exists(iso) else 0} bytes)")

# Check for any pending skill proposals
sw_dir = r'C:\Users\Veritas\.openclaw\workspace\.skill-workshop'
if os.path.exists(sw_dir):
    proposals = [d for d in os.listdir(sw_dir) if os.path.isdir(os.path.join(sw_dir, d))]
    print(f"\nSkill Workshop proposals: {len(proposals)}")
    for p in proposals:
        print(f"  - {p}")
else:
    print("\nSkill Workshop dir: MISSING")
