# OpenClaw Parallel Pilot Queue

Status: thin compatibility route. The legacy embedded workflow sequence and finance pilot queue were retired on 2026-08-29.

## Live owners

- workflow priority and lifecycle: `06. Playbooks/Active Workflows.md`
- current lane and lease: `tmp/current-active-lanes.json` and the concurrent lane register
- resumable next action: `tmp/current-resume.json`
- historical queue detail: `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md`

## Operating rule

Do not open work from stale prose in this file. Resolve the exact workflow owner, validate the current checkpoint and lease, and use the smallest bounded implementation route. Main owns integration, QC, acceptance, and user-facing judgment.

Parallel work is appropriate when independent proof or implementation lanes reduce elapsed time without creating overlapping writers. Each lane must declare scope, exact files, stop lines, proof, and handoff.

## Finance boundary

Finance helper work is limited to alert evidence, freshness, research, validation, and non-executing recommendations. It may not maintain portfolio or simulated-account state, draft orders, access brokerage/account routes, infer approval, or perform paper/live execution.

## Historical workflow posture (registry-residue record, not an active control surface)

This section preserves registry-agreed posture so governance truth checks stay reconciled. Live state remains owned by `06. Playbooks/Active Workflows.md`.

### Active workflow

Workflow 88 (Veritas OS 2.0 Learning, Cleanup, and Unified Routing) is the current approved active P1 workflow lane. WF40 is intentionally left as residual scheduled-proof watch while another approved workflow remains active; it is not an ordinary scheduled-repeat active queue blocker.

### Next approved queue item

WF40 closed scheduled confirmation watch continues as the next-pass residue: confirm the next ordinary scheduled 17:10 cron audit repeats cleanly and stably before treating WF40 closeout as fully confirmed. No new lane spawns from this file.

### Paused follow-up lane

Workflow 37 remains paused follow-up: review-only proof, delivery posture pending explicit owner decision, and cron promotion stays fail-closed. Resume only for repeated clean review-only run proof and the delivery-posture decision.

### Closed handoff residue

Workflow 39 is closed with handoff back to WF38 (weekly-review / diversification-coverage residue). Workflow 38 is closed with handoff to the standing weekly review surface; NVDA remains timing-blocked and LLY/CAT remain watch-only / review-prep.
