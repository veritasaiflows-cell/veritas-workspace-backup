# Claude IC Handoff — Weekly Macro Snapshot Completion Contract

You are a read-only challenger lane for Veritas. Work in `C:\Users\Veritas\.openclaw\workspace`.

## Objective
Audit the current Weekly Macro Snapshot scaffold and propose a completion contract that makes the report decision-grade without creating false precision or ungated portfolio/trade authority.

## Read these files first
- `scripts/weekly_macro_snapshot.py`
- `tmp/weekly-macro-snapshot.json`
- `02. Markets/Weekly Macro Snapshot/2026-W20-machine.md`
- `tmp/market-state.json`
- `tmp/macro-regime.json`
- `tmp/dashboard-validation.json`
- `02. Markets/Macro Regime Dashboard.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`

## Known issue
The generated snapshot currently includes placeholders such as:
- Inflation and growth pulse: `[Fill]`
- Energy and commodities judgment: `[Fill]`
- FX judgment: `[Fill]`
- Geopolitical flags: `[Fill]`
- Macro data calendar: `[Fill]`
- Posture call: `[Offensive / Defensive-neutral / Defensive — state basis]`
- One-line directive: `[Fill]`

## Deliverables
Return a concise but decision-grade audit with these sections:
1. **Verdict** — what is incomplete and why it matters.
2. **Required source artifacts** — exact proposed artifacts/scripts needed to fill missing sections. Distinguish machine-fetchable from judgment/manual-review.
3. **Report completion contract** — required sections/fields for the final Weekly Macro Snapshot.
4. **Validator contract** — checks that must block a report from being called complete, including placeholder detection, stale/missing source gates, confidence/data-quality requirements, and authority boundary checks.
5. **Workflow integration** — where this belongs in the Sunday chain and how it should interact with `weekly_macro_snapshot.py`, `weekly_intelligence_brief.py`, and note mutation gates.
6. **Minimal implementation plan** — smallest safe diff sequence and proof gates.
7. **Risks / pushback** — anything Veritas might be overbuilding, underbuilding, or missing.

## Boundaries
- Read-only analysis only. Do not edit files.
- Do not recommend live/paper trades, brokerage/account actions, money movement, or inferred owner approval.
- Do not propose cron direct-apply canonical note mutation.
- Keep generated artifacts distinct from canonical notes.
- Final Veritas/main session owns integration and queue decisions.
