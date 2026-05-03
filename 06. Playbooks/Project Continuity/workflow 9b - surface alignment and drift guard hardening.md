# Workflow 9B - Surface Alignment and Drift Guard Hardening

## Objective
- Make dashboards, validators, and note-owned mirrors reflect one coherent lane / ownership contract before more scaling or automation.
- Convert repeated drift warnings into enforced rules or explicit owner-bound manual exceptions.

## Current State
- Queued directly behind Workflow 9A as the second organization-first pass.
- The backend lane model is materially cleaner after Workflows 6-9, but audits still show human-facing surfaces and validators lagging that contract.
- Known residue includes incomplete human-facing consistency checks, non-execution lane presentation gaps, recurring state mismatches like `GS`, and the lack of a formal post-catalyst truth-sync contract.

## Last Meaningful Progress
- Workflow 6 hardened the lane / tier framework and downstream validator behavior.
- Workflow 8 kept Command Center downstream and non-authoritative while proving a cleaner source-truth contract.
- The new audits clarified the next gap: surface alignment and drift prevention are now the limiting factor, not raw infrastructure.

## Outstanding
- Expand consistency checks to `02. Markets/Watchlist.md`, `04. Research/Coverage Universe.md`, and other human-facing mirrors.
- Define a mandatory post-catalyst **Truth Sync** protocol after heavy earnings windows, FOMC pivots, or similar same-window truth shocks.
- Define explicit artifact-owner / read-write boundaries for ICs and automation before more delegation is opened.
- Continue enum enforcement where ambiguous boolean entitlement sprawl still survives.
- Design the dry-run-first gated write-back utility for syncing technical levels / entry bands from machine truth into note-owned surfaces.
- Close or explicitly own the known surface-mismatch items like `GS` state drift and non-execution lane overview gaps.

## Blockers / Trust Gaps
- This workflow must not become a backdoor for silent canonical rewrites.
- UI / presentation changes must remain downstream and non-authoritative.
- Some path or owner decisions may depend on the organization map produced by Workflow 9A.

## Next Action
- Draft the validator / surface contract and the first bounded issue list after Workflow 9A produces the organization map.

## Key Files
- `08. Audits/Workspace Optimization and Scale Readiness Audit - 2026-05-02.md` - primary queue trigger.
- `06. Playbooks/Automation Orchestration Protocol.md` - ownership and sequencing rules.
- `06. Playbooks/Notes Layer Governance Protocol.md` - note-layer mutation boundary.
- `06. Playbooks/Notes Layer Audit Checklist.md` - audit checklist for downstream note surfaces.
- `02. Markets/Watchlist.md` - human-facing mirror to validate.
- `04. Research/Coverage Universe.md` - thesis / lane mirror to validate.
- `03. Portfolio/Portfolio Snapshot.md` - current owner note with known state-surface residue.
- `tmp/portfolio-config.json` - machine lane assignment source.
- `tmp/dashboard-validation.json` - current validator artifact.

## Automation / Refresh Path
- Keep this main-session controlled.
- Read-only helper lanes are fine for validator expansion proposals or UI diff prep.
- Any write-back utility must default to dry run and require post-apply validation before it is ever treated as usable.
