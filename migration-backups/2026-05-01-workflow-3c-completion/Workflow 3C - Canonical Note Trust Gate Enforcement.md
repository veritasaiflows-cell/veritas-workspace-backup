# Workflow 3C - Canonical Note Trust Gate Enforcement

## Objective
- Prevent canonical note mutation before the trust contract explicitly allows it.
- Keep the fix bounded to trust-gate enforcement, not broad architecture redesign.

## Current State
- User approved Workflow 3C on 2026-05-01.
- Queue was updated so Workflow 3C now sits between Workflow 3B and Workflow 4.
- File inspection completed.
- No implementation patch has been applied yet.
- A preflight reviewer lane was spawned, but its completion was not confirmed before restart/handoff.

## Last Meaningful Progress
- Identified the live trust-gap surface in these files:
  - `scripts/run_finance_refresh_chain.py`
  - `scripts/run_summary_refresh.py`
  - `scripts/weekly_macro_snapshot.py`
  - `scripts/weekly_intelligence_brief.py`
  - `scripts/postmarket_snapshot.py`
  - `scripts/daily_executive_brief.py`
- Updated the queue to reflect the audit-driven insertion of Workflow 3C.

## Outstanding
- Re-run or confirm the preflight reviewer result.
- Decide the safest bounded fix:
  - move trust adjudication earlier,
  - add explicit fail-closed gates to canonical writers,
  - or use a minimal hybrid.
- Implement the bounded patch.
- Validate that no pre-trust canonical write path remains in the touched flow.

## Blockers / Trust Gaps
- Reviewer completion was not confirmed before session restart.
- Current chain evidence still shows Sunday canonical writers can run before `run_summary_refresh.py` emits the downstream trust object.
- Runtime/session state should be treated as advisory until Workflow 10 closes the control-surface reliability gap.

## Next Action
- Restart in a new session, read this note plus the queue/audit, then either recover the reviewer result or rerun the preflight review before editing trust logic.

## Key Files
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - queue order and Workflow 3C contract
- `08. Audits/Workspace QA Audit - 2026-05-01.md` - source of the trust-blocker finding
- `scripts/run_finance_refresh_chain.py` - chain ordering currently lets canonical writers run before trust summary finalization
- `scripts/run_summary_refresh.py` - current downstream trust object with `canonical_note_mutation_allowed: false`
- `scripts/weekly_macro_snapshot.py` - canonical weekly note writer in the Sunday chain
- `scripts/weekly_intelligence_brief.py` - canonical weekly intelligence writer in the Sunday chain
- `scripts/postmarket_snapshot.py` - daily note writer in post-close / Sunday chain
- `scripts/daily_executive_brief.py` - daily executive note writer in post-close / Sunday chain

## Acceptance Target
- Warning-grade/internal-only trust posture cannot mutate canonical weekly/intelligence notes implicitly.
- The chain degrades honestly instead of writing first and disclaiming later.
- Verification proves no touched pre-trust canonical write path remains.
