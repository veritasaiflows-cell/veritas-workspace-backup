from pathlib import Path
active = Path('06. Playbooks/Active Workflows.md')
s = active.read_text(encoding='utf-8')
row = "| P1 | WF78 - 500 Ticker Finance Intelligence Scaleout | Opened / Phase 1 planning: tier-aware universe schema and SQL current-state design for scaling WF77/WF72 from 42 tickers toward 500 active monitored names without false precision, authority drift, provider fragility, or artifact sprawl | Finance Intelligence Desk + SQLite / Retrieval Desk + OS Operator | Implement Phase 1 only after explicit execution pass: create tier-aware universe registry/validator for current 42 first, then WF77 read-only ingestion and no-drift validation. | WF78 continuity note exists; current 42 behavior remains unchanged until implementation; acceptance requires universe validator, 42-card build, router QA, artifact-index validate, and no authority widening. | Review/routing/infrastructure only; no full SQL-canon migration, no canon/portfolio/sizing/cash/risk-rule mutation, no approval inference, no paper/live execution, no brokerage/account/money action, no DB path migration without separate migration packet. | [[06. Playbooks/Project Continuity/Workflow 78 - 500 Ticker Finance Intelligence Scaleout]] |"
if 'WF78 - 500 Ticker Finance Intelligence Scaleout' not in s:
    lines = s.splitlines()
    insert_at = None
    for idx, line in enumerate(lines):
        if line.startswith('| P1 | WF77'):
            insert_at = idx + 1
            break
    if insert_at is None:
        for idx, line in enumerate(lines):
            if line.startswith('| P'):
                insert_at = idx + 1
        if insert_at is None:
            insert_at = len(lines)
    lines.insert(insert_at, row)
    active.write_text('\n'.join(lines) + '\n', encoding='utf-8')

mem = Path('memory/2026-05-27.md')
ms = mem.read_text(encoding='utf-8')
entry = "\n- 22:29 MST WF78 opened from Randall request: `06. Playbooks/Project Continuity/Workflow 78 - 500 Ticker Finance Intelligence Scaleout.md` now defines review-only 500-ticker scaleout plan, incorporates the two external architecture suggestions, keeps Markdown canon / JSON proof / SQLite validated routing-cache hierarchy, accepts state-folder/query-surface improvements as governed backlog, and explicitly defers full SQL-canon migration or DB path moves until separate no-drift migration proof. Added Active Workflows row. Status: Phase 1 planning only; no universe/schema implementation yet.\n"
if 'WF78 opened from Randall request' not in ms:
    mem.write_text(ms.rstrip() + entry, encoding='utf-8')
