import json

d = json.load(open("tmp/validator-bundle-router.json", encoding="utf-8"))
sv = d.get("selected_validators", [])
print(f"Selected validators: {len(sv)}")
for i, c in enumerate(sv[:30]):
    print(f'{i+1}. {c.get("command",c.get("name","?"))} | {c.get("category","?")} | budget={c.get("budget","?")}')

print("\n=== RUN RESULTS ===")
rr = d.get("run_results", {})
print(f'Status: {rr.get("status","?")}')
print(f'Executed: {rr.get("executed_command_count","?")}')
print(f'Failed: {rr.get("failed_command_count","?")}')

# Also check the changed_file_route for recommendations
cfr = d.get("changed_file_route", {})
cfr_summary = cfr.get("summary", {})
print(f'\nChanged paths: {cfr_summary.get("changed_path_count","?")}')
print(f'Recommendations: {cfr_summary.get("recommendation_count","?")}')
print(f'Recommended budget: {cfr_summary.get("recommended_budget","?")}')
print(f'Heavy validators reserved: {cfr_summary.get("heavy_validators_reserved","?")}')
