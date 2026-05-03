# Workflow 12 - Macro Policy Trust Repair

## Objective
- Close or explicitly own the long-carried macro/policy trust residue and the remaining timing-sensitive dependency gaps that keep degrading trust surfaces.

## Current State
- This workflow is queued behind Workflow 11 in the reprioritized sequence.
- Macro/policy caveats were reduced materially by earlier hardening, but manual-dependency residue still recurs in the trust surface and should not live forever as unnamed background debt.
- The new architecture audit also called out timing-sensitive earnings-date friction as another repairable trust dependency that should be handled intentionally instead of living as recurring validator noise.

## Last Meaningful Progress
- Earlier policy hardening automated the current Fed target range from FRED and removed the old manual-target blocker path.
- Even after those fixes, macro/policy residue has continued to appear as accepted warning-grade/manual-trust debt rather than a fully closed contract.

## Outstanding
- Define which macro/policy caveats are intentionally manual and long-lived.
- Define which remaining macro/policy and timing caveats are still repairable and should not remain permanent residue.
- Decide whether policy-expectations sourcing and targeted earnings-date verification can be automated enough to retire the recurring friction honestly.
- Assign explicit ownership and disclosure rules for any manual dependencies that remain.

## Blockers / Trust Gaps
- The main risk is letting old caveats persist simply because they are familiar.
- This workflow should separate **intentional manual dependency** from **unfinished trust repair**.
- It also must avoid fake precision: some dependencies may stay manual by design if the source quality or trust boundary is still weak.

## Next Action
- Draft the residue inventory and split it into: intentional/manual, repairable soon, and no-longer-valid legacy caveats, with timing-sensitive earnings-date trust gaps included in the same inventory.

## Key Files
- `tmp/market-state.json` - live macro trust surface.
- `tmp/policy-expectations.json` - live policy artifact.
- `scripts/earnings_calendar_enrichment.py` - current timing-source helper that may need a stricter verification path.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - queue residue history.
- `05. Intelligence/Weekly Positioning Review.md` - downstream consumer of macro/policy judgment.

## Automation / Refresh Path
- Treat this as trust-repair work, not as a broad macro rewrite.
- Close only what evidence supports; keep the remaining manual dependencies explicit and owned.
- If any timing or policy input is automated here, it still must fail closed when source quality is weak.
