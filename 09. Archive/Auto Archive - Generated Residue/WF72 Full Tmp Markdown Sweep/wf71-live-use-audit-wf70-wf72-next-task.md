# WF71 Live-Use Audit - WF70/WF72 Next Task

- **Status:** ok with recommendations
- **Generated:** 2026-05-22T23:47:46Z
- **Scope:** Small WF71 live-use audit on the next WF70/WF72 task after current-window and run-summary registry migrations.

## Decision

The next WF70/WF72 task should be treated as a **bounded Implementation / Refactor Desk task** with Official Source Desk as a domain consumer and Independent QA as read-only challenger.

Candidate: **chain_manifest official-capture registry closeout**.

Reason: `scripts/chain_manifest.py` is partially migrated at runtime but still carries many static `q1-2026` official-capture expected-output literals. That is a maintainability/rollforward risk, not a source-evidence extraction task.

## WF71 route

| Field | Recommendation |
|---|---|
| Primary department | Implementation / Refactor Desk |
| Secondary consumers | Official Source Desk; OS Operator / Automation Desk |
| QA lane | Independent QA Desk, read-only after implementation proof |
| Main-session role | Veritas main owns final integration, queue wording, and authority boundary |

## Load-budget handoff

Read first, normal budget:

1. `06. Playbooks/Project Continuity/Workflow 70 - Official Company Source Capture and Reconciliation.md`
2. `06. Playbooks/Project Continuity/Workflow 71 - Veritas OS Department Staff and Skill Ownership Model.md`
3. `06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md`
4. `scripts/chain_manifest.py`
5. `scripts/official_capture_period_registry.py`
6. `scripts/test_official_capture_period_registry.py`
7. `tmp/wf70-run-summary-registry-migration.json`

Budget result: **7 files**, within the WF71 3-8 file normal lane budget.

## Top findings

| ID | Severity | Finding | Fix |
|---|---|---|---|
| WF71-LIVE-001 | Medium | Clear owner exists: this is an Implementation / Refactor task, not only Official Source Desk. | Use one implementation lane, then read-only QA. |
| WF71-LIVE-002 | Medium | `chain_manifest.py` is partially migrated but not flattened: registry replacement runs, but static Q1 path literals remain. | Replace static official-capture expected outputs with compact registry-derived construction and prove `get_steps()` no-drift. |
| WF71-LIVE-003 | Low | No new staff registry is justified yet. | Keep WF71 routing in existing continuity/control surfaces. |

## Acceptance proof for the next pass

- `python -m py_compile scripts\chain_manifest.py scripts\official_capture_period_registry.py`
- all-window `get_steps()` old/new compare with no exclusions unless explicitly justified
- official capture validator remains 31 captures / 0 findings
- manifest still includes validation outputs for all 31 captures
- no canon/portfolio/trade/account/paper/config/destructive authority widened

## Deferred

- Full skill-body audit against WF71 department map
- New durable staff registry
- Bridge/reconciliation registry migration
- Archive/move/delete cleanup
