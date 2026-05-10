# WF38 Mission Control Follow-up Recommendation - 2026-05-06

## Workflow under review
Workflow 38 - Sector Expansion and Promotion Review Hardening.

## Current active workflow truth
- WF38 is the live active/resumed workflow after WF39 closed; WF37 is paused with follow-up, not closed or scheduler-promoted.
- WF38 has real implementation proof for Coverage Universe de-authoring, JPM artifact-layer auto-approval, and stricter entry-band apply eligibility.
- WF38 is not closeout-ready because the latest post-close run is `status=blocked` at `workbook_export.py`, workbook exports are stale for that run, and downstream canonical note mutation is explicitly disallowed while run-summary status is blocked.
- The cron ledger's workflow preflight evidence is stale versus the live queue order: it still describes `WF31 -> WF26 -> WF22`, while the active control surfaces now say `WF38 active -> WF37 paused -> SOP / automation optimization backlog`.

## Smallest honest WF38 next action
Clear or release the `tmp/workbook-control-panel.csv` / Excel lock, then rerun exactly one workbook-export proof pass (`python scripts/workbook_export.py`) before any JPM owner-note packet decision.

If that rerun succeeds, decide one bounded question: should JPM receive an explicit owner-note mutation packet for human review, or remain artifact-approved only. If the rerun fails again, stop and log a degraded-run incident instead of pushing WF38 closeout language.

## SOP item 3 decision
Pull SOP backlog item 3 forward now, but as a bounded Mission Control follow-up immediately after the WF38 workbook/JPM disposition attempt, not as hidden WF38 scope.

Reason: the live evidence already shows the exact repeated friction this SOP is meant to reduce: blocked post-close run summary, stale workbook artifacts, manual/unconfirmed command-center dependencies, stale workflow-preflight queue order, and a post-earnings catch-up path that requested approval instead of closing cleanly. A degraded-run response SOP will improve efficiency before WF37/WF38 scheduling decisions widen.

## Recommended next phase
- Current phase: gated recovery / final WF38 disposition.
- Recommended next phase: one-shot workbook-export recovery proof, then JPM disposition or degraded-run stop.
- Safe automation boundary: artifact regeneration and review-surface status only; no automatic canonical note mutation, trade execution, sector-rotation authority, or scheduler promotion.

## Next proposed Mission Control workflows
1. **WF38 Workbook Export Recovery and JPM Disposition** — Clear the workbook CSV/Excel lock, rerun export proof, then decide whether JPM stays artifact-approved only or gets a human-reviewed owner-note mutation packet.
2. **Mission Control Degraded-Run Response SOP** — Create the incident/degraded-run procedure for blocked cron runs, stale run summaries, locked artifacts, approval-pending catch-ups, and queue-preflight drift.
3. **Workflow Preflight Queue-Truth Refresh** — Reconcile the sequential-advancement preflight payload/ledger with the live order (`WF38 -> WF37 -> SOP backlog`) and prove it fail-closes instead of advancing from stale WF31/WF26/WF22 assumptions.

Do not open these automatically; use them as the next bounded planning queue after main-session integration.

## Stop lines / what not to automate
- Do not mark WF38 closed while `tmp/run-summary-post-close.json` is blocked or workbook exports are stale for the current run.
- Do not mutate JPM owner notes from the promotion checker; artifact-level auto-approval is not canonical owner approval.
- Do not promote WF37 delivery posture or scheduled brief generation until repeated clean review-only proof exists.
- Do not let the workflow preflight job advance queue state from stale workflow-order assumptions.
- Do not treat manual earnings-date mismatches, LNG band debt, or stale workbook artifacts as harmless if they affect operator trust surfaces.

## Trust gates still missing
- Clean workbook-export proof after the lock clears.
- Explicit JPM disposition decision.
- Updated workflow-preflight proof aligned to the live queue order.
- Degraded-run SOP coverage for blocked, warning, approval-pending, stale-artifact, and manual-dependency states.

## Evidence used
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/Project Continuity/Workflow 38 - Sector Expansion and Promotion Review Hardening.md`
- `06. Playbooks/Project Continuity/Workflow 37 - Daily Summary Commercial Brief Hardening.md`
- `06. Playbooks/Project Continuity/Workflow 39 - Mission Posture and SOP Optimization Hardening.md`
- `06. Playbooks/Cron Run Ledger.md`
- `tmp/run-summary-post-close.json`
- `tmp/run-summary-post-earnings.json`
- `tmp/workbook-export-manifest.json`
- `tmp/veritas-command-center.html`
