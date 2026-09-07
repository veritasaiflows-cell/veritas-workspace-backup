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
