from pathlib import Path
entry='''

## WF72 Phase 8-11 readiness prep - 2026-05-24 11:24 MST

- Closed the remaining Opportunity 7 documentation residue by patching `skills/sqlite/SKILL.md` with workspace-index FTS5 retrieval guidance, exact-alias-first behavior, hyphenated query fallback (`note-drift` must not fail as `no such column: drift`), source-open-before-judgment rule, and the current WF72 thirteen-key SQL-canon/cache boundary.
- Prepared the bounded WF72 phases 8-11 plan in `tmp/wf72-phases-8-11-full-activation-readiness-plan.json/.md`.
- Phase 8 recommended next action: adjudicate `portfolio:source_freshness_classification` alone as a separate-gate proof-metadata candidate; do not mix it with deployment/status or higher-risk families in the same write pass.
- Phase 9: redesign or permanently hold 10 `deployment_proof_status` rows because wording can imply deployment/action authority.
- Phase 10: separate higher-risk families (`entry/stop`, `sizing/sleeve/cash/weight`, `risk-rule`, `trade/account/paper/live`, `credential/config`) into never-SQL-canon, proposal-only staging, or separately gated metadata categories.
- Phase 11: assemble final activation-readiness matrix with active/held/rejected keys, guard/test coverage, rollback drills, no-drift proof, and continuity updates.
- Proof: `python -m py_compile tmp\wf72_make_phases_8_11_plan.py`; `openclaw skills check` passed with SQLite visible/eligible. Boundary preserved: no additional SQL activation, no Markdown/canon/portfolio mutation, no owner approval inference, no cron-direct apply, no dashboard action-state behavior change, no trade/account/paper/live authority, no money movement, and no config/auth/channel/service mutation.
'''
for rel in ['06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md','memory/2026-05-24.md']:
    p=Path(rel); text=p.read_text(encoding='utf-8')
    if '## WF72 Phase 8-11 readiness prep - 2026-05-24 11:24 MST' not in text:
        p.write_text(text.rstrip()+entry+'\n',encoding='utf-8')
print('updated')
