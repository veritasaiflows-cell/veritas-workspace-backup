# Research Automation Freshness Candidate Input Contract

## Purpose
Define the exact v1 input object that WF22 will feed into `scripts/canonical_freshness_patch.py`.

This is a **patch-proposal input object**.
It is not an apply request.
It is not permission to rewrite canon.

## Top-level file shape
Accepted file shapes:
1. a JSON list of freshness-candidate objects
2. a JSON object with one key: `candidates`, where `candidates` is a list of freshness-candidate objects

## Required v1 candidate fields
Every v1 freshness-candidate object must include these keys explicitly:
- `target_note` - path to the note that may need a patch
- `stale_claim` - exact stale claim or stale section summary
- `why_stale` - why the claim is stale
- `new_evidence` - array of evidence objects
- `source_quality` - string such as `tier_1_primary`, `tier_2_trusted`, `rumor_unverified`
- `freshness_class` - one of `mechanical_date_elapsed_event`, `post_catalyst_status`, `cross_surface_contradiction`, `thesis_or_posture_change`
- `patch_scope` - narrow scope description
- `proposed_replacement` - exact replacement text or patch proposal text
- `judgment_impact` - one of `none`, `possible`, `material`
- `affected_surfaces` - array of paths or surface names
- `required_downstream_sync` - array of follow-up sync steps
- `rollback_note` - how to revert the patch if approved and later found wrong
- `verifier_signoff` - string
- `main_approval_required` - boolean and must remain `true`

## Optional v1 candidate fields
- `linked_packet_id` - packet id that led to this candidate
- `notes` - operator notes

## Evidence object shape
Each item in `new_evidence` may include:
- `title`
- `source`
- `source_quality`
- `url`
- `published_at`
- `excerpt`

## Safe-use rule
Normal safe v1 patch classes are:
- `mechanical_date_elapsed_event`
- `post_catalyst_status`

Higher-risk v1 classes:
- `cross_surface_contradiction`
- `thesis_or_posture_change`

Higher-risk classes may be drafted for review, but they should not be treated as normal fast-path patch help.

## Stop / reject expectations
A candidate should be review-escalated or rejected when:
- `main_approval_required` is false
- `judgment_impact` is `material`
- `freshness_class` is `thesis_or_posture_change`
- evidence is rumor-heavy or weak
- the patch scope is broad enough to behave like a thesis rewrite

## V1 operating rule for WF22
WF22 should use this object in this order:
1. receive a high-confidence stale or alignment issue
2. write the candidate into this contract shape
3. run `python scripts\\canonical_freshness_patch.py --input <file>`
4. inspect proposal status, rejection reasons, and downstream sync requirements
5. require main-session approval before any apply

## Out of bounds
This input contract does not authorize:
- auto-apply
- silent note mutation
- thesis or posture rewrite
- deployment-state changes
- using geopolitical rumor as freshness justification
