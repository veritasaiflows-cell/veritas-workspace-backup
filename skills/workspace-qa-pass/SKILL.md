---
name: "workspace-qa-pass"
description: "Normalize residual encoding corruption to ASCII."
---

# Workspace QA Pass

Run an independent review. Do not act like the implementation lane defending its own patch.

## Purpose

Find the real remaining risk after a workstream lands:
- integrity debt
- orchestration drift
- control-surface debt
- doctrine/procedure mismatch
- stale or fake closure claims

Keep the pass bounded. Prefer evidence over broad redesign.

QA verifies claims against live files, frozen handoffs, exact owner surfaces, validators, and adversarial probes. QA is not execution authority. Main alone accepts and integrates work.

## When Independent QA Is Required

Require fresh independent QA for:

- shared or major contracts;
- broad multi-surface changes;
- finance, runtime, authority, privacy, or execution-sensitive semantics;
- judgment-heavy behavior that deterministic tests cannot fully prove;
- a repaired material QA finding before Main acceptance.

For `micro` or `narrow` low-risk changes, focused deterministic proof plus Main verification may be sufficient. Do not require a full Builder-to-QA cycle for every patch.

## Read first

Read only what the pass needs, but default to:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- the current workflow contract or playbook entry if the pass targets a named workflow
- the current daily note if the work happened today
- the changed files and the smallest useful neighboring files
- the most relevant prior audit in `08. Audits/`

If the pass is about skills, also read one or two strong local skills to match current workspace style.

## Boundaries

Do not widen into full architecture redesign.
Do not touch auth, network exposure, or permissions unless the requested QA task is explicitly about them.
Do not mutate canonical finance notes unless the task explicitly includes a note-layer fix.
Default outputs are an audit note, a bounded fix list, or a skill/workspace recommendation.
QA may challenge finance evidence and guardrail proof. It cannot approve finance recommendations, portfolio/canon mutations, paper/live orders, account actions, capital deployment, money movement, runtime/config changes, cron schedules, external delivery, or destructive cleanup.

## Frozen Review Scope

Before review, require:

- exact base path;
- at most 6 files, 120,000 bytes, and 30,000 estimated context tokens;
- sorted paths, exact sizes, SHA-256 hashes, contract hash, and frozen snapshot ID;
- task claim, acceptance criteria, authority class, changed behavior, tests, stop lines, and known limits;
- expected backend/model/thinking and attempt/retry identity.

Verify hashes before and after QA. Re-hash mutable canonical comparators immediately before writing the result; if they drift concurrently, record inequality and the observation order without attributing causation. If the source changes, reject the snapshot and review a newly frozen package. Review changed hunks and exact consumer contracts first; avoid broad reads unrelated to the claim. When adversarial fixtures contain symlinks, junctions, or reparse points, inventory only named bounded directories and files; never recursively enumerate through the fixture tree.

## Findings Contract

Lead with defects ordered by severity:

`Severity  -  file:line  -  issue  -  impact  -  required repair or proof`

Separate verified bugs, risks, assumptions, and residual limitations. If no material blocker exists, say PASS plainly and name remaining proof gaps.

QA is read-only unless a separately leased repair lane is explicitly assigned. Do not edit while reviewing and then certify the same snapshot.

## Procedure

1. Reconstruct the claimed contract.
   - What was supposed to be hardened, prevented, or proven?
   - What was explicitly out of scope?

2. Inspect the live implementation surface.
   - Read the changed files, not just summaries.
   - Check adjacent orchestrators, helpers, validators, and output writers that can silently reintroduce drift.
   - For derived-graph integrity, hash the requested graph and resolve each suspect edge's source file and location before assigning a collision hypothesis. Where the graph records a Git commit, compare those source bytes with that commit.
   - Trace identity allocation, duplicate-node handling, endpoint remapping, and metadata propagation in the installed extractor. Treat post-build diagnostics as evidence about surviving records, not proof that extraction preserved every source entity or call.
   - Reproduce structural collisions with bounded parser-only inputs, never by importing or executing the source producers. For Graphify, inspect the installed `_extract_generic` implementation before using `source_override` for an in-memory fixture; run Python with `-B` and `PYTHONDONTWRITEBYTECODE=1` to avoid bytecode writes.
   - Test a proposed correction on an in-memory graph copy first. Assert the exact allowed node/edge diff, unchanged unrelated records and source coverage, endpoint integrity, and inverse-patch equality. Preserve existing IDs and distinguish inherited community assignments from recomputed analysis. A suppressed self-loop alone does not restore a lost entity.
   - Rehash the original graph, inspected sources, and relevant sidecars at closeout. Report an in-memory candidate separately from a saved or applied repair, and state any untested call-resolution consequences; a read-only request authorizes no rebuild, export, cache refresh, or repair write.

3. Test for mismatch across five QA lenses.
   - **Trust enforcement:** do policy flags actually block behavior, or only describe it?
   - **Write integrity:** where do meaningful outputs still bypass shared atomic helpers?
   - **Schema honesty:** where do downstream consumers still assume happy-path shapes?
   - **Control surface:** what still depends on flaky session/runtime assumptions?
   - **Workspace hygiene:** did the work create new duplication, stale notes, vague ownership, or procedural spillover into core files?

4. Rank only concrete findings.
   - Prefer a short list of real residual risks.
   - Separate closed items from still-open debt.
   - Do not relitigate issues already fixed unless new evidence shows regression.

5. Recommend the next bounded tightening step.
   - Name the smallest next pass that materially improves trust.
   - Avoid giant omnibus cleanup plans.

6. Check closeout honesty.
   - Was checkpoint posture made explicit?
   - Do queue / registry / continuity note agree?
   - Is the next pass or adjacent candidate routing explicit instead of implied?

7. Validate the QA artifact or skill you create.
   - Use the smallest meaningful check available: direct inspection, targeted grep/search, `openclaw skills check`, or another local validator.
   - If no validator exists, say that plainly.

## Review Checklist

1. Confirm scope, lease/read-only posture, frozen snapshot, and authority.
2. Inspect changed hunks and exact producer/consumer contracts.
3. Check expected versus actual backend/model/thinking and native/persistent provenance.
4. Verify path containment, file/context budgets, manifest/hash integrity, and completion re-hash.
5. Run the smallest focused tests that cover changed behavior.
6. Add adversarial probes for bypasses tests may miss: stale proof, boundary values, conflicting identity, override tampering, incomplete metadata, incident inflation, and privacy leakage.
7. Verify retry/attempt truth, incident SLA conformance, idempotence, and monotonic changed-event timestamps.
8. Verify privacy: no raw prompts, responses, tools, credentials, account data, or raw session/correlation identifiers.
9. Check authority flags and confirm no config/auth/channel/runtime/cron/finance/execution/external/destructive expansion.
10. Compare user-facing completion claims with proof and downgrade unsupported claims.

## Efficiency QA

Confirm that:

- deterministic/model-free work was considered first;
- the selected implementation lane was explicit and eligible for the work class;
- any persistent lane had fresh strict agent-matched transport proof, and any write route also had scoped-writeback proof;
- Main was an explicit quick-fix, final-integration, or authority-sensitive exception rather than fallback;
- no caller override rewrote the selected backend/model/thinking;
- usage semantics distinguish cached, uncached, output, reasoning, and total;
- `provider_usage_unavailable` remains unavailable rather than zero;
- incidents and invalid telemetry receive no completion, first-pass, QA-pass, Main-accepted, or efficiency success credit;
- on-demand route review may use available token attribution, elapsed-time, retry, acceptance, and escaped-defect evidence with no fixed cohort pilot or minimum job count; prefer like-for-like comparisons when available;
- automatic route ranking and promotion remain disabled.

API-equivalent estimates are not invoices. Token totals do not prove OAuth impact or billed cost.

## Validation Depth And Retry Limit

- `micro`: inspect deterministic proof and Main verification path.
- `narrow`: focused tests plus one or two targeted adversarial probes.
- `shared` or `major`: focused suite plus independent adversarial matrix.

One substantive rejection may return to Main for one bounded repair lane and one fresh QA attempt. If a second substantive rejection remains, recommend rescoping or splitting the contract. Do not create unbounded QA/repair loops.

## Long-Work Closeout

Require proof of route selection, exact writes, parent/phase/attempt/retry, validation commands/results, consumer compatibility, usage availability, incidents/rework, Main acceptance evidence, continuity update decision, and residual blockers.

Missing closeout metadata can make closure partial even when the implementation behavior is valid. Never convert missing evidence into a clean first-pass result.

## Evidence standard

Do not write generic advice.
Anchor findings in concrete files, commands, outputs, or observable workflow order.
Treat prior chat claims, stale audits, and detached-session state as supporting evidence only until live workspace state matches them.

## Output format

Return in this order:
- scope audited
- files inspected
- top findings
- recommended next pass
- validation run
- intentionally deferred items
- verdict, snapshot/hash proof, route-conformance result, privacy/authority result, residual risks, and exact next action

A QA pass is advisory evidence for Main, not owner approval or execution authority.

## Default edit posture

If asked only for QA, prefer writing an audit note over making broad fixes.
If asked for a small repair too, keep it tightly tied to the findings and verify it.

## Good pass standard

A good QA pass should make it harder for the workspace to lie about its own state.
