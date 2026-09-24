# Phase 4: tier promotion and demotion design

Owner: Main. Requested by Randall in Telegram on 2026-09-07 at 18:24 America/Phoenix.

Status: **design record only.** Nothing here is implemented, scheduled, or approved. This document grants no guarded-SQL tier write, no canon mutation, no cron install, no provider expansion, and no activation authority. It records the current verified mechanism, the named gaps, and the recommended target shape so Phase 4 can be decided on evidence instead of re-derived later.

Policy owner: `Tier Entitlement and Atomic Promotion Review Contract.md` (v0.9.1). That contract already owns the promotion/demotion *state machines*, lease mechanics, proof requirements, and falsification tests. It defers the implementation to its own "Implementation phases requiring later approval" item 4. This note is that deferred implementation design, not a second policy.

Phase identity: the finance program's Phase 4, named in the contract at "guarded-SQL tier transactions (Phase 4)" and "Phase 4 separately owns any guarded-SQL tier transaction." This is **not** AGI Readiness Phase 4 (stronger-model admission), which is a separate program in `AGI Readiness Opportunity Plan - 2026-09-06.md`.

Scope note added 2026-09-17: this record covers tier movement mechanism only. `Alerts OS Unified Objective - 2026-09-17.md` states the program's outcome objective and finds that Phase 4 as designed addresses one of its five claims, and only the mechanism half of that one. Phase 4 is a prerequisite for scale, not the plan for meeting the objective. Decide Phase 4 scope against that record, not against this one alone.

**Sequencing decision added 2026-09-17: Phase 4 no longer runs first.** Randall directed that the forward-scorecard rescoring lane (`Forward Scorecard Rescoring Lane - 2026-09-17.md`) be built ahead of Phase 4. Reason: the target shape below requires a decision card proving a candidate is worth promoting, but no outcome measure exists against which "worth promoting" can be defined — the 415 durable recommendation rows have never been forward-scored, and the scoring path was structurally incapable of running. Promotion plumbing built before that measure exists has nothing to optimise against. Both lanes stay blocked until G9 closes. Open item 3 of that lane asks whether scored outcomes eventually become Phase 4 promotion criteria.

## Decision

**Do not build tier promotion/demotion during Phase 3.** After G9, implement it as *propose → decision card → owner approval → one gated canon rebuild*. The OS proposes; Randall decides; guarded SQL is rebuilt under an explicit `--approval-reference`. This preserves the read/write split that is currently doing real work, and it matches the contract's authority separation: the authorization check and the membership write stay separate proof steps that cannot infer each other.

## Why not during Phase 3

Two blocking reasons, both concrete:

1. **G8 measures scope stability.** G8 observes five trading sessions plus a closed-market session against the dynamic entitlement scope. Any tier change alters that scope's membership and fingerprint mid-window. A promotion during G8 does not just add noise — it invalidates the observation the gate exists to produce.
2. **The retired router carries pivot-incompatible semantics.** The dormant predicate is fed by WF78-era routing and freshness artifacts that predate the 2026-08-29 alerts-OS pivot and still carry deployment/production-scope meaning. Under the contract's rename-semantics test, surviving capital/deployment/position/sizing/order/execution meaning fails retirement. Reviving that feed without clearing the pivot validator would import exactly what the pivot removed.

## Current verified mechanism (checked live 2026-09-07)

### Chain of custody

`data/finance/universe-v1.json` (`tier` field, 300 entries, last written 2026-08-29 19:00)
→ `scripts/finance_sql_canon.py` derives `sql_tier`, `coverage_obligation_tier`, `tier_decision_scope`
→ `state/finance/finance-canon.sqlite` `universe_membership`
→ alerts OS reads only, via `scripts/finance_sql_canon_access.py`

`universe-v1.json` is the tier source of truth. The rebuild is the only writer. There is no incremental tier-change path.

### Live state

| Field | Observed | Meaning |
|---|---|---|
| `tier` (active) | A=15, B=17, C=268 | Matches the contract's admission caps |
| `decision_grade_eligible` | A/B=1, C=0 | Consistent with the tier split |
| `sql_tier_state` | `sql_first_wait_for_routing` for all 300 | Placeholder; no state machine exists |
| `production_scope_member` | 0 for all 300 | The predicate cleared nobody at last rebuild |
| `production_scope_source` | NULL for all 300 | No reason string retained |
| `promotion_required_before_action` | 1 for all 300, including Tier A | Gate is uniformly on; it does not discriminate |

### Four named gaps

1. **`sql_tier_state` is a hardcoded literal.** `scripts/finance_sql_canon.py:550` assigns `"sql_first_wait_for_routing"` unconditionally to every row. The value literally names a router that is retired. No row has ever held any other state.
2. **The code still names a retired router as tier authority.** `finance_sql_canon.py:37` defines `AUTO_ROUTER_PATH = TMP / "wf78-auto-tier-routing.json"` with the surviving comment "Routing auto_tier is the single tier authority." `skills/veritas-wf78-tier-promotion-spine/SKILL.md` is a tombstone with no active routing or tier-promotion authority. Both artifacts still exist on disk — `tmp/wf78-auto-tier-routing.json` (2026-08-29 14:43) and `tmp/wf78-tier-weighted-freshness-resolution.json` (2026-08-29 20:18) — frozen at the pivot date. They are stale inputs, not a live feed. This is a duplicate-truth-surface condition under the contract's single-owner policy.
3. **`production_scope_member` is 0 for all 300.** The dormant predicate `resolve_production_scope` (`finance_sql_canon.py:469-492`, terminal reason `proof_joined_routing_tier_ab_fresh_confident_card_coverage`) requires routing tier A/B, `resolution_state=fresh`, zero blocking card gaps, zero critical data conflicts, ready confidence, coverage-registry membership, and an on-disk card. It fails closed when its proof artifacts are unavailable. It survives intact and is fed by nothing current.
4. **`promotion_required_before_action = 1` even for Tier A.** The flag carries no tier-specific meaning today, so it cannot express "this name has already cleared promotion."

The useful finding: the *decision logic* survives and is fail-closed by construction. What is missing is a current evidence feed and an approval path — not the predicate.

## Target shape (post-G9, requires its own owner decision)

1. **Propose.** A deterministic weekly job resolves one guarded-SQL scope snapshot, evaluates the existing predicate against *current* alerts-OS evidence owners (not the frozen WF78 artifacts), and emits promotion/demotion candidates with per-candidate reasons. Read-only. No SQL write, no provider expansion beyond the standing policy.
2. **Decision card.** Candidates render as one card per ticker carrying the contract's required promotion proof: resolved identity against corporate actions, prior effective tier and version, thesis and official-source lineage, every required evidence class inside its recency limit, destination-tier capacity headroom, duplicate-surface census, and rollback plan. A free-text `not_applicable` cannot satisfy a proof.
3. **Owner approval.** Randall accepts, rejects, or defers per candidate. Absent approval, the prior effective tier stays authoritative — that is already the contract's rule, and the current architecture enforces it by having no incremental writer at all.
4. **Gated rebuild.** One `python scripts/finance_sql_canon.py --write --validate --approval-reference <ref>` applies the approved set. The existing rebuild already backs up `universe-v1.json`, both SQLite databases, and their WAL/SHM files before writing, and reports under `finance_sql_canon_promotion.v1`.

### What this shape does and does not satisfy

Satisfied by construction: single guarded-SQL writer; prior tier authoritative until commit; consumers derive scope after commit rather than holding independent lists; no half-promoted ticker observable as effective (a rebuild is all-or-nothing).

**Not** satisfied and still to design: per-ticker exclusive lease, expected-prior-version check, the `promotion_pending_coverage` intermediate state, next-session timeout with expiry reasons, crash-recovery reversal, and the demotion-specific rules (sustained impairment required; system-caused staleness cannot demote; no beneficiary of vacated capacity as sole evidence source). A whole-canon rebuild is a coarser instrument than the contract's per-ticker transaction, and that difference is the main open design question.

## Alignment check performed

- `Tier Entitlement and Atomic Promotion Review Contract.md` — **consistent.** This note implements its deferred item 4 and adds no policy. Its `promotion_candidate → promotion_pending_coverage → tier_effective | promotion_blocked | promotion_expired` machine is preserved as the target, with the gap above stated honestly rather than declared met.
- `state/dynamic-entitlement-provider-policy.json` — **consistent.** `authority_boundary.guarded_sql_tier_or_membership_writes_allowed: false` remains true and unchallenged. Nothing here proposes changing the standing provider policy, its component/provider allowlists, its envelope, or its 400-call daily budget.
- `Phase 3 Main-Only End-to-End Acceptance - 2026-09-05.md` — **consistent.** G6-G9 remain open and unaffected. This note explicitly defers all work past G9 and adds no gate.
- `skills/veritas-wf78-tier-promotion-spine/SKILL.md` — **consistent.** The tombstone stays retired. Nothing here revives WF78 production, deployment, paper, or execution routes. The two frozen `tmp/wf78-*` artifacts are cited as evidence of a stale feed, not proposed as inputs.
- Finance "Phase 4" namespace — **clean.** No other workspace document claims it. The AGI Readiness Phase 4 is a separate program and is not touched.

## Stop lines

No tier change, no canon write, no schedule change, no cron install, no provider-policy change, no external delivery, and no capital, order, brokerage, account, paper, or live execution authority arises from this document. Archive or deletion of the stale WF78 artifacts requires separate explicit approval and is not proposed here.

## Open items for Randall (not blocking, decide at Phase 4 activation)

1. Whether a whole-canon rebuild is acceptable as the apply mechanism, or Phase 4 must build the per-ticker transactional writer the contract describes.
2. Whether the stale `tmp/wf78-*` artifacts should be retired at Phase 4 start, so the predicate cannot silently read pivot-era evidence.
3. Cadence for the proposal job. Weekly aligns with the contract's Tier A coverage measurement and its five-market-day P3 status bound.

## Addendum 2026-09-16: fifth named gap — promotion does not require a reference-level refresh

Added by Main after a live check on 2026-09-16. This is a design gap, not a live defect: it is unreachable today because nothing has ever been promoted.

**The gap.** The alerts OS compares live quotes against a frozen baseline of three numbers per ticker. `reference_levels` holds 200 rows — 32 in the evaluated scope and 168 tier-C bench rows — and all 1000 lineage cells (200 tickers x 5 fields) carry one identical `source_generated_at_utc` of `2026-09-10T23:34:45.835735Z`. Freshness policy is `max_level_age_days = 14.0`.

A tier-C name promoted into the evaluated scope therefore arrives carrying bench-age levels. If its baseline is already past the age limit at promotion, the controller emits `freshness_decay` for it immediately; if it is close to the limit, the name enters the scope with only the remainder of the window. Either way the promotion produces a ticker that cannot alert correctly.

**Why the target shape does not already cover it.** Step 2 requires "every required evidence class inside its recency limit," but the alert reference baseline is not enumerated as an evidence class anywhere in this record. It is a separate content-addressed artifact (`state/finance/baselines/alert-reference-levels-v1-<sha256>.json`) pinned in `finance_state_meta` under `alerts_os_reference_baseline_v1`, governed by its own owner-gated apply path rather than by the evidence registry.

**Recommended resolution, for decision at Phase 4 activation.** Make a fresh reference level a required promotion proof, so the decision card cannot render a candidate whose baseline age at the intended commit date exceeds the policy limit. The coarse alternative — rebuilding the whole baseline on every promotion — is worse, because the pin is deliberately immutable and single-stamped, and a promotion should not be able to move the yardstick for the 32 names already being evaluated.

**Interaction with the existing decision.** This reinforces, rather than changes, the decision not to build promotion during Phase 3. A promotion inside G8 would not only alter the observed scope fingerprint, it could inject a name that is stale on arrival.

**Open item 4 for Randall (not blocking):** whether a fresh reference level becomes a required promotion proof, or promotion is permitted with a recorded stale-baseline exception.

## Addendum 2026-09-16: routing note

This record already documented, on 2026-09-07, that `sql_tier_state` is a hardcoded literal, that `production_scope_member` is 0 for all 300 rows, and that the tier authority named in code is a retired router. On 2026-09-16 Main re-derived those same facts from live canon and reported them to Randall as new findings, because nothing routes an operator question about evaluation scope to this document. Reading `universe_membership.tier` alone yields the wrong conclusion that tier A/B/C is the settled design.

For the avoidance of doubt: `current_sql_canon_routing` selects `u.tier AS legacy_tier`, `tier_routing_state` holds 0 rows, and the feeder that would populate it (`Finance - Daily SQL Canon Tier Routing Sync`, `scripts/sql_canon_tier_routing_refresh.py`) was retired on 2026-08-29 with `rollback_requires_owner_gate: true`. Tier A/B/C is the legacy fallback still doing real work because its replacement is unbuilt, and this document owns that replacement.

## Addendum 2026-09-23: per-name onboarding readiness (owner direction)

Randall, Telegram 2026-09-23: the 32 names must not be static; as Tier A rotates under the Phase 4 dynamic router, every new name must arrive with the same readiness work completed.

**Principle: readiness is a per-name contract, not a per-list project.** A router promotion may only activate a name whose readiness record passes; otherwise the name stays monitor-only (alerts on invalidation/data quality, never a recommendation) and a readiness task is queued.

**Per-name readiness gate (all required before recommendation eligibility):**
1. Accepted structured thesis, `state/finance/thesis/<T>.json`, `status: accepted`, inside `review_due`.
2. Fresh band from the current methodology (`mech-v3-floor-atr20` or later) with non-null `reference_confidence`, invalidation below band low, width >= 1×ATR20.
3. 252 clean or repaired daily bars; at most 2 repaired bars (nightly gap repair covers any name in the live controller scope automatically).
4. Earnings date and macro-regime context present.
5. Sector ETF benchmark assigned (for relative strength and ledger scoring).
6. Ledger `state_snapshot` written on first evaluation so its first transition has a prior.

**Static assumptions that must be removed before the router goes live (found 2026-09-23):**
- `scripts/yahoo_reference_level_matrix.py` hard-codes `SCOPED_TICKERS` (the 32) and rejects any other scope.
- `scripts/g6_yahoo32_sql_apply.py` enforces `EXPECTED_TRIPLE_COUNT = 32`, so a batch cannot add or remove a name.
- Both must read scope from the guarded-SQL dynamic entitlement (the same source the recurring chain uses) and support per-ticker apply, consistent with recommendation P4-2 (per-ticker transactional writer).

**Already dynamic:** the recurring chain and controller (dynamic entitlement scope), the nightly gap repair (reads the promoted controller), the alert-event ledger (keys on ticker; new names get a `state_snapshot`).

**Thesis supply for rotation:** a promotion candidate triggers a thesis draft task automatically; Randall's acceptance is the gate. Until accepted, promotion can proceed for monitoring but not for recommendations.
