# Subagent Load Budget and Staff Handoff Standard

## Purpose
Prevent new sessions/helper lanes from being overloaded with the entire workspace, stale history, or unclear authority. Use small, file-grounded handoffs by staff lane.

## Core Rule
A helper lane should receive only the doctrine slice, owner surfaces, exact task files, stop lines, output contract, and proof requirements needed for its assignment.

Route authority is `scripts/project_implementation_router.py` (`veritas.execution_efficiency_policy.v1`): model-free first; explicit bounded Codex-native Terra; explicit Main/Sol exceptions; otherwise persistent Terra only with fresh strict transport proof. A missing transport proof blocks dispatch and does not justify silent Main fallback.

## WF71 Department Routing Gate
Before spawning a helper lane, Veritas main should run two checks:

1. **Main-session minimal check** - keep the task in main if it is a one-step lookup/edit, a final authority judgment, a queue/control-surface decision, or an owner-facing synthesis that does not require broad proof.
2. **Department/helper check** - delegate only when the task is multi-artifact, proof-heavy, implementation-heavy, broad-inspection, or independent-QA useful; name exactly one primary department owner and list secondary consumers without writer authority.

Use WF71 department ownership as a routing index, not a new authority layer. Staff lanes are helper roles, not autonomous identities. Veritas main remains final integrator, owner-facing truth surface, queue owner, and authority boundary.

## Default Load Budget
- Doctrine: cite or summarize `SOUL.md`/`AGENTS.md` hard boundaries in the handoff; do not paste broad doctrine unless needed.
- Skills: read at most one relevant skill up front unless the lane is explicitly multi-domain.
- Artifact awareness: when a helper needs generated artifact/proof/provenance context, prefer current SQL cockpit output (`scripts/artifact_index.py cockpit`, `ticker-cockpit`, `trust-cockpit`, `proof-field`, `ticker-card`, `answer-packet`, `validate`) over handing it broad `tmp/` directory scans. Include only the specific target artifact paths it must inspect after SQL routing.
- Files-to-read-first: at most 6 exact files, 120,000 total bytes, and 30,000 estimated context tokens per frozen handoff. Split a broad audit rather than widening these ceilings.
- Broad audit lanes: read-only by default and must return a claim matrix plus priority recommendations.
- Outputs: one summary artifact/final response plus exact proof paths; JSON artifacts must parse.
- Runtime: fresh isolated sessions by default; forked context only when transcript context is required.
- Ownership: exactly one primary department/helper lane per delegated task; no two helper lanes may write the same canonical owner surface.
- Main-session fallback: if routing is ambiguous, authority-sensitive, or lacks exact read-first files, keep the decision in main or ask the smallest concrete question.
- Frozen proof: require an explicit workspace-relative base path, sorted file inventory and SHA-256 hashes, deterministic preflight, frozen snapshot id, and closeout rehash.
- Route telemetry: require parent job, phase, attempt/retry, expected/actual backend/model/thinking, handoff files/bytes/tokens, elapsed time, authoritative usage or truthful unavailable status, QA verdict, and Main acceptance.

## Required Handoff Fields
Every helper-lane prompt should include:

1. **Staff lane / role**
2. **Objective**
3. **Files to read first**
4. **Allowed actions**
5. **Forbidden actions / stop lines**
6. **Output contract**
7. **Acceptance proof**
8. **Timeout / partial-output expectation**
9. **Merge expectation** - read-only, patch proposal, artifact write, or implementation
10. **Authority boundary** - especially finance/trading/config/destructive boundaries
11. **Route proof** - router artifact, selected backend/model/thinking, and persistent transport proof when applicable
12. **Frozen handoff** - base path, manifest, snapshot id, exact file/byte/context totals
13. **Incident/attempt contract** - 90-second provisional update, attempt id, retry reason, and first-pass separation

## Staff Lane Defaults

| Staff lane | Typical files-to-read-first | Default merge mode |
|---|---|---|
| Official Source Desk | WF70 note, company source metadata, target capture scripts/artifacts | Artifact or patch proposal |
| Alerts and Recommendations Desk | WF84 evidence, WF85 non-executing recommendations, active alert canon, current freshness proofs | Artifact/implementation with tests; no finance-state ownership |
| Analytics / Probability Desk | WF69, WF55, state-history artifacts, validators | Artifact/validator; no probability claims |
| Finance Alert Canon Steward | guarded SQL, Alert Trigger Policy, Alert Bands and Invalidation Register, pivot validator | Read-only audit or exact owner-approved alert-canon patch with numeric-preservation proof; no construction or simulated-account state |
| OS Operator / Automation Desk | Active Workflows, target continuity note, runtime docs, relevant scripts | Patch proposal/implementation; config gated |
| Independent QA Desk | Target files/artifacts only plus governing boundaries | Read-only report unless explicitly scoped |

## Anti-Overload Rules
- Do not ask a helper lane to read all of `memory/`, all workflows, all scripts, and all finance notes unless it is explicitly a broad audit lane.
- Do not combine implementation, QA, workflow governance, finance judgment, and archive cleanup in one helper.
- Do not ask a helper to decide final queue priority; Veritas main integrates.
- Do not let a helper infer owner approval from validation success.
- Do not give write access to a helper lane touching canonical finance notes unless the scope, target files, and validators are exact.

## Positive / Negative Skill Trigger Check
Each handoff should state why the selected department/skill is positively triggered and which negative triggers were checked. Do not load a specialist skill by habit. Do not spawn a department lane when a negative trigger applies, including owner-approval inference, final queue movement, forbidden mutation, live account/trading/money movement, ungated canon mutation, or config/auth/channel/service mutation.

Minimum acceptance checks:
- exactly one primary department/helper lane named;
- read-first list stays within budget or the broad-audit exception is explicit;
- manifest file/byte/context totals are within the non-widenable handoff budget;
- expected and actual backend/model/thinking match at closeout;
- allowed write surfaces are named and collision-free;
- validator/test/direct-inspection proof is named;
- authority flags remain hard-false unless a separate exact approved gate is in scope;
- main session remains final integrator.

## Closeout Standard
A helper closeout must state:
- what it inspected
- what it changed or did not change
- proof/tests/validators
- blockers/trust gaps
- exact next action
- whether output is safe to merge, needs audit, or is review-only
- uncached and gross tokens when authoritative, elapsed time, retry tax, and whether the result was first-pass Main-accepted

Validation budget: micro work uses deterministic proof plus Main verification; narrow work uses focused tests plus Main; shared/major or privacy/security/authority/finance/repeated-failure work uses one fresh independent QA after deterministic preflight. After one repair and one rerun, another rejection returns to Main for root-cause/scope reclassification.

Efficiency comparison is like-for-like and quality-weighted. Incidents, invalid telemetry, unavailable route evidence, and mismatches receive no success credit. Ten comparable Main-accepted jobs is the evidence gate; automatic ranking and promotion remain disabled.

## Security Boundary
Config/auth/channel/network/service/credential changes are never helper-default. They require explicit owner approval and main-session review.
