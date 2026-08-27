---
name: "implementation-friction-closeout"
description: "Close recurring implementation friction: stale artifacts, validator order, lane/write drift, Skill Workshop hazards, and warning residue."
---

# Implementation Friction Closeout

Use this skill when a task reveals repeated implementation friction: stale generated artifacts causing false failures, lane contracts that no longer match writes, validator order problems, recurring test gaps, Skill Workshop body-replacement hazards, or closeout residue that keeps reappearing across sessions.

## Contract

- Treat friction as evidence, not annoyance.
- Preserve authority boundaries first: no portfolio/canon mutation, paper/live/account action, credential/auth/runtime/config mutation, external action, or cron schedule mutation unless a separate exact approval exists.
- Do not apply skills, config, or policy changes from this skill. Produce scoped repairs, proof, or pending proposals only.

## Skill Workshop Body-Replacement Guard

When creating, revising, reviewing, or applying Skill Workshop proposals for an existing live skill, assume `proposal_content` will become the full live `SKILL.md` body unless the tool contract explicitly proves otherwise.

Do not apply an existing-skill update proposal when any of these are true:

- the proposal title starts with `# Proposed Update` instead of the real live skill title
- the body is an addendum, summary, patch note, heading-hygiene note, or partial section rather than a full merged skill document
- the proposal says `Preserve existing behavior` but does not include the existing behavior in the proposed body
- the proposal is materially shorter than the current live skill without an explicit replacement intent
- important live sections would disappear after apply

Required pre-apply sequence for existing-skill updates:

1. Inspect the live `skills/<skill>/SKILL.md`.
2. Inspect the pending proposal.
3. Build or revise the proposal into a full-body merged document that preserves existing doctrine and inserts the new rule in the narrowest relevant section.
4. Apply only after the proposed body can stand alone as the live skill file.
5. Immediately read back the live `SKILL.md` after apply.
6. Search the touched skill for `# Proposed Update` and other thin-proposal residue.
7. If body replacement occurred, repair through a full-body Skill Workshop proposal before closeout.

For multi-skill batches, apply one skill, inspect live body, then continue. Do not batch-apply multiple existing-skill updates unless each proposal has already passed the full-body check.

## Workflow

1. Name the friction pattern in one sentence.
2. Check the concurrent lane register before edits.
3. If files will be written, lease the exact write surfaces and include generated proof artifacts, sidecars, SQLite WAL/SHM files when relevant, and append-only ledgers if used.
4. Inspect producer-consumer order before rerunning validators. Refresh source artifacts before downstream scorecards, harnesses, ledgers, and session packets.
5. Classify the fix:
   - `code_patch`: small deterministic script/test/harness correction.
   - `artifact_refresh`: stale derived proof/index rebuild only.
   - `skill_proposal`: repeated procedure problem that should become a pending Skill Workshop proposal.
   - `owner_gate`: config, collector depth, schedule, authority, or policy decision.
   - `skill_workshop_full_body_repair`: existing skill update proposal or live skill body risks thin-proposal replacement and needs full-body repair.
6. Apply only scoped code patches that are inside the active lane and do not widen authority.
7. Validate with the smallest complete chain: focused unit/path tests, producer artifact, downstream consumer, and final route/scorecard.
8. Record what remains as real backlog, expected pending gate, or blocked owner decision. Do not make the loop look green by hiding unresolved debt.

## Expected Outputs

- A concise friction diagnosis.
- A repaired lane/write contract if needed.
- A producer-order validation list.
- Updated tests or harness predicates when the old gate was semantically wrong.
- Pending Skill Workshop proposal only when the issue is reusable procedure debt.
- Full-body Skill Workshop repair proposal when an existing-skill update is thin, stale, or body-replacing.
- Final proof that distinguishes fixed, expected-pending, and still-blocked items.

## Stop Lines

Stop and escalate if the fix would require destructive cleanup, config/auth/network/service/startup mutation, collector config changes, cron schedule mutation, portfolio/canon/cash/sizing/risk mutation, paper/live/account action, or owner approval inference.
