---
name: "workspace-qa-pass"
description: "Risk-budgeted independent QA with frozen scope, adversarial route/privacy checks, and bounded repair loops."
---

# Workspace QA Pass

## Purpose

Provide independent findings-first review of material workspace changes without turning QA into automatic ritual, hidden reimplementation, or acceptance authority.

QA verifies claims against live files, frozen handoffs, exact owner surfaces, validators, and adversarial probes. Main alone accepts and integrates work.

## When Independent QA Is Required

Require fresh independent QA for:

- shared or major contracts;
- broad multi-surface changes;
- finance, runtime, authority, privacy, or execution-sensitive semantics;
- judgment-heavy behavior that deterministic tests cannot fully prove;
- a repaired material QA finding before Main acceptance.

For `micro` or `narrow` low-risk changes, focused deterministic proof plus Main verification may be sufficient. Do not require a full Builder-to-QA cycle for every patch.

## Frozen Review Scope

Before review, require:

- exact base path;
- at most 6 files, 120,000 bytes, and 30,000 estimated context tokens;
- sorted paths, exact sizes, SHA-256 hashes, contract hash, and frozen snapshot ID;
- task claim, acceptance criteria, authority class, changed behavior, tests, stop lines, and known limits;
- expected backend/model/thinking and attempt/retry identity.

Verify hashes before and after QA. If the source changes, reject the snapshot and review a newly frozen package. Review changed hunks and exact consumer contracts first; avoid broad reads unrelated to the claim.

## Findings Contract

Lead with defects ordered by severity:

`Severity — file:line — issue — impact — required repair or proof`

Separate verified bugs, risks, assumptions, and residual limitations. If no material blocker exists, say PASS plainly and name remaining proof gaps.

QA is read-only unless a separately leased repair lane is explicitly assigned. Do not edit while reviewing and then certify the same snapshot.

## Review Checklist

1. Confirm scope, lease/read-only posture, frozen snapshot, and authority.
2. Inspect changed hunks and exact producer/consumer contracts.
3. Check expected versus actual backend/model/thinking and native/persistent provenance.
4. Verify path containment, file/context budgets, manifest/hash integrity, and completion re-hash.
5. Run the smallest focused tests that cover changed behavior.
6. Add adversarial probes for bypasses tests may miss: stale proof, boundary values, conflicting identity, override tampering, incomplete metadata, incident inflation, and privacy leakage.
7. Verify retry/attempt truth, 90-second incident SLA, idempotence, and monotonic changed-event timestamps.
8. Verify privacy: no raw prompts, responses, tools, credentials, account data, or raw session/correlation identifiers.
9. Check authority flags and confirm no config/auth/channel/runtime/cron/finance/execution/external/destructive expansion.
10. Compare user-facing completion claims with proof and downgrade unsupported claims.

## Efficiency QA

Confirm that:

- deterministic/model-free work was considered first;
- Codex-native was explicit and eligible;
- persistent Terra had fresh strict transport proof;
- Main/Sol was an explicit exception rather than fallback;
- no caller override rewrote the selected backend/model/thinking;
- usage semantics distinguish cached, uncached, output, reasoning, and total;
- `provider_usage_unavailable` remains unavailable rather than zero;
- incidents and invalid telemetry receive no completion, first-pass, QA-pass, Main-accepted, or cohort credit;
- like-for-like cohort eligibility uses at least 10 comparable Main-accepted jobs;
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

## Finance And Authority Boundary

QA may challenge finance evidence and guardrail proof. It cannot approve finance recommendations, portfolio/canon mutations, paper/live orders, account actions, capital deployment, money movement, runtime/config changes, cron schedules, external delivery, or destructive cleanup.

## Closeout

Return verdict, findings, validation proof, snapshot/hash proof, route-conformance result, privacy/authority result, residual risks, and exact next action. A QA pass is advisory evidence for Main, not owner approval or execution authority.
