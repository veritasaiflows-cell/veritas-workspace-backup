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

## Addendum 2026-09-26: post-G9 profitability and code audit — plan of attack

Randall requested a Sol audit of recommendation economics and a Muse Spark read-only code audit of Phase 4 and its prerequisites. Main reconciled the reports against the current owner records, guarded SQL, current generated artifacts and selected source lines. **Phase 4 remains design-only.** This addendum prioritizes review-only preparation and testable implementation slices; it does not approve a tier transaction, canon write, recurring job, external product, or trading action. “Maximum profitability” is an objective for *measured recommendation quality*, not a promised return or permission to maintain portfolio state. The 2026-09-23 monetization audit is a dated snapshot, not today's status.

### Current checkpoint and immediate trust gap

- G9 closed on 2026-09-23 with recorded exceptions (`Phase 3 Main-Only End-to-End Acceptance`, G9 addendum; reconciliation register). The prior “both lanes blocked until G9” condition is therefore cleared; their own design, validation and authority gates remain.
- Five Tier A theses (CME, ITA, LIN, META, PH) are accepted; the 2026-09-26 08:00 thesis review counts **27 of 32 missing**. The 08:00 `tmp/recommendation-funnel.json` has 3 review candidates (CME, ITA, LIN), 2 board-only and 27 monitor-only. Its weights are `owner_approved_uncalibrated`; a rank is not an expected-return estimate, fired alert, delivered recommendation, or order.
- The weekly renewal applied at 09:00 on 2026-09-26 (`tmp/weekly-band-renewal.json`, apply and freshness guard both rc 0); the older **08:00 funnel is now version-stale**. CME illustrates the material difference: that funnel used 263.915–269.4602 / invalidation 255.5971, while current read-only SQL `reference_levels` returned 258.87–267.8765 / invalidation 249.9238 (source generated 2026-09-26T16:00:07Z). CME's thesis narrative also describes the prior proposed 255.60 invalidation. Do not present its morning rank or thesis number as a current recommendation or let narrative overwrite SQL. Recompute and reconcile after a renewal before a material review; no unscheduled band/canon apply is implied.
- The live alert-event hash chain verified **110 records through 2026-09-25** (one genesis and 109 events, head seq 110). The events do not themselves prove forward returns or delivery; the current accuracy events have `delivered: false`. The retired legacy 415-row outcome ledger still has pending forward checkpoints, and semantic outcome grades are not price-return evidence. The 2026-10-15 one-shot `finance-alert-ledger-scorer-readiness-check.json` is a *sample-maturity/design wake*, not a scorer or permission to build one early. Respect its recorded owner decision unless separately reopened.
- The previous digest suppression and timestamp-based dedup defects were repaired; the 2026-09-23 audit's “no ledger, no ranking, no structured thesis, NULL confidence everywhere” descriptions are no longer current. Do not re-open these as blanket defects. Missing coverage, score calibration, point-in-time call provenance and the dynamic tier writer **are** current gaps.

### Attack sequence and release criteria

| Order | Bounded lane | Exit proof before promoting the next claim |
|---|---|---|
| **0 — make current reviews trustworthy** | Rebuild the *read-only* funnel after any approved band renewal, joining one SQL baseline pin, controller quote/session, thesis version and macro/earnings evidence. Label an older funnel stale and block a current recommendation from using it; reconcile stale thesis narrative against SQL for review without silently rewriting Randall's accepted thesis. Separate `review_candidate`, alert transition and delivery in the user-facing surface. | Replay a 09-26-style 08:00-funnel/09:00-renewal fixture: stale rank is rejected, new rank has the renewed levels, and a sampled call points to exact input versions. Alert invalidations remain visible even when eligibility fails. |
| **1 — preserve an honest, scoreable call record** | Extend the existing alert-ledger design with a point-in-time *recommendation decision* record (including candidate and excluded-name reasons, methodology/rank version, prices, input hashes and whether anything was sent), plus a verifiable delivery receipt. Keep unsent events and data-quality transitions distinct from delivered calls; no rewriting or synthetic historical sends. Then scope an append-only forward scorer against future Yahoo closes, SPY and a benchmark assigned **before** the signal. Keep retired WF55 capital/paper feeders out of the new path. | Hash-chain and receipt reconciliation pass; sampled calls reconstruct what was known and delivered. The scorer design states the 5/21/63 **trading-day** observation convention, corporate actions, maximum observation lag, invalidation/adverse excursion and named `unscoreable` reasons; a due-but-empty run is non-green. Before enough mature observations, report sample size and uncertainty, **not** profitability, win rate or tuned weights. The 10-15 readiness/approval gate is unchanged. |
| **2 — complete intelligence coverage before scale** | Draft source-backed theses for the remaining 27 evaluated names for Randall's acceptance, with review-due and invalidation rationale; verify the live band, confidence, earnings, macro and sector benchmark on each name. Preserve monitor-only while any gate fails. Compare transparent ranking against a preregistered baseline and negative controls (e.g. random/sector ranking) on *out-of-sample* resolved calls before changing the owner-approved but uncalibrated weights or band geometry. | 32/32 accepted and in-date theses for recommendation eligibility, with fail-closed tests for missing/stale input; ranking calibration shows sample, uncertainty, benchmark excess return and downside rather than an in-sample success claim. Monitoring can remain broader than recommendation eligibility. |
| **3 — implement Phase 4 as evidence-gated movement** | First make the retired WF78 tier-DB apply route non-operational or explicitly fenced, then choose a transactional apply design with a validated approval reference, per-name prior-version check, exclusive lease, pending-coverage expiry, rollback and demotion rules. Build a *proposal* and decision card from current alert-OS evidence and outcome-readiness proof; owner approval is required for each effective tier change. Replace the two static-32 band-generator/apply assumptions with a scope derived from the same guarded entitlement, including per-name onboarding and first ledger snapshot. | Tests prove stale, duplicate, conflicted, partially failed, expired, unready and system-caused-staleness candidates cannot become recommendation-eligible; no half-promoted name or retired-router evidence reaches current consumers; guarded SQL and provenance match after rollback/crash recovery. A fresh accepted thesis, valid current band/invalidation, 252 daily bars within repair budget, earnings/regime, sector benchmark and ledger snapshot are checked per name. A name may be monitor-only pending Randall's thesis acceptance. No tier apply occurs merely because these tests pass. |
| **4 — assess a separate impersonal product** | Only after sufficient contemporaneous resolved history, assess data-license rights, securities-counsel/regulatory posture, a distinct non-personalized output contract and external-delivery approval. | No public performance or revenue claim from mechanical bands, incomplete cohorts or private user preferences; launch remains a separate owner decision. |

### Code-audit containment (static findings, not executed failures)

Muse Spark performed a **read-only source review**, not a test run. Main verified the first two bounded observations below; other findings require focused reproduction and an independent QA pass before severity or remediation is accepted:

1. **Standing 5% renewal gate precision:** `scripts/weekly_band_renewal.py:evaluate_gate` rounds each percentage to four decimals *before* comparing with the owner-approved `MAX_EDGE_MOVE = 0.05`. A move narrowly over 5% can round down and pass. Preserve the approved 5% limit; test the unrounded comparison at the boundary and display rounded values separately. Today's largest reported move was ~3.46%, apply rc 0 and freshness guard rc 0; **there is no evidence today's renewal crossed the gate**. Keep this as a separate narrow safety fix, not a change to approval policy.
2. **Retired writer hazard:** `scripts/sql_canon_tier_routing_refresh.py` still exposes `--apply-db` using retired WF78 routing evidence, whereas `finance_sql_canon_access.py` requires that retired routing state be absent. Do not execute it for proof; first design a deny-only/regression test and check current command references. This is not the Phase 4 writer.
3. **Further audit leads to reproduce:** `finance_sql_canon.py` rebuild/backup/approval atomicity; recurring chain receipt/promotion failure isolation; digest status-coherence across send paths; renewal post-guard status and durable audit overwrite on repeat. These observations do **not** overturn the already accepted Phase 3 run proof without a reproducer. Prioritize the approval/rollback and receipt guarantees before any Phase 4 apply design; keep test artifacts away from live canon and scheduled jobs.

### Decision and boundary register

- **Existing decisions preserved:** forward scoring ahead of tier promotion; weekly band-renewal Option B's exact 5% stop; owner-approved funnel weights remain *uncalibrated*; the 2026-10-15 scorer design-readiness wake; per-thesis acceptance by Randall; Yahoo-only personal source; no external/customer delivery.
- **Needed for eventual activation, not for this plan:** Randall chooses whole-canon rebuild versus per-name transaction after the failure/rollback prototype (per-name transaction is recommended for traceable changes); accepts or rejects each thesis and each tier move; approves any scorer build or earlier change to the October timing; separately decides commercial data rights, product format and legal review.
- **Hard boundary:** no sleeve, holding, position, allocation, weight, sizing, tranche, cash, rebalance or simulated account state; no capital, order, account, brokerage, money movement, paper/live execution, external delivery or inferred authority. This addendum cannot activate SQL writes, cron/config changes or a product launch.

## Implementation checkpoint 2026-09-26 (owner approved workflow work at 10:33 Phoenix)

Randall approved continuing the Phase 4/alerts workflow upgrade and testing bounded isolated agents, **not** an individual effective-tier transaction, trade, public delivery or a relaxation of proof gates. Start with the renewal safety and same-version funnel slices before the tier writer. `FINANCE-PHASE4-20260926::renewal-gate` leases only `scripts/weekly_band_renewal.py` and its focused test; no source edit has been accepted under that lease yet.

**Reproduced, not fixed:** `evaluate_gate` reports a raw 5.004% move as rounded 5.00% and passes the standing 5% gate. Main ran the existing six focused tests (6 pass); none covers 5% plus a small positive epsilon. This is a prospective fail-open edge, not evidence of a 09-26 over-limit apply. The exact fix contract is compare the unrounded fraction to the existing `MAX_EDGE_MOVE = 0.05`, round only presentation, add 5.000% pass / 5.004% block regression cases, and rerun the focused suite plus an independent safety QA pass. Do not move the owner-approved limit.

**Isolated builder test:** a two-file 15,331-byte worktree handoff was staged for `implementation-builder` with a clean committed baseline and three exact allowed paths (the two sources and `canary-receipt.txt`). In a sandboxed Muse Spark run, the agent read the manifest and source, computed the source SHA-256, wrote and read back only the receipt. Main verified the receipt and unchanged source SHA-256 independently; Docker is reachable and the scoped host bind exists. This proves *only this scoped file-tool canary*. `project_implementation_router.py` still rejects implementation dispatch: its v2/v3 contract requires a separate full attachment/runtime-probe, negative-control, changed-path and close-proof bundle. The current canary has none of those; `scoped_writeback_preflight.py` has been returned to **blocked** (the partial evidence file is not dispatch authority). Do not assert full transport readiness, write production source, substitute Main as code author, or weaken the router to clear the failure. Correction after Randall's 11:18 clarification: the approved builder was already exercised in the live `builder-v1` suite (35 graded attempts, 19/20 first-pass cases, zero invalid transport in `data/evals/builder-v1/baseline-v2-summary.json`). Do not run another coder-qualification test or negative-control canary under this task. The implementation router still rejects this specific dispatch because the existing eval record is not its required v2/v3 transport-proof bundle; the scoped canary must not be relabeled as that proof. Read-only reconciliation at 11:22 Phoenix: `data/evals/builder-v1/baseline-v2-summary.json` has 35/35 graded attempts, 0 invalid transports, 19/20 first-pass cases, 0 hard fails, and explicitly says the 20 cases are reconstructions, not replays. The repository search found no `veritas.persistent_transport_proof.v3` artifact or v2 runtime probe to satisfy `project_implementation_router.py`; its scoped-writeback gate requires actual attachment, negative-control, changed-path and close-proof evidence, not just a model evaluation score. This is an evidence-contract mismatch, **not** permission to edit the eval or partial-canary JSON to say the missing checks passed. No additional coder-qualification test is authorized. Keep dispatch blocked rather than bypass the gate; continue only safe non-dispatch Phase 4 work until the evidence requirement has a legitimate satisfied route. Normal focused regression testing belongs to an implementation only after lawful dispatch.

**Unchanged follow-on order:** after that gate, fix and test the renewal threshold, then same-version funnel freshness/delivery provenance, then thesis coverage and scorer-readiness work, then design/test the guarded transactional tier mechanism; actual tier moves remain per-candidate owner decisions. No cron, canon, config, account or external surface changed in this checkpoint.

### Narrow dispatch-safeguard verification, 11:30 Phoenix (failed; no implementation)

Randall explicitly authorized a single narrow verification, **not** another builder benchmark. The coder read a host-staged read-only attachment with matching SHA-256; writes to the attachment, `/role`, and `.git` were denied by its tools. But it also **successfully created** `out-of-scope-denied.txt` inside the staged `/worktree`, outside the manifest's three allowed paths; Main independently verified its existence, hash, and that both staged source files are unchanged. A connection to `127.0.0.1:1` was refused, which does *not* prove network denial. Manifest/sentinel write protection was not exercised, so it remains unproven by this run. Exact failed proof: `tmp/implementation-builder-scoped-worktree/phase4-transport-verification-20260926.json`.

This does not expose the real workspace: the worktree manager's `close_worktree` rejects any changed path outside the manifest before producing a patch. It **does** mean the router's required stronger `out_of_scope_write_blocked` claim cannot truthfully be made for this run. No close, accepted patch, code integration, config change or financial action occurred. Preserve the out-of-scope probe as incident evidence until an owner-approved cleanup; do not repeat a probe or relabel the proof as pass. The next engineering decision is whether to enforce the path allowlist at write time or redesign the dispatch contract around *proven fail-closed close-time rejection*, with explicit owner review of the different threat boundary; neither choice is implied by this authorization.

### Security tightening and narrow fix accepted, 11:37–12:00 Phoenix

Randall separately authorized the write-time boundary repair and continuing Phase 4. Main backed up `~/.openclaw/openclaw.json` to `~/.openclaw/openclaw.json.pre-phase4-builder-boundary-20260926`, changed the *one* builder `/worktree` bind from `rw` to `ro`, and validated the config. This deliberately **disables scoped worktree implementation**; the available route is the router-supported `patch_draft` contract, with only ephemeral sandbox scratch writes and a diff returned in the reply. The existing failed v2/v3 scoped-writeback proof remains failed; it was not relabeled or bypassed. A fresh builder session confirmed that out-of-scope `/worktree` creation and protected-control append-open are denied; Main independently inspected its Docker container: `network=none`, `/worktree` and `/attachments` read-only, only `/workspace` writable to an isolated sandbox directory, not Main's workspace. `tmp/implementation-builder-scoped-worktree/phase4-patch-draft-transport-proof.json` is a **v1 attachment-only proof** and passed the router's `patch_draft` check. The scoped-writeback preflight correctly remains blocked for v1.

**Operational incident:** the documented `openclaw sandbox recreate --agent implementation-builder --force` selected **53 historical builder session containers**, wider than the single current container expected. The process was interrupted after reporting 15 removals; Main did not retry. A *new* session was used for the verified read-only mount. Do not claim the older remaining containers were recreated or use them for code dispatch. Host-staged source and failed-probe evidence were preserved. This is cleanup debt, not permission to sweep all old runtimes.

**Accepted narrow code slice:** Muse Spark read the frozen two-file handoff (preimage SHA-256 `0b2502ac…` and `32df1a2f…`), edited only its sandbox scratch copy and returned a two-file unified diff. Main verified preimages, applied that exact fix to `scripts/weekly_band_renewal.py` and `scripts/test_weekly_band_renewal.py`, and verified the postimages (`81ef9244…`, `f07960db…`). `evaluate_gate` now compares the **unrounded** fractional move to the unchanged 5% limit, retaining four-decimal rounding only for display; the regression covers exactly 5.000% allowed and 5.004% blocked. Host focused `pytest`: **7 passed**; `git diff --check`: pass. Independent read-only QA examined a host-staged snapshot of the *actual applied files* and reported READY with nonblocking findings (pre-existing zero/missing old-edge skip, no negative-boundary test, conservative float equality, upstream freshness dependency); its terminal session later showed a runtime-plugin-generation failure, so retain that attribution caveat. Main's narrow acceptance proof: `tmp/phase4-renewal-applied-diff-acceptance-20260926.json`. No finance canon, tier, schedule, account, capital or order change.

**Next gate remains stale rankings:** the live 08:00 funnel was generated before the 09:00 renewal and uses pre-renewal CME levels; it is not a current recommendation. A standalone post-renewal controller preview (`tmp/phase4-alert-controller-postrenewal-20260926.json`) returned `ok` but only the **legacy 18-name scope**, omitting CME; it was not promoted over the live 32-name controller. Use the exact dynamic-entitlement chain and same-version SQL/controller/funnel provenance before refreshing or presenting candidates. Then implement durable stale-consumer rejection and reviewed/sent/not-sent records before outcome scoring and any Phase 4 tier transaction.

### Fail-closed stale ranking guard integrated, 12:20 Phoenix

Separate scoped patch-draft lease `FINANCE-PHASE4-FUNNEL-20260926` covered only `scripts/recommendation_funnel.py`, its tests, `scripts/veritas_mcp_server.py`, and its tests. Main staged exact file hashes for the isolated builder, rejected the first draft's missing-packet/naive-time fail-open, required a corrected draft and strict whitespace repair, then verified the four final bytes and applied the exact four-path diff. `git apply --check --whitespace=error` and post-apply `git diff --check` passed; Main host pytest on the two changed test files: **31 passed**, and the neighboring weekly chain, thesis review and renewal files: **19 passed**. Quarantined source and final patch: `tmp/phase4-funnel-builder-final-20260926/` (patch SHA-256 `1a96ce8c…`). Independent actual-applied-diff QA was requested with its own staged snapshot at `~/.openclaw/workspaces/qa-redteam/review/phase4-funnel-20260926/`; do not mark that QA accepted until the verdict is reviewed.

The producer now suppresses recommendation candidates before any market ranking fetch when an **applied** renewal finishes after the controller, or required controller/renewal timestamps are absent, unreadable, or timezone-naive. The read-side checks both controller and funnel against the applied renewal and suppresses ranked names. Legitimate non-applied renewal does not imply new band data. This is a **timestamp freshness guard, not SQL same-version proof**: a later controller generated from stale SQL inputs could still pass the comparison. A bounded runtime proof with a throwing market-data stub suppressed all names from the real **32-name** scope without calling market fetch. Main backed up the old three-candidate funnel as `tmp/phase4-funnel-pre-stale-guard-20260926.json`, ran the deterministic producer `--write` path, and validated `tmp/recommendation-funnel.json` reports `status=stale_suppressed`, 32-name scope, and **zero** candidates/names. No recommendation was sent. The live `veritas-data` tool reads the empty packet but currently omits the new `status`/reason because its long-running server has not loaded the revised code; a fresh host import of that source does return `stale_suppressed`. No service restart was attempted. The next positive ranking still requires the governed **32-name dynamic-entitlement refresh** and independent SQL/controller/funnel version proof; do not substitute the legacy 18-name standalone controller preview.

**Refresh timing guard:** `scripts/main_session_greenkeeper_controller.py` documents the exact 32-name dynamic-entitlement chain flags and makes its midday refresh **slot-bound to a weekday 11:00–12:00 Phoenix window**; it skips weekends and off-slot runs after an earlier shared-artifact overwrite incident. Since this is Saturday, do not manually run that production chain to clear the stale status. Observe the next scheduled trading-day run and verify the resulting scope, quote/session freshness, SQL guard provenance and funnel version *before* presenting any candidate. A controller with a newer timestamp alone does not prove those conditions.

**Final QA close, 12:29 Phoenix:** independent review of the actual applied four-file snapshot reported READY but found four initially nonblocking signal-loss/malformed-input cases that Main treated as acceptance blockers. The same leased builder corrected all four in a 133-line incremental patch: only explicit `applied=True/status=applied` counts as applied; only explicit `applied=False/status=needs_owner_review` or `gate_passed_not_applied` can bypass a new-band check; malformed/inconsistent/failed renewal state suppresses. The MCP reader preserves the funnel artifact's own `stale_suppressed` status even if a controller is refreshed later, and the producer guards a non-dict controller before dereferencing rows. Strict `git apply` and `git diff --check` passed; Main host ran **56 tests passed** across the two changed files and three adjacent workflow suites. Independent QA inspected the final applied four-file diff and explicitly verified all four cases closed with no new fail-open or authority expansion. Main's narrow acceptance proof: `tmp/phase4-funnel-applied-diff-acceptance-20260926.json`; final source SHA-256s begin `fe37f0bd`, `67aef600`, `c3ffe6a3`, `dcb638cf`. Both Phase 4 implementation leases are closed with active lease admission `ok`; the lane register's single pre-existing historical validation error remains, so do not report the whole register green. The live packet still suppresses all candidates, while the already-running MCP process still omits the reason until an owner-gated runtime reload. Do not infer Phase 4 completion, same-version canon proof, or positive recommendation readiness from this closeout.

### 2026-09-26 13:18 Phoenix: four-slice builder transport incident (no Main implementation)

Randall authorized all four audit repairs with `implementation-builder` and `anthropic/claude-opus-5-5` as independent QA, **not** any live tier/canon apply, external delivery, service change, or policy bypass. Main verified the configured QA model and patch-draft attachment transport, leased exact non-overlapping code paths, and froze bounded read-only handoffs. The builder's actual factory role and `patch-draft-bounded-linux` skill, however, permit edits and synchronous proof **only under `/worktree`**. Main's handoffs instead requested scratch writes under `/tmp` or `/workspace` and prohibited `/worktree`; the current `/worktree` bind is read-only, and `scoped_writeback_preflight.py` reports blocked capability, fingerprint and writable-bind checks. This is a real authority/transport conflict, not a failed financial test.

One prototype worker stopped before editing. The other three reported making draft-only sandbox-scratch edits outside the role-approved root before Main's stop signal. **Reject those drafts as invalid transport evidence; do not copy, apply, QA-sign, or re-label them as a compliant worktree result.** Main checked seven frozen Main source hashes unchanged, six proposed new Main source files absent, and no canon, tier or production-ledger apply requested. No Opus QA run was started because there is no eligible applied diff. All four implementation lanes were marked blocked; active lease admission returned `ok` with 0 active lanes, while the unrelated historic register validation error remains. Proof: `tmp/phase4-builder-write-surface-incident-20260926.json`. A lawful resume requires a genuinely policy-compliant builder worktree and fresh frozen inputs; do not change permissions, bypass the scoped-writeback gate, fall back to Main-authored implementation, or activate any tier/canon action merely to clear this incident. The live recommendation funnel remains `stale_suppressed` pending the normal 32-name same-version refresh.

### 2026-09-26 14:05 Phoenix: exact-file bind canary passed its boundary, failed both code-edit tools

Under Randall's 13:54 instruction to fix the route, Main preserved the old occupied scoped-worktree plus sentinel **intact** in `~/.openclaw/workspaces/implementation-builder/handoff/retained/finance-phase4-renewal-gate-20260926-1354/` with SHA inventory and rollback receipt; it did not delete the out-of-scope probe. The approved manager prepared and verified a fresh two-file canary worktree. A disposable offline Docker run and a real `implementation-builder` run proved the read-only parent with exact-file RW binds: direct write to the named file succeeded, attempts to create `frozen.txt` and `unlisted.txt` both failed, and the host found neither file. Docker inspect showed `/worktree` RO, the two named files RW, and manifest RO. **This is a partial boundary proof, not approval to dispatch code.**

The builder's normal `edit` tool failed when its atomic temporary file required creation in the RO parent; a separate `apply_patch` canary failed because its host-resolved path escaped the tool's sandbox root. The latter changed 0 files; Main confirmed the manifest and probe content remained unchanged. Consequently the factory role's first-class editing path is unusable under this file-level boundary, and a direct `exec` code-writing workaround conflicts with its proof-only exec rule and the leased edit procedure. No valid scoped-writeback v3 proof was produced; `scoped_writeback_preflight` still reports blocked capability/fingerprint/RW-source checks. The temporary two-file config append was restored by validated batch to the original 15 RO binds; workspaceAccess `none`, network `none`, and readOnlyRoot `true` remain unchanged. No Phase 4 source/canon/ledger/tier write and no Opus implementation QA occurred. Verdict: `tmp/implementation-builder-scoped-worktree/filebind-canary-verdict-20260926.json`; preservation receipt in the retained handoff. A route choice for read-only builder patch proposals versus holding for platform file-tool repair was requested but received **no answer**; do not infer a choice or reuse rejected scratch drafts.

### 2026-09-26 22:08 Phoenix: proposal-route foundation accepted; activation still blocked

Randall authorized the bounded proposal route and required GLM 5.3 QA. Main integrated three isolated implementation slices: same-version SQL/controller/funnel lineage checks, an append-only recommendation decision ledger, and deterministic readiness plus an in-memory tier-transaction prototype. After one bounded repair batch, host validation passed **179 tests** (39 funnel, 50 ledger, 49 readiness, 41 transaction) plus four disposable `py_compile` checks. Independent QA using exactly `ollama-cloud/glm-5.3:cloud` passed all final artifacts with no critical, high, or medium correctness/security finding. Main accepts these files only as inert foundations. Full decision, residuals, usage, and proof paths: `Phase 4 Proposal Route Acceptance - 2026-09-26.md`; machine receipt: `tmp/phase4-proposal-route-20260926/phase4-final-acceptance-20260926.json`.

Nothing was wired live: no canon or tier mutation, schedule/config/runtime/channel/credential change, external delivery, authenticated approval service, scorer, or execution authority. Both implementation lanes are terminal with technical/Main acceptance and activation blocked; the register records token/cache budget breaches and legacy v1 usage-binding limits, so their administrative status is blocked rather than complete. Active lanes are 0 and the pre-existing global register validation error remains. Resume from the acceptance note, not the earlier transport incident. The next owner decision, only after scorecard/readiness prerequisites, is whether to authorize a separate guarded per-name transactional writer lane; per-name is recommended over whole-canon rebuild.

### 2026-09-27 Phoenix: Tier A thesis drafts written (readiness-gate item, owner acceptance pending)

Randall approved drafting. Main wrote draft thesis records for the 10 Tier A names that had none: BRK.B, ETN, GOOG, GS, JPM, LMT, MSFT, NVDA, VRT, XOM (`state/finance/thesis/<T>.json`, `status: draft`, `owner_accepted_at: null`, v1). Evidence comes from official Q2 2026 releases (SEC exhibits, or the company newsroom where no exhibit was used), plus `tmp/fundamental-metrics-current.json` (09-26) and the earnings calendar. Each price invalidation cites the live guarded-SQL `reference_invalidation_level` with its 09-26 value and states that SQL governs after renewal. This keeps thesis text from disagreeing with SQL, which is the CME problem.

Proof:
- `thesis_record_validator.py`: 15/15 valid; drafts are not eligible.
- A sandbox copy with simulated acceptance gave eligible 15, `new_quarter` 0, `invalid` 0. The sandbox was deleted.
- Builder script: `tmp/phase4-thesis-drafts-20260927/build_tier_a_drafts.py`. It refuses to overwrite existing files.

Open issues surfaced, not fixed:
- The aggregator lags a quarter for ETN and GS (period 03-31).
- XOM's Q2 source is a trade-press summary because the 8-K fetch failed.
- The 5 accepted theses still cite pre-renewal "proposed" invalidation numbers.
- SQL labels META `BELOW_STOP` while the controller shows 751.26, above its band.
- The BRK.B aggregator P/B is 0.0.

Nothing grants eligibility or authority until Randall accepts each thesis.

### 2026-09-27 ~08:05–08:15 Phoenix: 9 accepted, XOM confirmed, band-repair v2s staged, META label diagnosed

**Acceptance.** Randall (WebChat ~08:05): "Accept all except XOM. Proceed with next steps." BRK.B, ETN, GOOG, GS, JPM, LMT, MSFT, NVDA and VRT were accepted in place at v1, following the 09-23 precedent (`owner_accepted_at` 2026-09-27T08:05:00-07:00). Pre-acceptance copies are in `tmp/phase4-thesis-drafts-20260927/pre-acceptance-drafts/`. The validator shows 14/15 Tier A eligible; XOM remains a draft.

**XOM.** The draft's Q2 figures now match the official 8-K exhibit 99.1. The company re-domiciled to Texas on 07-01 under ExxonMobil Holdings Corporation, which has a new SEC CIK (2115436); the ticker is unchanged. That move is why the old-CIK fetch found nothing, and SEC.gov direct fetch returns 403/ECONNRESET, so the copy came from the IR site. The fundamentals feed already uses the new CIK. XOM awaits re-acceptance.

**Band-repair v2s (staged, not applied).** CME, ITA, LIN, META and PH each have a version-bumped proposal in `tmp/phase4-thesis-drafts-20260927/v2-proposals/`.
- Each proposal points the price rule at live SQL (CME 249.92, ITA 205.72, LIN 443.66, META 515.67, PH 879.36 at the 09-26 renewal) and replaces the stale 09-22 proposed-band evidence.
- Thesis content is otherwise unchanged.
- All five validate as drafts and as simulated accepted records.
- The accepted v1/v2 records stay live and eligible until Randall accepts.
- Apply with `apply_v2_band_repair.py --accepted-at ... --quote ... <tickers>`. It copies the prior version into `history/` first.

**META "BELOW_STOP" diagnosis.** `reference_levels.reference_band_status` is not recomputed on renewal.
- The 09-26 numeric baseline carries no status field.
- The column holds `alert_state_observation` from the 2026-08-21 register row, which is embedded in `raw_json` with the old levels.
- Against 09-25 closes, 13 of 32 labels disagree with the current band, including 5 "BELOW_STOP" names that are in band: KTOS, META, NFLX, TMUS, VMC.
- `canonical_finance_data_plane.py` computes status from price and uses the column only as a fallback. Controller and funnel logic do not gate on it.
- Impact: misleading to direct SQL readers; no wrong computed alert state was found.
- Fixing it (null or recompute on renewal) is a canon write and needs an owner gate.

### 2026-09-27 ~08:17–08:30 Phoenix: XOM and v2s accepted, label fix built, static-32 removal prepared

Randall (WebChat ~08:17): "Proceed with all three recommendations, continue and prepare to remove the static 32-name list".

**Acceptances.** XOM was accepted in place at v1. CME v2, ITA v3, LIN v2, META v2 and PH v3 were applied with `apply_v2_band_repair.py`; prior versions are in `state/finance/thesis/history/`. All six have `owner_accepted_at` 2026-09-27T08:17:00-07:00. The validator reports 15 eligible and 0 errors, so all 15 Tier A names now have accepted theses.

**Stale-label fix (code only; no canon write today).**
- `scripts/g6_yahoo32_sql_apply.py` now sets `reference_band_status` to NULL for renewed rows only, in the same transaction as the triples.
- The dry run lists the labels it would clear.
- The rollback record keeps each prior label in `before_rows` and lists the cleared names. The byte-exact backup restores them.
- Post-apply verification checks that renewed rows are NULL and every other row is unchanged.
- The status column is not added to the numeric pin.
- Tests: `test_g6_yahoo32_sql_apply.py` 121/121 (10 new `status_*` checks); `test_weekly_band_renewal.py` 7/7; hermetic chain plus baseline guard 38/38.
- Router packet: `tmp/phase4-thesis-drafts-20260927/router.json`, status `planned`. The earlier `blocked` result came from the router defaulting to a persistent isolated-agent backend; it cleared with `--expected-execution-backend main`.
- Live effect: the next Option B renewal (Sat 10-03 09:00) clears 31 stale labels. ITA is already NULL. Read-only preview on a canon copy: `tmp/phase4-thesis-drafts-20260927/status-clear-live-preview.json`; the live canon hash was unchanged (`1208a615…`).
- An append-only amendment to `state/finance/standing-approvals/band-renewal-option-b.json` records this approval. Auto-apply conditions are unchanged.

**Static-32 removal: prepared, not executed.** Plan and inventory: `Phase 4 Static-32 Removal Plan - 2026-09-27.md`. The dynamic entitlement currently equals the hard-coded 32 (15 A + 17 B, 0 debt), so the change is behavior-neutral today. Owner decisions are listed there: D1 implementation route, D2 an Option B stop condition on scope change, D3 onboarding for names without a `reference_levels` row.

### 2026-09-27 late morning Phoenix: static-32 removal accepted and repaired; aggregator fixes (Claude, GitHub session)

Randall accepted the PHASE4-DYNAMIC-SCOPE-20260927 Muse Spark code as-is, waived further external QA, and kept implementation and QA with Claude in the GitHub session.

- **Static-32 removal accepted.** Claude fixed both HIGH findings. A non-regular prior audit record now stops the renewal instead of falling back. Every apply now needs a scoped, fingerprint-matched and live-verified matrix. The scope-change stop (D2) is enforced. Proof, tests and the offline canon-copy end-to-end: `Phase 4 Static-32 Removal Plan - 2026-09-27.md`, section "Acceptance and repair".
- **D3 blocked; owner decision.** `scripts/finance_sql_canon_access.py` guards exactly 200 reference, evidence and pin rows (new inventory row S7), so an onboarding insert fails the guard. The recommendation is to build D3 and the guard-contract change inside the P4-2 per-name writer lane. Until then, a promoted name without a row stays monitor-only.
- **Aggregator quarter lag (ETN, GS): cause found, fix in code.** `latest_comparable_pair` in `scripts/fundamental_metrics_refresh.py` fell back to the prior quarter whenever the year-ago column had two or more gaps, even if the newest quarter was fully reported. A synthetic statement reproduced the 03-31 result. A fully reported newest quarter now wins, and missing year-over-year values stay visible as `partial`. Confirming ETN/GS specifically needs the next refresh on the Windows host (no yfinance access in the cloud).
- **BRK.B P/B 0.0: fixed.** yfinance's `priceToBook` for BRK-B uses Class A book value per share, about 0.001. A non-negative provider P/B below 0.05 is now recorded as `price_to_book_provider_rejected`, and `price_to_book` is null, not 0.0. Negative P/B (negative equity) is kept.
- **Still open:** 13 stale band-status labels, which clear at the 10-03 renewal. XOM's thesis source note is superseded by the official 8-K confirmation.
- **Not done:** the P4-2 per-name tier writer. Its prerequisites (forward scorecard, the 2026-10-15 scorer-readiness gate) are unmet. Nothing was written to live canon, tiers, schedules, config or delivery.

### 2026-09-27 ~12:01-12:20 Phoenix: unified monitoring/scale-out plan (nothing executed)

Randall (WebChat ~12:01): "review attach and plan a fix to ensure we integrate this into phase 4. This has to be fully functional alert system that is unified and is able to monitor up to thousands of names." The attached Q&A (untrusted external content) was verified number-for-number against the live canon: 15 A / 17 B / 268 C; 168 carried-over Tier C band rows (59 still carrying stale 08-21 status labels), 100 without rows, 200 total; promotion-only band path; no promotion rule until the scorecard.

New owner artifact: `Phase 4 Unified Monitoring and Scale-Out Plan - 2026-09-27.md`. Three monitoring grades: decision-grade (evaluated scope only, feeds alerts), weekly screening bench-bands for all 300 (review-only, recomputed never persisted stale - the fix for the 168-row problem class), and a future universe-watch grade for thousands-name scale (batched snapshots; licensed/screener feed is the durable data answer). Stage 1 bundles the P4-2 per-name tier writer, D3 onboarding INSERT, and the 200-row guard contract change in one lane. Stage 2 needs one new standing permission (weekly screening refresh, ~268 extra Yahoo pulls/week). Owner decisions D-A through D-D pending. Nothing executed; no canon, tier, schedule, or config change.

### 2026-09-27 ~14:44 Phoenix: Tier B coverage complete (32/32); P4-2 writer lane dispatched

Randall accepted batch 3 (PLTR, RTX, SMCI, TMUS, VMC, WMB) and directed "Proceed with phase 4 remaining work." All 32 evaluated-scope names now have owner-accepted theses (validator 32/32 eligible, 0 errors) - the Tier B coverage milestone from the 12:09 reconciliation is complete.

P4-2 writer lane dispatched to Muse Spark (explicit model override): slice A = weekly read-only tier proposal job with Tier Entitlement decision cards per the adopted two-test policy; slice B = owner-gated onboarding INSERT writer plus the S7 guard scope-derived contract change (unapplied patch, drafted against HEAD 3d7721c5). Drafts only; Main verifies and applies. Stage 2 screening (D-A) remains an ungranted standing permission. Oct-15 scorer readiness assessment unchanged.

### 2026-09-27 ~17:12 Phoenix: P4-2 source landing accepted; activation blocked

Main recovered and integrated both r3 builder outputs, then required three bounded GPT-6 Sol actual-diff reviews. The first reviews found unsafe authorization, rollback, path-containment, recency and proof-overstatement behavior. Main applied one bounded repair, then narrowed the contract after the fresh review still rejected production-grade claims. Final QA passed the narrowed code landing with no Critical/High finding.

Accepted source behavior: the weekly proposal job is read-only/no-apply and emits honest missing/blocked proof slots; candidate bands are review-only/no-repair; S7 is now scope-derived (pin consistency, equal reference/evidence sets, full evaluated-scope coverage, universe containment); onboarding and tier transaction mechanics exist only as OS-temp hermetic test foundations. Both production apply and rollback CLIs fail closed with `exact_apply_authorization_not_implemented`.

Main verification: 125 focused checks, compile, shared validator bundle 9/9, live guard `ok`, live proposal smoke 15/17/268 with no demotion/swap, production mutation probes refused with the canon logical hash unchanged. No live canon, tier, band, schedule, config, runtime or delivery mutation occurred.

This closes the two implementation-draft slices, **not Phase 4 cutover**. Remaining cutover blockers are the contract's per-ticker lease, pending/timeout/restart recovery, producer-consumer and queue enrollment, exact owner authorization, live-safe atomic restore, complete source-owned recency/identity/census proof, scorer-readiness decision, and a separately owner-approved pilot transaction.
