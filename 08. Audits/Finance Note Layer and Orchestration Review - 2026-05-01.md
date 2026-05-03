# Finance Note Layer and Orchestration Review - 2026-05-01

## Scope
Synthesize the 2026-05-01 multi-agent audit pass across:
- finance note-layer remediation
- continuity/archive safety
- orchestration / automation review

## Top Findings

### 1. Finance note layer is split-brain
- Artifact layer is current through 2026-05-01.
- Several top human-facing finance notes are still frozen in the 2026-04-24 to 2026-04-28 window across the FOMC / earnings catalyst cluster.
- Result: visible note guidance is not just stale; some of it is actively misleading.

Highest-risk files called out:
- `05. Intelligence/Weekly Positioning Review.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/Next Actions.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Macro Regime Dashboard.md`

### 2. Archive posture is currently correct and conservative
- Recent archive decisions were validated.
- No further archive moves are recommended right now.
- Remaining archive-safe candidates were not identified; the remaining older files are still referenced by active notes or chain logs.

### 3. Orchestration is coherent but not closed-loop yet
- Queue, registry, continuity notes, cron protocol, and live cron posture mostly agree.
- Biggest current gap is live cron proof plus run-history / failure-visibility, not more architecture writing.

## Ranked Remediation Order

### Fix now
1. `05. Intelligence/Weekly Positioning Review.md`
2. `05. Intelligence/Weekly Intelligence Brief.md`
3. `01. Dashboards/Executive Brief.md`
4. `01. Dashboards/Next Actions.md`
5. `03. Portfolio/Portfolio Snapshot.md`
6. `02. Markets/Macro Regime Dashboard.md`

### Fix next
7. `01. Dashboards/This Week.md`
8. `02. Markets/Watchlist.md`

### Leave alone for now
9. `07. Risk/Risk Rules.md`

## Smallest Safe Remediation Workflow
- Do one narrow post-cluster truth-sync.
- Use current evidence only:
  - `tmp/market-state.json`
  - `tmp/trigger-sheet.json`
  - `tmp/post-earnings-prep.json`
  - `tmp/post-earnings-note-targets.json`
- Update only the highest-risk core notes first.
- Do not mix that pass with broader note cleanup, scorecard churn, or risk-doctrine edits.

## Orchestration Recommendation
Insert a new priority queue item:
- `Workflow 4B — Live Cron Shakedown + Run Ledger Hardening`

Reason:
- The cron layer is live but not yet boringly trustworthy.
- The next missing proof is repeated run evidence, run-history visibility, blocked/error follow-up, and explicit delivery-posture clarity.
- This should happen before PDF/Excel fit, coverage tiers, sector expansion, or department design.

## Resulting Direction
- Keep archive posture conservative.
- Fix the finance note layer with a narrow truth-sync pass.
- Prove the cron layer through Workflow 4B before broader expansion.