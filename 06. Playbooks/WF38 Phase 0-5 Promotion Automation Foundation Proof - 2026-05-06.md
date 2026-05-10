# WF38 Phase 0-5 Promotion Automation Foundation Proof - 2026-05-06

## Purpose
Record the first fail-closed automation foundation for promotion review and sector-expansion candidates.

This proof does not authorize ticker promotion, owner-note mutation, or capital deployment.

## User-approved posture
Randall approved:
- weekly sector-expansion review as a real standing decision checkpoint
- owner-layer cleanup work to define or refresh bands for underdefined candidates
- band review work for LLY and CAT
- wider promotion automation as a priority, provided the fail-closed foundation exists first

## Files landed
- `scripts/schemas/candidate_packet_schema.json`
- `scripts/candidate_packet_validator.py`
- `scripts/portfolio_integrity_check.py`
- `scripts/catalyst_window_check.py`
- `scripts/ranking_shadow_canon_check.py`
- `06. Playbooks/Promotion Review Queue.md`
- `tmp/wf38-fixtures/passing_packet.json`
- `tmp/wf38-fixtures/failing_packet.json`
- `tmp/wf38-fixtures/blocked_catalyst_packet.json`
- `tmp/wf38-fixtures/sector_breach_packet.json`
- `tmp/wf38-fixtures/deployable_missing_queue_packet.json`
- `tmp/wf38-fixtures/deployment-check-shadow-violation.json`

## Contract alignment
Candidate packet schema now includes the required automation fields:
- `ticker`
- `proposed_lane`
- `thesis_exists`
- `levels_exist`
- `timing_posture`
- `portfolio_competition_assessed`
- `sector_cap_checked`
- `correlated_sleeve_checked`
- `catalyst_window_status`

Catalyst vocabulary is intentionally limited to:
- `clear`
- `warning`
- `blocked`
- `unknown`

## Guardrail decision
`ALMOST DEPLOYABLE` does not require a Promotion Review Queue row by default.

Queue entry is required for:
- `DEPLOYABLE`
- `DEPLOYABLE NOW`
- explicit written threshold override

Reason: ALMOST means at least one blocker remains; auto-queueing every ALMOST name creates noisy false urgency instead of a better promotion process.

## Proof run
Command set:

```powershell
python -m py_compile scripts\candidate_packet_validator.py scripts\portfolio_integrity_check.py scripts\catalyst_window_check.py scripts\ranking_shadow_canon_check.py
python scripts\candidate_packet_validator.py tmp\wf38-fixtures\passing_packet.json
python scripts\portfolio_integrity_check.py tmp\wf38-fixtures\passing_packet.json
python scripts\catalyst_window_check.py tmp\wf38-fixtures\passing_packet.json
python scripts\ranking_shadow_canon_check.py tmp\wf38-fixtures\passing_packet.json
python scripts\ranking_shadow_canon_check.py
python scripts\candidate_packet_validator.py tmp\wf38-fixtures\failing_packet.json
python scripts\portfolio_integrity_check.py tmp\wf38-fixtures\failing_packet.json
python scripts\catalyst_window_check.py tmp\wf38-fixtures\failing_packet.json
python scripts\catalyst_window_check.py tmp\wf38-fixtures\blocked_catalyst_packet.json
python scripts\portfolio_integrity_check.py tmp\wf38-fixtures\sector_breach_packet.json
python scripts\ranking_shadow_canon_check.py tmp\wf38-fixtures\deployable_missing_queue_packet.json
python scripts\ranking_shadow_canon_check.py --deployment-check tmp\wf38-fixtures\deployment-check-shadow-violation.json
```

Result:
- compile proof passed
- passing packet passed all four checks
- current live deployment-check scan passed with zero deployable records requiring queue rows
- failing packet failed candidate validation as expected
- failing packet failed portfolio integrity as expected
- LLY missing-calendar fixture failed as `unknown` catalyst as expected
- LNG present-calendar fixture failed as `blocked` catalyst as expected
- NVDA sector-breach fixture failed sector and correlated-sleeve checks as expected
- deployable-missing-queue fixture failed as expected
- deployment-check shadow violation fixture failed as expected
- live LLY candidate packet is schema-valid and blocked as expected: missing earnings-calendar coverage, no canonical entry/invalidation, and owner-layer sizing still required
- live CAT candidate packet is schema-valid and blocked as expected: sector/catalyst checks pass, but thesis, band drift, and sizing gates still require owner-layer review

## Remaining residue
- `LLY` is absent from `tmp/earnings-calendar.json`; fail-closed behavior correctly blocks catalyst clearance until calendar coverage exists.
- correlated-sleeve taxonomy is currently local to `portfolio_integrity_check.py`; future hardening should centralize it in config or a schema-owned artifact.
- the scripts are not yet wired into a scheduled weekly review chain; this is intentional until WF38 active handoff and repeated proof are complete.

## Next action
- Use the new foundation to run owner-layer band review and candidate-packet prep for LLY and CAT.
- Do not promote either name until the packet validator, portfolio integrity check, catalyst check, queue state, and owner-layer review all align.
