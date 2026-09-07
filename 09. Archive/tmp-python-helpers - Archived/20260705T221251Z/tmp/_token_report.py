import json

# Token efficiency top candidates
d = json.load(open("tmp/token-efficiency-scorecard.json", encoding="utf-8"))
candidates = d.get("top_cron_efficiency_candidates", [])
print("=== TOP CRON TOKEN CONSUMERS ===")
for c in candidates:
    print(f'{c["rank"]}. {c["cron_job_name"]}')
    print(f'   {c["tokens_per_run"]:.0f} tok/run | ${c["estimated_cost_per_run"]:.4f}/run | cache={c["cache_ratio"]:.1%} | output={c["output_ratio"]:.1%}')
    print(f'   types: {c["candidate_types"]}')
    print()

# Validator timing
vd = json.load(open("tmp/validator-timing-ledger.json", encoding="utf-8"))
print("=== VALIDATOR TIMING ===")
print(f'Commands run: {vd.get("commands_run", "?")}')
print(f'Elapsed: {vd.get("elapsed_seconds", "?")}s')
print(f'Target: {vd.get("target_seconds", "?")}s')
print(f'Slow: {vd.get("slow", "?")}')
print(f'Reserved for major: {vd.get("reserved_for_major", [])}')

# Validator bundle
bd = json.load(open("tmp/validator-bundle-router.json", encoding="utf-8"))
print(f'\n=== VALIDATOR BUNDLE ===')
print(f'Status: {bd.get("status", "?")}')
print(f'Selected: {bd.get("selected", "?")}')
print(f'Failed: {bd.get("failed", "?")}')

# Summary
print(f'\n=== SUMMARY ===')
print(f'Total token events: {d.get("summary",{}).get("token_event_count", "?")}')
print(f'Total tokens: {d.get("summary",{}).get("total_tokens", "?"):,}')
print(f'Est cost: ${d.get("summary",{}).get("estimated_cost_total", "?"):.2f}')
print(f'API reduction candidates: {d.get("summary",{}).get("api_call_reduction_candidate_count", "?")}')
print(f'Prompt compression candidates: {d.get("summary",{}).get("prompt_compression_candidate_count", "?")}')
print(f'Failure cost candidates: {d.get("summary",{}).get("failure_cost_candidate_count", "?")}')
print(f'Implementation token gaps: {d.get("summary",{}).get("implementation_token_gap_count", "?")}')
