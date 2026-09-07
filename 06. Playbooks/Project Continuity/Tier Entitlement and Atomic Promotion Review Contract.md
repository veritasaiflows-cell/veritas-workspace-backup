# Tier Entitlement and Atomic Promotion Review Contract

Status: review-only policy adopted for owner review; not implemented

Version: 0.9.1

Adopted for review: 2026-08-30 America/Phoenix

Owner surface: WF85 Alerts and Recommendations OS

## Decision

Adopt a tier policy in which Tier A, Tier B, and Tier C define research attention and evidence entitlements. A tier never means buy-ready, approved, deployable, or executable.

Adopt atomic promotion and demotion as mandatory future implementation behavior. Until a separately approved implementation and cutover passes the acceptance tests in this contract, guarded SQL membership remains unchanged and no promotion or demotion apply authority exists from this document.

## Objective

Ensure that every effective Tier A ticker receives the evidence depth, freshness, review cadence, and recommendation synthesis promised by the tier. Prevent partial promotion, stale-evidence gaming, queue starvation, duplicate truth surfaces, macro double-counting, analyst-data misuse, and authority leakage.

## Non-goals and stop lines

This contract does not:

- change a ticker's tier;
- change alert bands, invalidation thresholds, thesis canon, SQL, cron schedules, runtime, or channels;
- create holdings, positions, allocations, sizing, tranches, cash posture, rebalancing, or simulated account state;
- authorize capital, orders, brokerage or account action, money movement, paper/live execution, or external delivery;
- revive historical WF78 production, deployment, paper, or execution routes;
- authorize archive, deletion, or destructive duplicate-surface cleanup.

Generated packets, tier labels, scores, alerts, and recommendations remain review evidence only.

## Current verified baseline

As of the 2026-08-30 local proof set:

- Guarded SQL contains 15 Tier A, 17 Tier B, and 268 Tier C tickers.
- The active quote/alert and analyst-refresh set contains 18 names and covers only 10 of 15 Tier A and 8 of 17 Tier B names.
- Current Tier A entitlement gaps are CME, ITA, LIN, META, and PH.
- Current Tier B entitlement gaps are BKNG, ECL, GE, KTOS, NFLX, SMCI, TMUS, VMC, and WMB.
- The same 18-name list is independently embedded in `scripts/run_alerts_recommendations_chain.py`, `scripts/alert_level_freshness_controller.py`, and `state/cron-contracts/finance-weekly-analyst-consensus-evidence-refresh.json`.
- `tmp/analyst-consensus-current.json` carries its own conflicting `tier_sets`; those sets are not authoritative.
- Market/alert freshness is operationally joined today. Official filing, fundamental, macro, catalyst, and analyst evidence remain feeder evidence requiring Main synthesis for a material recommendation.

This baseline is a known failed coverage condition. It cannot be relabeled green by counting enrollment without delivered, fresh, validated output.

## Policy definitions

- **Effective tier:** the only authoritative attention tier, read from guarded SQL through its approved read path.
- **Tier candidate:** a review state proposing a different tier. It has no entitlement or membership effect.
- **Entitlement:** evidence or review service owed by an effective tier.
- **Observed entitlement:** the required producer ran on schedule, emitted the required ticker output, passed validation, met recency, and carried no unresolved lineage conflict.
- **Coverage:** observed entitlements divided by required entitlements, measured per ticker and tier over the defined service window. Enrollment alone is not coverage.
- **Material alert override:** an invalidation, thesis change, material catalyst, or serious freshness conflict can outrank routine tier work for any ticker. The override changes queue priority, never effective tier.
- **Current:** a per-evidence-class recency limit, not a judgment word.

## Dynamic entitlement scope and invocation consistency

The future dynamic scope owner is the guarded SQL read path in `scripts/finance_sql_canon_access.py`. It is a read-only consumer boundary; it grants no tier-write, canon, schedule, provider, account, capital, or execution authority.

- The sole canonical effective-tier field is `universe_membership.tier`, using the values `A`, `B`, and `C`. A Tier A+B invocation includes every `securities.active=1` row whose canonical effective tier is `A` or `B`, in deterministic ascending ticker order.
- `universe_membership.sql_tier` and `universe_membership.coverage_obligation_tier` are consistency witnesses, not alternate membership predicates. They must map exactly to the canonical tier (`Tier A`/`A`, `Tier B`/`B`, or `Tier C`/`C`). A missing, invalid, or disagreeing witness fails the complete scope closed as `guarded_sql_scope_tier_conflict`; no ticker-scoped provider work may start.
- `decision_grade_eligible` is not a membership filter. An active effective Tier A or B ticker with that flag false remains in the returned scope with its false flag preserved and resolver-derived `eligibility_debt`. This debt means missing decision-grade eligibility, not structural corruption: it permits only otherwise-authorized evidence collection and never confers decision, recommendation, or band-dependent claim readiness. Tier C remains outside the Tier A+B scope regardless of this flag. A missing or disagreeing tier witness, invalid identity, or other structural failure still fails closed; every non-empty `integrity_breaches` value is rejected without string-shape exceptions.
- The committed-snapshot fingerprint remains one SHA-256 digest of the UTF-8 canonical JSON array of the ordered tuples `[ticker, tier, decision_grade_eligible]`. The shared resolver is the sole implementation of this encoding. The returned scope also carries its source label, ordered ticker count, tier breakdown, structural integrity failures, and eligibility debt separately. A present serialized `eligibility_debt` list must exactly match debt derived from fingerprint-bound member flags; absent annotations retain the explicit legacy rule of deriving debt from those flags, never inferring readiness. Derived labels or counts do not override the flags.
- A logical producer invocation resolves one immutable scope snapshot before planning any ticker work. An orchestrator passes that serialized scope and fingerprint to every child. A child recomputes the fingerprint only from that received serialization; it never re-queries guarded SQL or selects its own membership. A serialization/fingerprint mismatch fails the logical invocation closed as `guarded_sql_scope_payload_fingerprint_mismatch`, performs no further provider work, and records visible repair debt.
- There is no code-level ticker ceiling, truncation, static membership list, cached scope, or silent fallback. The 15/17/32 values below are admission and measurement facts, never a resolver limit.
- If the returned complete scope exceeds a named provider-workload envelope, the resolver still returns every member and records `scope_over_envelope`. A provider-capable path without a separately approved envelope expansion must make zero provider calls and emit a visible overflow/entitlement-debt record containing the full scope fingerprint and counts. It may not drop, defer indefinitely, or substitute some members. The required owner decision is an envelope-expansion/canary decision, not a tier rewrite.
- A provider-capable dynamic path is disabled by default. Authority comes from the standing owner-approved provider policy at `state/dynamic-entitlement-provider-policy.json`, adopted 2026-09-02. That policy alone declares the enabled flag, allowed components, allowed providers, scope-count envelope, per-member attempt ceiling, run-duration cap, and daily aggregate provider-call budget. A missing, disabled, malformed, or unknown-field policy fails closed with zero provider calls. Preview and dry-run may resolve and report the complete local scope plus gate status, but make zero provider calls and cannot be treated as external enablement.
- The retired mechanism was a per-run signed approval record with an Ed25519 signature, module trust pin, 900-second record TTL, per-run decision packet, and twelve-file source-hash binding. Randall retired it on 2026-09-02 on the ground that ordinary non-capital data collection must not require per-run owner approval. Nothing else moved: the policy grants provider reads only, and the scope-count envelope became an owner knob instead of a static `32` that voided the run on the next Tier A/B admission.
- Scheduler/payload cutover (Phase 3G), guarded-SQL tier transactions (Phase 4), capital, orders, accounts, external delivery, and runtime/config change remain outside the standing policy and still require their own separate owner decisions.
- Tier C material attention remains a Phase 3E queue-and-review lane. It may surface a material event immediately, but it does not add Tier C names to the Tier A+B dynamic external scope or change effective tier.

Default recency limits:

| Evidence class | Current means | Failure state |
|---|---|---|
| Quote/session | Current market session, or explicitly the last completed session when the market is closed | `freshness_decay` |
| Official filing/earnings review | Most recent available official document, reviewed inside the tier SLA | `stale_evidence` or `review_overdue` |
| Fundamental packet | Covers the most recent completed reporting period; partial fields are named | `stale_evidence` or `partial_evidence` |
| Macro overlay | Most recent daily regime state for Tier A; current weekly state for Tier B, plus event refresh | `macro_stale` |
| Catalyst/event calendar | Next known scheduled event identified, plus material events since the last completed session, from a named source | `catalyst_stale` or `unsourced_catalyst` |
| Analyst context | Most recent weekly refresh, with material-use cross-check status | `analyst_quarantined` |

An evidence class without a defined recency limit cannot be called current or satisfy promotion, coverage, or recommendation completeness.

## Tier entitlements

| Entitlement | Tier A | Tier B | Tier C |
|---|---|---|---|
| Quote and threshold evaluation | Every scheduled market window plus material events | Morning/post-close plus material events | Changed-only or event-driven |
| Official earnings/filing review | Within 1 business day of availability | Within 3 business days | Required before promotion or material recommendation |
| Fundamental packet | Full current packet; conflicts and missing fields explicit | Current core packet; repair debt explicit | Thin screen only |
| Macro/sector overlay | Daily and material-event overlay | Weekly and material-event overlay | Theme/discovery context only |
| Analyst context | Weekly; source-open cross-check before a material claim | Weekly breadth context; source-open before a material claim | Optional and never load-bearing |
| Recommendation card | Every material state change | Material alert/catalyst | Only after promotion-quality evidence |
| Contradiction handling | Fail closed and publish repair debt | Fail closed for the affected claim | Monitor or exclude |

Tier A work is the first scheduled research entitlement after material-alert incidents. Tier A routine volume may not suppress a material alert from another tier.

## Capacity and service-level proof

- The initial policy admission caps remain 15 Tier A and 17 Tier B during the implementation proof period. They govern whether a later Phase 4 guarded-SQL membership transaction may admit a new effective-tier member; they are not code-level resolver limits and may not justify consumer truncation.
- The observed 15 Tier A / 17 Tier B / 32 Tier A+B values are the initial measurement envelope. A membership count beyond that envelope is visible `scope_over_envelope` service debt, not a reason to omit an eligible ticker from the returned scope.
- Tier A coverage is measured weekly as observed entitlements divided by required entitlements for each name over a trailing four-week window.
- No cap increase is eligible until every effective Tier A ticker records 100% coverage for four consecutive weeks, all official events in that window meet their deadline, and no partial promotion state is observed.
- Every digest must publish the failed-entitlement ticker list, evidence class, age in business days, owner, and next repair step.
- A Tier A gap is visible immediately. A gap older than one business day becomes a P1 coverage breach; a gap older than 10 business days is a contract failure, not compliant degradation.
- A Tier B entitlement gap older than 10 business days is published as contract debt on every digest and blocks any Tier B cap change until repaired. It remains P2 and never outranks a Tier A breach.
- Capacity proof must include measured producer load, source-open review load, Main review load, queue aging, retry rate, and missed SLAs. A declared cap without this evidence is not demonstrated capacity.
- A challenger cannot displace an incumbent because this OS failed to deliver the incumbent's entitlement. System-caused staleness creates repair debt, not a comparative weakness.
- Cap expansion, schedule change, or new recurring external-source use remains a separate owner-gated implementation decision.

## Queue precedence and starvation bounds

| Priority | Work |
|---|---|
| P0 | Invalidation, thesis change, material ticker-specific catalyst, or serious evidence conflict for any tier |
| P1 | Tier A material review and Tier A entitlement breach |
| P2 | Due Tier A scheduled work, Tier B material review, and overdue Tier B entitlement repair |
| P3 | Promotion/demotion candidates and oldest Tier C research candidates |
| P4 | Duplicate-surface retirement and non-urgent hygiene |

Rules:

- A broad macro event does not create one P0 per ticker unless each ticker has a distinct material consequence. Duplicate events are grouped by ticker, state, cause, and source version.
- No queue item may go one market day without review or a visible deferral record naming the higher-priority work that displaced it.
- A P3 candidate may not go more than five market days without a visible status refresh.
- P0 volume above measured capacity produces an explicit degraded-mode digest with total queued, reviewed, deferred, and oldest age. No item is silently dropped.
- Ranking orders work inside a priority bucket. It cannot suppress a material state or rewrite effective tier.
- A pending, blocked, or expired promotion candidate that fires a material alert is handled under its prior effective tier plus the material-alert override.

## Atomic promotion

Future state machine:

`promotion_candidate -> promotion_pending_coverage -> tier_effective | promotion_blocked | promotion_expired`

The prior effective tier remains authoritative until a single commit record is complete.

Required mechanics:

1. One named guarded-SQL writer holds an exclusive ticker lease for the entire transaction.
2. The transaction records a unique ID, expected prior tier/version, fixed enrollment order, forward action, exact inverse, and timeout.
3. Every step is idempotent. A second writer or prior-version mismatch fails closed.
4. Default timeout is the end of the next market session. Timeout returns the candidate to its prior effective tier and records reasons.
5. Restart recovery reverses any transaction without an effective-tier commit or marks it blocked. A half-promoted ticker is never observable as effective.
6. Consumers derive scope from guarded SQL after commit; they do not maintain independent membership lists.
7. The transaction must leave `tier`, the two consistency witnesses, and `decision_grade_eligible` in a state that passes the dynamic-scope integrity rules before the effective-tier commit is observable. A mismatched flag or witness is an entitlement breach, never a silent exclusion.

Promotion proof must include:

1. resolved identity/listing checked against the most recent corporate-action and symbol-change record;
2. prior effective tier and version;
3. current thesis, official-source lineage, material risks, current macro/sector sensitivity, and catalyst/event context within the recency table;
4. every destination-tier producer and consumer enrollment;
5. every required evidence class inside its recency limit;
6. destination-tier capacity headroom or an approved comparative displacement;
7. current quote/session eligibility for the stated review consequence;
8. recommendation-card and queue enrollment;
9. duplicate-surface census showing no competing tier owner;
10. rollback, crash-recovery, validation, and audit proof.

A free-text `not_applicable` value cannot satisfy a proof. Exceptions must use an enumerated reason owned by this contract and remain visible in the audit record.

## Atomic demotion

Future state machine:

`demotion_candidate -> demotion_pending_coverage -> tier_effective | demotion_blocked | demotion_expired`

Rules:

- Staleness, missing OS-produced evidence, or temporary source failure alone cannot demote a ticker.
- A demotion proposal requires a named proponent, sustained thesis impairment or reduced materiality evidence, the same lease/version/timeout mechanics as promotion, destination-tier enrollment in the same transaction, rollback, and audit.
- No entity that benefits from vacated capacity may be the sole source of the demotion evidence.
- Apply authority is not granted here. A future implementation must name the policy authorization gate and the guarded-SQL writer separately.

## Evidence-to-recommendation compiler

Every material recommendation should use one lineage-bound join in this order:

1. guarded-SQL identity, effective tier, source lineage, thesis, band, and invalidation;
2. current quote and market-session proof;
3. most recent official filing/earnings evidence and validated fundamental packet;
4. ticker-specific catalyst and contradiction evidence;
5. one macro/sector overlay application;
6. quarantined secondary analyst context;
7. one current recommendation card and one digest projection.

### Finance evidence roles

- Official filings and company/SEC/IR evidence are primary for financial performance, guidance, balance-sheet, and thesis claims.
- Derived fundamental metrics may summarize primary evidence but must expose period, formula, lineage, warnings, and missing fields.
- Market data determines session, price, band proximity, no-chase, invalidation, and quote freshness. It does not rewrite static canon.
- Macro changes confidence, evidence burden, scenario risk, and review priority. It does not set recommendation direction or become a transaction signal.
- Analyst consensus is secondary expectations/dispersion context. It cannot set tier, thesis, band, invalidation, recommendation direction, scenario center, or evidence completeness.

### Macro single-application rule

Each card records one macro input version and one resulting delta. The same macro state cannot be applied again through ranking, scenario weighting, or sector scoring.

If an approved band or invalidation version already embeds the same macro snapshot, that influence is marked `already_embedded`; the card cannot add a second adjustment. Macro-informed canon maintenance, if ever used, remains a separate exact gate and is not authorized by this contract.

An approved band or invalidation version must record the macro snapshot version it embedded, or explicitly record `macro_not_embedded`. A version with no macro-embed lineage may be treated as `macro_not_embedded` only when its approval proof predates this lineage requirement; otherwise the card routes to repair until the lineage is declared.

### Analyst quarantine rule

- Any analyst artifact carrying a local `tier_sets` block is quarantined from tier routing.
- A source-open cross-check emits `pass`, `fail`, `stale`, or `unavailable`, with source, timestamp, horizon, and identity match.
- Analyst evidence can lower confidence or trigger verification. It cannot increase completeness, promote a ticker, move a scenario center, or override official evidence.
- If a material target or consensus claim cannot be cross-checked, omit it or label it unavailable.

## Single-owner and duplicate-surface policy

Keep exactly one active owner for each truth class:

| Truth class | Single owner |
|---|---|
| Tier membership | Guarded SQL |
| Tier policy and interpretation | This review contract plus active Alerts and Recommendations canon after approved cutover |
| Quote/session and alert freshness | One quote/freshness controller |
| Evidence join and recommendation queue | One compiler/queue |
| Current ticker recommendation | One current card per ticker |
| User-facing rollup | One digest derived from the queue/cards |

A surface is a prohibited duplicate if it can independently assign effective tier, band, invalidation, technical state, queue priority, or recommendation direction.

Before cleanup, implementation must produce a named inventory of every script, artifact, cron contract, cache, and document containing:

- a hard-coded ticker scope;
- `tier_sets` or local tier-bearing state;
- band, invalidation, technical, queue, or recommendation truth;
- portfolio, deployment, capital, position, sizing, order, or execution semantics.

Each inventory row needs keep/consolidate/archive/delete disposition, reference proof, semantic consumer review, rollback, and validation. Archive/delete requires separate explicit approval.

A field rename is not retirement. Renamed values and consumers must contain no surviving capital, deployment, position, sizing, order, or execution meaning.

Initial named consolidation targets are:

- `scripts/run_alerts_recommendations_chain.py` hard-coded 18-name scope;
- `scripts/alert_level_freshness_controller.py` hard-coded 18-name scope;
- `state/cron-contracts/finance-weekly-analyst-consensus-evidence-refresh.json` hard-coded 18-name scope;
- `tmp/analyst-consensus-current.json` local `tier_sets` semantics;
- any macro output or consumer still using portfolio/capital/deployment semantics;
- retired WF78/WF85 deployment, paper, or execution-era producers still discoverable as active.

## Authority separation for future implementation

- Alerts and Recommendations policy defines whether an apply is permitted.
- Guarded SQL is the only tier-membership writer.
- The authorization check and membership write are separate proof steps and cannot infer each other.
- Main verifies evidence, integrates challenger findings, and owns final recommendation judgment.
- Helpers may research or challenge. They cannot accept the contract, apply tier changes, or make final finance judgments.
- Randall retains any decision that lacks an already approved exact gate and all capital, execution, account, external, runtime, schedule, destructive, or authority-expansion decisions.

## Implementation phases requiring later approval

1. Build the exact duplicate-surface and producer/consumer inventory.
2. Replace hard-coded ticker lists with one guarded-SQL-derived scope and quarantine analyst-local tiers.
3. Build observed-entitlement measurement, aging debt, queue fairness, and the evidence compiler.
4. Build atomic promotion/demotion proposal and apply gates with lease, inverse, expiry, crash recovery, audit, and authority separation.
5. Run fault injection and a four-week Tier A service proof without changing the cap.
6. Propose cron/schedule changes and archive/delete actions separately, with rollback and explicit approval.
7. Cut over only after all acceptance gates pass and Randall approves the implementation scope that requires his authority.

## Falsification and acceptance tests

The policy fails if any of these tests fails:

1. **Current positive control:** the present CME/ITA/LIN/META/PH Tier A gap must report failed coverage, not green.
2. **Partial enrollment:** crash after any promotion step; every surface must retain the prior tier and show blocked/expired recovery.
3. **Lease contention:** two writers target one ticker; one must fail before mutation.
4. **Timeout:** pending coverage exceeds the next-session timeout; it expires with reasons and prior-tier authority.
5. **Stale source:** an aged fundamental packet, stale macro input, or outdated symbol cannot satisfy promotion.
6. **Coverage integrity:** enrollment with missing, invalid, stale, or conflicted output cannot count as observed entitlement.
7. **P0 flood:** 50 material items cannot silently drop work; deferrals, oldest age, and degraded capacity remain visible.
8. **Starvation:** no item exceeds one market day without review/deferral, and no P3 item exceeds five market days without status.
9. **Macro single application:** one macro perturbation creates at most one recorded card delta and never silently rewrites a band.
10. **Analyst injection:** changing analyst direction cannot move tier, band, scenario center, direction, or completeness; confidence cannot increase from analyst data alone.
11. **Duplicate census:** more than one active owner for any truth class, or any surviving hard-coded 18-name operational scope after consolidation, fails cutover.
12. **Rename semantics:** capital/deployment/position/sizing/order/execution meaning surviving a rename fails retirement.
13. **Incident during promotion:** a material alert on a pending ticker uses the prior effective tier plus override.
14. **Incumbent staleness attack:** an OS-created entitlement gap cannot help a challenger displace the incumbent.
15. **Authority clamp:** no test or generated artifact can apply a tier, canon, schedule, runtime, capital, order, account, paper/live, external, or destructive action without its exact separate gate.

## Review defaults Randall may adjust before implementation

| Decision | Adopted review default |
|---|---|
| Tier A cap | 15 until four consecutive weeks at 100% observed coverage |
| Tier B cap during proof | 17 |
| Promotion timeout | End of next market session |
| Queue visibility | One market day; P3 status at least every five market days |
| Analyst role | Secondary, quarantine-eligible, never load-bearing |
| Demotion apply | No authority from this contract; future exact gate required |
| Macro handling | One lineage-recorded application per card; no duplicate delta |
| Cleanup | Inventory and reference proof first; archive/delete separately approved |

## Challenger adjudication

The requested Ollama Cloud GLM5.3 read-only challenge returned `accept-with-changes`. Main accepted its load-bearing findings on measurable coverage, transactional promotion mechanics, queue aging, demotion symmetry, macro single application, analyst quarantine, duplicate-surface inventory, and authority separation.

The follow-up review of the applied contract returned `pass-with-findings`. Main accepted and repaired all three closure gaps: band-side macro-embed lineage, catalyst/event recency plus promotion proof, and the Tier B contract-debt clock.

Final bounded re-QA of version 0.9.1 returned `PASS`: all three findings were closed and no review-only authority was weakened.

Main adjusted two challenger suggestions:

- Macro-informed canon is not categorically forbidden. If an approved band already embeds the same macro version, the card must mark it `already_embedded` and apply no second delta.
- This contract does not assign automatic demotion authority or require per-ticker capital-style approval. A later exact routing gate must separately prove policy authorization and the guarded-SQL write.

## Acceptance state

- Policy contract: adopted for review.
- GLM5.3 challenge: completed and adjudicated.
- Current Tier A entitlement coverage: failed baseline; known five-name gap.
- Phase 2 implementation: complete and Main-accepted as a bounded source-retirement, guarded-SQL routing, and analyst-quarantine slice. The active reactivation-error count moved `13 -> 0`; the question router derives the exact 32 Tier A+B names from guarded SQL and fails closed on identity or SQL errors; analyst-local tier/confidence/queue truth was removed.
- Phase 2 did not change tier membership, finance canon, recurring schedule, runtime/configuration, alert bands, recommendation direction, capital, accounts, or execution. The live alert chain and weekly analyst job remain on their existing 18-name external workloads.
- Phase 3A dynamic-routing amendment: complete and Main-accepted as a local review-only contract slice. It replaces the static 18-to-32 proposal with the guarded-SQL scope, immutable invocation fingerprint, explicit no-omission overflow behavior, and positive external-scope gate defined above. The inherited `external_baseline_blocked` checks remain open; no 3A or 3B validation may be read as clearing them.
- Phase 3D observed-entitlement coverage: the local review-only projection and adversarial test slice is implemented. It resolves one guarded-SQL Tier A+B snapshot and reports quote/session, reference level, lineage, freshness, analyst symbol, recommendation-card, and queue evidence through one frozen source registry. Undefined reference/lineage recency, placeholder analyst output, missing cards/freshness, and the absent queue owner remain visibly non-observed; no substitute owner, new recency policy, dynamic polling, provider work, or action authority was created. Current proof: tmp/tier-entitlement-v091-phase3d-observed-coverage.json.
- Phase 3D observed-entitlement coverage is Main-accepted as a local review-only proof. The Opus 5 challenger findings were integrated; focused validation passed; and Randall explicitly accepted the actual GPT-5.6 Terra, medium-thinking substitute QA for this Phase 3D acceptance. The original GLM-5.3 route request remains nonconformant and is not relabeled as GLM QA. This one acceptance exception does not change model configuration/runtime or authorize any provider, scheduler, tier, canon, capital, account, or execution action. Current checkpoint: tmp/tier-entitlement-v091-phase3d-implementation-proof.json.
- Historical Phase 3F/3G preparation was documentation only: `tmp/tier-entitlement-v091-phase3f-external-canary-preparation-plan.json` and `tmp/tier-entitlement-v091-phase3g-scheduler-cutover-preparation-plan.json` describe the former disabled gate and four-contract inventory. Those implementation and per-run approval descriptions were superseded by the September 2 standing-policy change below; they are not current runtime truth or activation authority. Current recurring scope requires reconciliation of the five implicated workloads against live automation records, named contracts, actual stage parity, and current approval proof before any cutover. The September 5 completion work remains unaccepted; neither historic preparation nor local test success starts Phase 3H.
- The former `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json` is superseded by this dynamic contract. It has no approval or execution effect and cannot be revived without a new hash-bound envelope, overflow rule, contract binding, canary evidence, rollback, and named scheduler-contract gate.
- Follow-on inventory: 42 consolidation targets and 44 residual-sweep hits remain visible as separately dispositioned follow-up, not as a silent expansion of the completed Phase 2 slice.
- Phase 3F standing-policy cutover, 2026-09-02: Randall approved the policy values and directed dropping the cryptographic per-run approval path. The signed-record apparatus was removed from `scripts/phase3f_external_canary_approval.py`; `scripts/dynamic_entitlement_provider_policy.py` now owns strict policy validation and the daily provider-call ledger; and `require_dynamic_entitlement_external_gate` enforces the policy ceiling instead of returning a hard stub. Runtime enforcement kept from the retired path: no scope truncation, fail-closed overflow with a member-enumerating debt artifact and zero provider calls, scope/attempt/duration ceilings, component and provider allowlists, workspace-confined output paths, sealed capability handoff, and one-shot receipt plus per-component claim. Newly added: a daily aggregate call budget keyed to Phoenix local days.
- Daily-budget settlement, 2026-09-02: the ledger reserves the worst-case call count before any provider work and then settles to actual attempts, so unused reservation returns to the day. Settlement only ever lowers a day total; an actual count above its reservation is recorded as `overrun_attempts` and never granted; settlement is single-shot per `run_id`; a duplicate `run_id` reservation within a day fails closed; and a crash between reserve and settle deliberately leaves the reservation open so budget is not handed back on an unknown spend. Without this, a 64-call run against a 400-call day capped the day at six runs regardless of real usage, which would have constrained the four recurring Phase 3G contracts.
- First bounded run under the standing policy, `policy-20260903T052707Z` (2026-09-02 local): `analyst_consensus` over the 32-member guarded-SQL Tier A+B scope at fingerprint `2acd2c9c41a7798b`, 64 of 64 provider method attempts completed with zero failures in 6.79s. Evidence was auto-sourced for 31 of 32; `ITA` returned no analyst data because it is an ETF, which is a data-availability gap rather than a provider or scope defect. The resulting artifact remains quarantined at `placeholder_manual_required` with `decision_input_allowed=false` and `cross_check_conflict=unavailable` for all 32, so the run proves the dynamic scope path end to end and does not close the Phase 3D coverage debt.
- Next decision: Phase 3G requires its own separate owner decision after an accepted 3F canary run; it alone may propose named recurring scheduler/payload changes. Phase 4 separately owns any guarded-SQL tier transaction. Neither is authorized by the standing provider policy.
