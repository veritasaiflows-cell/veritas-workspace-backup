# WF37 Phase 3 Brief Lint and Guard Proof - 2026-05-06

## Purpose
Prove the first bounded validator for future commercial briefs catches authority drift before any real writer trial is promoted.

## Implementation
- added `scripts/summary_brief_lint.py`
- validator checks:
  - packet posture stays `review_only`
  - packet does not allow canonical mutation
  - draft includes review/routing language
  - draft cites at least one required owner layer
  - draft does not use forbidden authority / trade language
  - draft visibly preserves unresolved-truth posture when the packet carries unresolved truths

## Proof run
- `python -m py_compile scripts\summary_brief_lint.py`
- `python scripts\summary_brief_lint.py --packet tmp\premarket-brief-input.json --draft legacy tmp artifact tombstoned in `state/tmp-lifecycle-deletion-tombstone.json` (`wf37-safe-draft.md`)` -> `status: ok`
- `python scripts\summary_brief_lint.py --packet tmp\premarket-brief-input.json --draft legacy tmp artifact tombstoned in `state/tmp-lifecycle-deletion-tombstone.json` (`wf37-unsafe-draft.md`)` -> expected failure with 7 issues:
  - missing routing language
  - missing owner citations
  - publishes deployable-now state
  - uses direct trade instruction
  - implies immediate readiness authority
  - clears a blocker in summary language
  - hides unresolved-truth posture

## Result
Phase 3 proof is good enough to move WF37 forward to the first bounded writer-trial prep.
The validator is intentionally simple, but it already fails the exact authority drift this workflow is trying to prevent.

## Residue
- no real AI-written brief has been trialed yet
- lint coverage is phrase-based, not semantic adjudication
- cron promotion remains out of scope until a real writer trial passes cleanly
