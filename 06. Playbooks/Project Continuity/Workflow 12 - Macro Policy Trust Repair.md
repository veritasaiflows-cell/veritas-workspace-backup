# Workflow 12 - Macro Policy Trust Repair

## Objective
- Close or explicitly own the long-carried macro/policy trust residue and the remaining timing-sensitive dependency gaps that keep degrading trust surfaces.

## Current State
- Workflow 12 is now **honestly closed** after splitting active macro/timing caution from stale inherited caveats, updating the active note surfaces, and rerunning the trust checks.
- Macro/policy caveats were reduced materially by earlier hardening, but the remaining debt was mostly stale downstream wording rather than live machine-state failure.
- Timing-sensitive earnings-date friction is now narrowed explicitly instead of being repeated as a broad warning blanket across the active note layer.

## Last Meaningful Progress
- Earlier policy hardening automated the current Fed target range from FRED and removed the old manual-target blocker path.
- Workflow 12 then landed `06. Playbooks/Macro Policy and Timing Trust Protocol.md` to distinguish what is still intentionally approximate from what is merely stale inherited warning language.
- Active downstream surfaces (`Executive Brief`, `Next Actions`, `Macro Regime Dashboard`, `Weekly Positioning Review`, `Deployment Trigger Sheet`, `Technical Entry and Invalidation Sheet`, `Portfolio Snapshot`, and `Event Calendar`) were updated so they no longer claim default manual-policy debt or broad unresolved date-mismatch residue that the live artifacts do not support.
- `scripts/dashboard_validation.py` now has a bounded note-surface guard for stale manual-policy wording when the live policy artifact is no longer in manual mode.
- Validation and acceptance reruns still passed after the trust-repair edits.

## Outstanding
- Use the next real policy/timing drift event as the first proof case that the new protocol and validator guard actually catch stale wording early.

## Blockers / Trust Gaps
- The main residual risk is regression: old blanket warning language can creep back in if downstream notes are updated loosely.
- This workflow now separates **intentional approximation/caution** from **stale inherited caveat**; future edits need to preserve that distinction.
- It also must avoid fake precision: provider-derived timing and simplified policy probabilities still are not a license for overconfidence.

## Next Action
- Keep Workflow 12 closed unless a real policy/timing regression appears; the post-chain hardening pass and checkpoint commit closed the prior repo-state residue.

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
