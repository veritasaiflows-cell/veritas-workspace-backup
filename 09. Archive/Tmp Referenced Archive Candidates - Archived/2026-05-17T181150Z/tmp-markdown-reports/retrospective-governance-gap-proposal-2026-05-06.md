# Retrospective Governance Hardening Proposal - 2026-05-06

## Scope
Bounded comparison between:
- `08. Audits/Closed Workflow Retrospective Guidance - 2026-05-06.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`

Goal: identify the smallest real gaps between retrospective recommendations and the live standards, without editing canonical docs.

## 1) Recommendations already substantially covered by live standards

### A. Independent audit before meaningful closeout
Already covered in all three live standards.
- `Major Workflow Contract Standard.md` -> `Acceptance Gates`, `Exit / Closeout Checklist`
- `Spawn and Closeout Governance Matrix.md` -> `Independent auditor closeout rule`, `Executive-summary gate`, `Closeout checklist`
- `Workflow Closeout Artifact Standard.md` -> `Required closeout artifacts` item 7

Retrospective recommendation coverage:
- recommendation 6 (`use independent audits to challenge closure claims before queue movement`)
- bottom-line emphasis on audit as a real brake

### B. Proof refresh / smallest acceptance gate after contract-bearing changes
Already substantially covered, though phrased broadly rather than with the retrospective’s exact sequence.
- `Major Workflow Contract Standard.md` -> `Acceptance Gates`
- `Spawn and Closeout Governance Matrix.md` -> closeout proof expectations via audit and acceptance evidence
- `Workflow Closeout Artifact Standard.md` -> chain-log validation evidence and cross-surface honesty rule

Retrospective recommendation coverage:
- recommendation 3 (`code change -> regenerate artifacts -> rerun smallest acceptance gate`)
- guidance section on adjacent proof refresh for contract-bearing outputs

### C. Honest bounded closeout instead of fake readiness
Already covered.
- `Workflow Closeout Artifact Standard.md` -> `Closure labels`, `Cross-surface honesty rule`
- `Major Workflow Contract Standard.md` -> `Acceptance Gates`, `Exit / Closeout Checklist`, `Canonical Mutation Posture`
- `Spawn and Closeout Governance Matrix.md` -> blocked/main-session rules, anti-patterns, executive-summary gate

Retrospective guidance coverage:
- keep bounded usefulness as a first-class success state
- resist widening useful pilots into speculative automation

### D. Ownership / subordinate-surface labeling
Already covered.
- `Major Workflow Contract Standard.md` -> `Owner Layer`, `Surface / Handoff Posture`, `Canonical Mutation Posture`, `Stop Lines`
- `Spawn and Closeout Governance Matrix.md` -> core rule, helper-lane authority, anti-patterns, default posture for current research automation lane

Retrospective recommendation coverage:
- recommendation 4 (`open widening workflows only when a consumer is real`)
- recommendation 5 (`keep subordinate surfaces labeled by function`)

### E. Cross-surface state agreement at closeout
Covered in principle, but not with the retrospective’s full explicit surface list.
- `Major Workflow Contract Standard.md` -> preflight and exit checklists require queue/registry/continuity agreement
- `Spawn and Closeout Governance Matrix.md` -> executive-summary gate and closeout checklist require queue/registry/continuity agreement
- `Workflow Closeout Artifact Standard.md` -> required artifacts include continuity, chain log, registry, queue, audit artifact, executive summary; cross-surface honesty rule names several failure cases

Retrospective recommendation partial coverage:
- recommendation 1 (`mandatory closeout sync checklist`) is directionally present

## 2) Real uncovered or under-specified gaps

### Gap 1. No explicit stale-diagnosis cleanup rule
This is the clearest real miss.

The retrospective recommends: when live checks overturn an earlier blocker or diagnosis, the closing artifact should explicitly mark the old claim stale and point to the new truth source.

Current standards require honesty and current-state agreement, but none explicitly require:
- marking earlier claims as stale
- naming the superseding source
- cleaning up inherited ghost blockers in the owning note or audit

Why it matters:
- prevents reopened solved blockers by inheritance
- reduces ghost residue after live reality changes
- directly addresses the WF31 pattern called out by the retrospective

### Gap 2. Closeout sync checklist lacks one explicit canonical surface bundle
The standards repeatedly require agreement across queue/registry/continuity and mention chain logs, audits, executive summaries, and memory in different places, but there is no single explicit checklist that mirrors the retrospective’s exact closeout-sync bundle:
- queue top summary
- recently closed section
- registry row
- continuity note
- audit/verdict note
- daily memory entry

This is not a conceptual gap in intent; it is a packaging/clarity gap.

Why it matters:
- the retrospective’s failure mode was not absence of closeout theory; it was surface drift through incomplete synchronized updates
- one concrete list would reduce interpretation wiggle room during closeout

### Gap 3. Artifact regeneration is implied, not explicitly mandatory when shared contracts change
The standards already require acceptance evidence and smallest meaningful proof, but they do not explicitly say that for shared-contract changes the workflow must refresh any contract-bearing generated artifacts before claiming closure.

The retrospective recommendation is more precise:
- change code/contract
- regenerate artifacts/sidecars/summaries that embody that contract
- rerun the smallest downstream gate

Why it matters:
- addresses the WF32/WF33 pattern where code landed ahead of proof artifacts
- converts a broad proof norm into a specific anti-fake-green sequence

## 3) Exact file / section changes worth making

These are the smallest worthwhile canonical edits.

### Proposed change A
File:
- `06. Playbooks/Workflow Closeout Artifact Standard.md`

Section to change:
- `Required closeout artifacts`

Suggested addition:
- add a new explicit item or sub-bullets under queue/registry/continuity requiring a **closeout sync bundle** check naming at minimum:
  - queue top summary
  - recently closed section
  - registry row
  - continuity note
  - audit/verdict artifact
  - daily memory entry
- allow explicit defer only when named honestly in the artifact

Why here:
- this file is the most direct home for a mandatory closeout artifact bundle

### Proposed change B
File:
- `06. Playbooks/Major Workflow Contract Standard.md`

Section to change:
- `Exit / Closeout Checklist`

Suggested addition:
- add one checklist item such as:
  - `if a prior blocker/diagnosis was overturned by later live checks, the closeout must mark the earlier claim stale and point to the superseding truth source`
- add one checklist item such as:
  - `if shared contract/code changed, regenerate affected contract-bearing artifacts and rerun the smallest downstream acceptance gate before closure`

Why here:
- this standard governs workflow execution and closeout behavior directly
- it is the best place to turn the retrospective lessons into operator-facing workflow obligations

### Proposed change C
File:
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`

Sections to change:
- `Independent auditor closeout rule`
- `Closeout checklist`

Suggested additions:
- in `Independent auditor closeout rule`, add that the auditor should flag stale inherited diagnoses when live evidence supersedes them
- in `Closeout checklist`, add explicit synchronized-surface verification wording that includes recent-closures and daily-memory surfaces, not just queue/registry/continuity

Why here:
- this document is the canonical spawn/closeout governance source
- the audit lane is the right place to enforce stale-claim challenge behavior

## 4) Recommended priority

1. **Highest value:** add the stale-diagnosis cleanup rule
2. **Next:** add one explicit closeout sync bundle checklist
3. **Then:** sharpen shared-contract proof refresh language into a mandatory sequence

## 5) Recommendation on whether to edit now

Worth editing, but only as a small standards-tightening pass.
No broad rewrite appears justified.
The retrospective mostly confirms the standards are directionally right; the real need is to make three narrow expectations more explicit.

## Verification performed
- Read and compared the four named source documents directly.
- Checked each retrospective recommendation against the relevant standard sections.
- Produced proposal only under `tmp/`; made no canonical document edits.
