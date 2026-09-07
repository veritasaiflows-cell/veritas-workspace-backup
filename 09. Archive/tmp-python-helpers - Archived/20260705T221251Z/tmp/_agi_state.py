import json

# Vector memory
with open(r'C:\Users\Veritas\.openclaw\workspace\tmp\vector-memory-index.json') as f:
    vm = json.load(f)

# Checkpoint
with open(r'C:\Users\Veritas\.openclaw\workspace\tmp\wf74-wf88-checkpointed-execution.json') as f:
    cp = json.load(f)

# Decision docket
with open(r'C:\Users\Veritas\.openclaw\workspace\tmp\wf74-decision-docket.json') as f:
    dd = json.load(f)

print("=== VECTOR MEMORY ===")
print(f"Status: {vm.get('status')}")
print(f"Chunks: {vm.get('chunk_count')}")
print(f"Sources: {vm.get('source_count')}")
print(f"DB: {vm.get('db_path')} ({vm.get('db_size_bytes','?')} bytes)")
print(f"Embedding: {vm.get('embedding_provider')}/{vm.get('embedding_model')}")
print(f"Retrieval: {vm.get('retrieval_mode')}")
print(f"FTS: {vm.get('fts_enabled')}")

print("\n=== CHECKPOINTED EXECUTION ===")
print(f"Status: {cp.get('status')}")
print(f"Run: {cp.get('run_id')}")
print(f"Steps: {cp.get('step_count')} completed")
print(f"DB: {cp.get('db_path')}")
for s in cp.get('steps', []):
    print(f"  [{s['status']}] {s['step_id']} ({s['duration_seconds']}s)")

print("\n=== DECISION DOCKET ===")
print(f"Rows: {dd['summary']['row_count']}")
print(f"Active: {dd['summary']['active_action_count']}")
print(f"States: {dd['summary']['action_state_counts']}")
print(f"Next: {dd['summary']['next_safe_action']}")

# Fix-now items
fix_now = [r for r in dd.get('rows', []) if r.get('action_state') == 'fix_now']
print(f"\nFix-now items ({len(fix_now)}):")
for r in fix_now:
    print(f"  - {r.get('title')} (priority={r.get('priority')})")
