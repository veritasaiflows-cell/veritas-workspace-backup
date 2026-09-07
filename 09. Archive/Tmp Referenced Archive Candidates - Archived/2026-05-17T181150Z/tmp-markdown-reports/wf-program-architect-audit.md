# WF40-WF49 Program Architect Audit

Generated: 2026-05-09 MST  
Scope: WF40, WF44-WF47, WF41-WF43, WF48-WF49.  
Authority boundary: planning/audit only. No trading, no canonical finance mutation, no config/auth/channel/network mutation, no inferred owner approval.

## Workflow under review

Current program stack for moving Veritas toward higher-grade owner-gated capital-deployment recommendations:

1. **WF40** - cyber-security / runtime governance proof gate.
2. **WF44-WF47** - truth-surface and trust-contract prerequisites.
3. **WF41-WF43** - Level-3 recommendation-prep automation spine.
4. **WF48-WF49** - operator-gated sidecars for canonical mutation ownership and credential/runtime inheritance.

## Current phase

The stack is still in **scheduled artifact generation + scheduled review-surface generation**, not autonomous decision execution. Existing scripts can already generate market-intelligence and daily-review artifacts, but the control surface is not yet decision-complete or trust-boring enough to widen recommendation autonomy.

WF40 remains the active blocker because the 2026-05-09 scheduled proof failed closed: fresh wrapper proof exists, but `proof_status=blocked`, `audit_status=critical`, `audit_stop_line=true`, and wrapper errors are non-empty. The immediate blocker set includes an allowed queue/registry wording mismatch plus operator-gated config/auth/channel findings.

## Recommended next phase

Recommended next phase is **read-only/gated implementation hardening**, in this exact sequence:

1. Repair/triage WF40 proof enough to either close or explicitly hand off with named operator-gated residue.
2. Land WF44-WF47 as prerequisite truth-surface and trust-contract hardening.
3. Then harden WF41-WF43 into decision-grade review packets and append-only history.
4. Keep WF48/WF49 as operator-gated sidecars that may be asked/handled when they block evidence quality or authority vocabulary, but must not be silently merged into implementation lanes.

## Safe automation boundary

Allowed automatically after proof:
- read-only checks;
- generated JSON/HTML/Markdown review artifacts under `tmp/` or explicit review-output folders;
- dashboard/rendering acceptance tests;
- fail-soft classifier output;
- review-only event packets, recommendation packets, and append-only history rows;
- validators that block or downgrade downstream consumers.

Still blocked without explicit owner/operator approval:
- trade execution, account action, capital deployment, or automatic position sizing;
- canonical Portfolio Snapshot / Deployment Trigger Sheet / Watchlist mutation;
- thesis, promotion, demotion, or deployment-state mutation;
- config/auth/channel/network changes;
- credential storage or secret echoing;
- treating a clean packet, dashboard, or classifier state as owner approval.

---

# 1. Recommended phase sequence

## Phase 0 - WF40 active-blocker remediation and closure/handoff decision

**Goal:** make the control-plane/security proof boring enough that finance hardening work is not built on a failing runtime/governance gate.

**Implementation posture:** main-session controlled; helper lane may audit wording/proof only. No config/auth/channel mutations.

**Ordered work:**
1. Reconcile only the allowed queue/registry wording mismatch around WF40 cron-proof / repeated-stability residue.
2. Do not touch Telegram/channel config, `commands.ownerAllowFrom`, trusted proxies, browser enablement, auth, or network posture without explicit Randall approval.
3. Run or wait for a repeat wrapper proof.
4. Inspect:
   - `tmp/cyber-security-daily-audit-cron-proof.json`
   - `tmp/cyber-security-daily-audit.json`
   - `tmp/cyber-security-daily-audit.md`
   - cron run history / `06. Playbooks/Cron Run Ledger.md`
5. Decide one of:
   - **Close WF40** if clean proof is achieved and warning-grade debt is triaged.
   - **Bounded handoff** if the only remaining blockers are explicitly operator-gated config/auth/channel decisions.
   - **Keep active** if proof remains blocked/critical or contradictory.

**Do not advance WF44-WF47 from a blocked WF40 proof.** If the operator intentionally pauses WF40, record the pause and allowed residue first.

## Phase 1 - WF44 Command Center Decision Object Visibility

**Goal:** make the human decision surface show the decision objects that already exist.

**Implementation posture:** medium-thinking implementation helper, then read-only audit helper.

**Ordered work:**
1. Add Promotion Review rendering in Overview/action card/deployment strip/trigger summary.
2. Ingest current-window `daily-review-objects-<window>.json` and `market-intelligence-events-<window>.json` into dashboard payload.
3. Render a Daily Intelligence / Decision Queue panel with counts, escalations, capital recommendations, owner questions, and authority fields.
4. Preserve dual-layer states: owner repair/do-not-touch state plus secondary technical risk flags.
5. Surface visible warnings for authority contradiction or execution ambiguity where known.
6. Add acceptance tests that fail if generated decision objects exist but are hidden.

**Why first:** capital-deployment recommendations are not useful if Randall cannot see the live promotion-review queue, daily review objects, or fresh-intelligence escalations.

## Phase 2 - WF45 Shared Stale Source Fail-Soft Classifier

**Goal:** establish one source-trust vocabulary before consumers widen.

**Implementation posture:** medium-thinking implementation helper; low/medium read-only audit.

**Ordered work:**
1. Define `source_freshness` contract and vocabulary: `fresh`, `current`, `manual_dependency`, `partial`, `stale`, `contradictory`, `missing`.
2. Add unit tests for classification/severity/criticality behavior.
3. Port or wrap existing `dashboard_core.py` freshness logic without loosening behavior.
4. Embed classifier output into dashboard trust first.
5. Then propagate into run summaries and deployment readiness.
6. Only after schema stabilizes, add trust fields to market-intelligence events, daily-review objects, and artifact index.

**Why before WF41-WF43:** recommendation quality depends on knowing whether evidence is fresh, stale, partial, contradictory, or manually dependent. Clean validation must not be mistaken for clean source trust.

## Phase 3 - WF46 Run Summary Finalization Semantics Gate

**Goal:** eliminate fake-terminal chain state.

**Implementation posture:** focused debugging lane; high thinking only if the tail-order issue resists a simple pass.

**Ordered work:**
1. Reproduce the state where `run-summary-post-close.json` says top-level `ok` while `execution.chain_status=running` / `chain_status_normalized=false`.
2. Choose one model:
   - preferred: re-finalize run summary after terminal chain artifact exists;
   - fallback: explicitly classify self-observation as pending/ambiguous and show it downstream.
3. Update `test_run_summary_tail_order.py` or equivalent to match current manifest tail.
4. Ensure dashboard/readiness consumers do not treat top-level `ok` as terminal if execution block is unnormalized.

**Why here:** scheduled autonomy cannot widen while the chain can look green and still carry unresolved execution state.

## Phase 4 - WF47 Authority Vocabulary Reconciliation

**Goal:** prevent generated artifacts from claiming wider authority than the run summary permits.

**Implementation posture:** medium implementation helper, low read-only audit.

**Ordered work:**
1. Map authority fields across:
   - `run-summary-post-close.json`
   - `postclose-brief-input.json`
   - `postmarket-snapshot.json`
   - `daily-executive-brief.json`
   - market-intelligence events
   - daily-review objects
2. Define shared vocabulary for:
   - review-only packet;
   - generated note/archive write;
   - canonical note mutation;
   - presentation allowed;
   - portfolio/deployment mutation;
   - trade execution;
   - owner approval.
3. Add cross-artifact validator.
4. Prefer safer near-term posture: dated dashboard/brief notes are generated review/archive surfaces unless explicitly blessed as canonical owners.
5. Block any artifact from saying `canonical_note_mutation_allowed=true` when the run summary says scheduled windows are fail-closed.

**Why before WF42:** a capital recommendation object must not inherit contradictory mutation or approval language.

## Phase 5 - WF41 Market Intelligence Event Intake and Materiality Router

**Goal:** turn event intake into reliable review-only materiality packets.

**Implementation posture:** high-thinking helper for contract/audit if existing sidecar behavior is broad; medium implementation if gaps are narrow.

**Ordered work:**
1. Audit existing `scripts/market_intelligence_event_router.py` against WF41 contract.
2. Confirm source-tier map handoff from WF26 or name exactly what is stale/missing.
3. Define/verify schemas for:
   - event packet;
   - unresolved-truth packet;
   - no-route decision;
   - review-route candidate.
4. Add source-freshness block from WF45.
5. Prove daily-review consumer uses packets as evidence only.
6. Keep output review-only and owner-review-required.

**Do not add broad web/news crawling unless approved source-tier rules and freshness handling are already explicit.**

## Phase 6 - WF42 Capital Deployment Recommendation Object

**Goal:** produce a decision-grade but owner-gated `deploy / wait / reject / review` packet.

**Implementation posture:** medium implementation helper plus independent read-only audit.

**Ordered work:**
1. Compare current `daily_review_objects.py` capital recommendation output to full WF42 contract.
2. Add only missing fields/proofs, not a parallel recommendation system.
3. Required packet fields:
   - ticker;
   - current state;
   - entry-band status;
   - five-gate status;
   - catalyst/earnings window;
   - sector/correlation check or explicit manual fallback;
   - macro regime / source-freshness state;
   - fresh-intelligence flags and unresolved truth;
   - risk/invalidation;
   - sizing posture as guidance only, not execution;
   - recommended action: deploy candidate / wait for band / wait for catalyst clearance / hold promotion review / reject-bench / review;
   - confidence and evidence provenance;
   - `owner_approval_required=true`;
   - all mutation/execution permissions false.
4. Add tests that fail if owner approval is absent or if any canonical/portfolio/deployment/trade authority is implied.

**Recommended near-term wording:** “candidate for owner review,” not “approved to deploy.”

## Phase 7 - WF43 State History and Review Outcome Retention

**Goal:** create append-only historical truth so future predictive analytics can avoid hindsight bias.

**Implementation posture:** medium implementation helper; audit for no-rewrite and known-at-time separation.

**Ordered work:**
1. Choose minimal append-only storage path/table.
2. Define schema with separate sections for:
   - known-at-time state;
   - source/provenance/timestamps;
   - owner decision if any;
   - realized later outcome.
3. Add append command and no-rewrite validator.
4. Append sample daily state from current artifacts.
5. Add tests that reject history rewrites and fields that mix realized outcomes into known-at-time data.
6. Keep modeling disabled; this is retention infrastructure only.

## Phase 8 - WF48 operator-gated regime scoring ownership decision

**Goal:** decide whether direct mutation of `02. Markets/Regime Scoring Matrix.md` is allowed.

**Posture:** operator-gated. Do not implement without Randall’s decision unless live files prove intended authority.

**Decision options:**
1. **Bless direct mutation** as a bounded scheduled canonical owner exception, with explicit validator gates.
2. **Recommended safer option:** make scheduled run write `tmp/regime-scores.json` plus a review/proposal artifact; manual or owner-gated apply updates the Markdown note.

**When to run:** after WF47 vocabulary mapping, or earlier only if regime scoring blocks classifier/trust correctness.

## Phase 9 - WF49 operator-gated FRED runtime persistence

**Goal:** make FRED-backed macro inputs reliable without leaking credentials.

**Posture:** operator-gated runtime/credential pass.

**Ordered work after owner action:**
1. Randall rotates/replaces exposed key outside chat.
2. Configure correct runtime environment scope without writing key to workspace files.
3. Restart/refresh runtime as approved.
4. Verify OpenClaw child process sees `FRED_API_KEY` without key appearing in commands, logs, artifacts, or chat.
5. Run macro refresh scripts and scan workspace for secret prefix.

**Until complete:** WF45 should classify FRED-dependent outputs as `manual_dependency` or `partial` as appropriate. WF42 must not treat affected macro precision as clean.

---

# 2. Dependencies and blockers

## Hard dependencies

- **WF40 before all:** do not treat the automation stack as baseline-stable until WF40 either closes cleanly or is explicitly paused/handoffed with operator-gated residue named.
- **WF44 before WF42 usability:** recommendations must render where Randall reviews decisions.
- **WF45 before WF41-WF43 widening:** event/recommendation/history consumers need shared freshness/trust semantics.
- **WF46 before scheduled-confidence claims:** run summaries must be terminal or explicitly ambiguous.
- **WF47 before WF42:** capital recommendation objects must inherit coherent authority vocabulary.
- **WF41 before full WF42:** recommendation packets need fresh-intelligence flags and unresolved-truth routing.
- **WF42 before WF43 full outcome labels:** history should retain review outcomes from the recommendation object rather than reconstructing them later.
- **WF43 before future WF27 modeling:** no predictive analytics until point-in-time state and outcome retention are stable.

## Operator-gated blockers

- WF40: Telegram/channel config contradiction, `commands.ownerAllowFrom` readability, trusted proxy posture, plugin pinning, browser/network/auth changes.
- WF48: whether `regime_scoring_refresh.py` may directly mutate a canonical Markdown note.
- WF49: FRED key rotation/replacement, runtime environment mutation, restart/verification.

## Technical blockers to remove

- Command Center currently hides or under-renders Promotion Review, daily review objects, and market-intelligence escalations.
- Source freshness vocabulary is fragmented across dashboard/run-summary/readiness/router/review-object/index layers.
- Run summary can be top-level ok while execution state remains running/unnormalized.
- Authority fields currently conflict across post-close outputs.
- Sector/correlation artifact is still weak/manual for WF42.
- Append-only state-history schema does not exist.

---

# 3. Helper-lane roles / thinking

## Main session / Veritas integrator

Owns:
- queue/registry status;
- final phase advancement;
- authority decisions;
- synthesis;
- accepting/pausing workflows;
- user-facing blocking questions.

Use main session for small allowed edits and final proof review. Do not delegate final capital/authority judgment.

## Implementation helper lane - medium thinking

Use for:
- WF44 dashboard payload/render/test edits;
- WF45 classifier module/tests once contract is clear;
- WF47 authority vocabulary/validator edits;
- WF42 schema/test edits;
- WF43 append-only implementation.

Deliverable required from helper:
- changed files list;
- exact tests run;
- authority boundary statement;
- residual risks;
- rollback notes.

## Debugging helper lane - high thinking when needed

Use for:
- WF46 if chain tail/finalizer behavior is non-obvious;
- repeated false-green / false-red states;
- cross-surface contradictions that persist after first fix.

Deliverable required:
- root cause;
- repro case;
- minimal fix;
- targeted regression test;
- proof the fix does not loosen stop lines.

## Read-only audit helper lane - low/medium thinking

Use after each phase to verify:
- rendered artifacts exist;
- tests cover intended stop lines;
- authority language did not widen;
- generated surfaces do not imply owner approval;
- stats match actual artifacts.

## Research/contract helper lane - high thinking only when source-authority questions are ambiguous

Use for:
- WF41 source-tier mapping and unresolved-truth design;
- WF42 evidence/invalidation standard if packet shape becomes ambiguous;
- WF48 ownership-option analysis, but not final owner decision.

## Operator-only lane

Only Randall/operator may authorize:
- config/auth/channel/network changes;
- credential/runtime environment changes;
- canonical mutation exceptions;
- owner approval for capital deployment.

---

# 4. Phase acceptance gates

## Phase 0 / WF40 gate

Pass only if:
- fresh `tmp/cyber-security-daily-audit-cron-proof.json` exists;
- `proof_status=ok`;
- `artifact_fresh_for_runner=true`;
- `audit_stop_line=false`;
- wrapper `errors=[]`;
- cron run history matches expected job/window;
- any remaining warning-grade debt is triaged as accepted local-only posture or named manual backlog.

Fail/hold if:
- `status=critical`, `stop_line=true`, non-empty wrapper errors, stale proof, or unresolved control-surface contradiction.

## Phase 1 / WF44 gate

Pass only if:
- rendered Command Center shows Promotion Review and ETN distinctly from Deployable Now / Almost;
- current-window daily review counts/escalations render;
- current-window market-intelligence escalations render;
- capital recommendation summary renders with owner-gated language;
- LMT-style dual owner/technical state is represented;
- acceptance tests cover all above;
- `validate_dashboard_state.py --write` and dashboard acceptance tests pass.

## Phase 2 / WF45 gate

Pass only if:
- classifier contract exists;
- tests cover all seven classes;
- critical vs optional behavior is tested;
- manual dependency and contradiction behavior are tested;
- downstream artifacts include explicit no-canonical/no-capital/no-approval permission fields;
- no consumer treats absence of warnings as permission.

## Phase 3 / WF46 gate

Pass only if:
- clean chain produces terminal normalized run-summary execution state; or
- if finalization is genuinely pending, dashboard/readiness surfaces visibly classify ambiguity;
- targeted regression test exists;
- no artifact says fully terminal/green solely from top-level `status=ok` when execution state disagrees.

## Phase 4 / WF47 gate

Pass only if:
- shared authority vocabulary is documented/encoded;
- cross-artifact validator passes;
- post-close outputs agree on review-only vs generated note/archive vs canonical mutation;
- no output implies trade execution, portfolio mutation, deployment mutation, or owner approval;
- scheduled windows remain fail-closed unless a specific owner-approved exception exists.

## Phase 5 / WF41 gate

Pass only if:
- existing router sidecar is audited against WF41 contract;
- source-tier authority is explicit or missing source-tier status is flagged;
- event/unresolved-truth/no-route schemas are stable;
- source-freshness context is included;
- daily-review consumer proof shows packets are evidence only;
- no canonical, deployment, promotion, or trade authority is widened.

## Phase 6 / WF42 gate

Pass only if:
- one canonical recommendation packet schema exists;
- it includes evidence, invalidation, confidence, source freshness, unresolved truth, sector/correlation, and explicit owner approval fields;
- packet supports deploy/wait/reject/review outcomes without executing them;
- tests fail if `owner_approval_required` is missing or false;
- all mutation/execution flags remain false;
- at least one current/live or fixture candidate is generated and audited.

## Phase 7 / WF43 gate

Pass only if:
- append-only schema exists;
- sample append works from current artifacts;
- no-rewrite validator catches changed prior rows/labels;
- known-at-time fields and realized outcomes are separate;
- owner decisions are represented only when explicit;
- no modeling/deployment authority is introduced.

## Phase 8 / WF48 gate

Pass only if:
- explicit owner decision is recorded;
- script behavior matches decision;
- if mutation remains allowed, it is documented as a narrow canonical-owner exception with validator gates;
- if not allowed, chain writes proposal/review artifact instead;
- finance chain proof still passes.

## Phase 9 / WF49 gate

Pass only if:
- rotated/replacement key is configured outside chat/workspace files;
- OpenClaw child process sees key without command injection;
- FRED-backed scripts produce current inputs without missing-key warnings;
- workspace secret-prefix scan is clean;
- artifacts reflect true data quality.

---

# 5. Risks / stop lines

## Global stop lines

- Any output implies owner approval from confidence, freshness, or dashboard status.
- Any generated artifact authorizes trade execution, account action, portfolio mutation, or deployment mutation.
- Any workflow mutates canonical finance notes without explicit owner-approved authority.
- Any classifier upgrades stale/manual/partial/contradictory sources into clean deployment permission.
- Any dashboard badge is green/ok while hiding critical stale, missing, contradictory, manual dependency, or run-finalization ambiguity.
- Any SQLite/index consumer is treated as canonical finance truth.
- Any FRED/API key is written into workspace files, logs, chat, generated artifacts, tests, or command text.
- Any run summary says terminal ok while internal execution remains running/unnormalized without visible caveat.
- Any WF48/WF49 action is smuggled into implementation without owner/operator approval.

## Main risks

- **False precision:** capital recommendation packets may look more certain than stale/manual inputs justify.
- **Authority drift:** generated notes and dashboard surfaces may become de facto canonical if wording is not disciplined.
- **Surface incompleteness:** recommendations may exist but not render in the Command Center, reducing owner review quality.
- **Vocabulary drift:** `ok`, `clean`, `fresh`, `usable_with_caution`, `DEGRADED`, and `review_required` currently differ by script.
- **Finalizer drift:** scheduled runs can look successful from one artifact and ambiguous from another.
- **Credential/runtime blind spot:** FRED-backed data may work in an ad hoc shell but not in OpenClaw runtime.
- **Premature modeling:** WF43 history could be mistaken as permission to reopen predictive deployment logic.

---

# 6. Stats to report after each phase

Use the same compact stat block after every phase so the main session can compare progress without rereading every artifact.

## Universal phase stats

Report:
- workflow / phase id;
- status: `passed`, `blocked`, `partial`, or `rolled_back`;
- files changed count;
- generated artifacts count;
- tests/validators run count;
- tests passed / failed;
- stop-line count;
- warning count;
- owner/operator decisions required count;
- canonical mutation flags found true count;
- trade/account/deployment/portfolio mutation flags found true count;
- owner-approval-required fields present / missing;
- rollback needed: yes/no;
- next recommended action.

## WF40-specific stats

- cron proof generated_at;
- `proof_status`;
- `artifact_fresh_for_runner`;
- `audit_status`;
- `audit_stop_line`;
- wrapper error count;
- governance critical finding count;
- operator-gated blocker count;
- days/runs of clean scheduled proof.

## WF44-specific stats

- dashboard validation critical/warning/info counts;
- dashboard acceptance passed/total;
- promotion-review count rendered;
- daily-review object count rendered;
- daily-review escalation count rendered;
- capital recommendation count rendered;
- market-intelligence event count rendered;
- market-intelligence escalation count rendered;
- authority-warning count rendered;
- dual-layer owner/technical state cases covered.

## WF45-specific stats

- classifier classes covered by tests: count/7;
- source blocks classified by state;
- critical sources stale/missing/contradictory count;
- manual_dependency count;
- stop_line count from classifier;
- `review_required` trust count;
- downstream artifacts carrying `source_freshness` count;
- consumers still using legacy/ad hoc freshness only count.

## WF46-specific stats

- run-summary windows checked;
- windows with terminal normalized execution state;
- windows with pending/ambiguous execution state;
- top-level/status execution mismatches count;
- dashboard ambiguity warnings rendered count;
- regression tests added/updated count.

## WF47-specific stats

- artifacts scanned for authority fields;
- authority contradictions found/fixed;
- artifacts with `canonical_note_mutation_allowed=true`;
- artifacts with trade/portfolio/deployment mutation allowed;
- artifacts missing owner-approval fields where required;
- cross-artifact validator status.

## WF41-specific stats

- source-tier inputs checked;
- events emitted;
- unresolved-truth packets emitted;
- no-route decisions emitted;
- review-route candidates by route;
- source conflicts count;
- source_freshness worst classification;
- review-only/owner-review-required fields passed count.

## WF42-specific stats

- recommendation objects emitted;
- recommendations by action: deploy-candidate / wait / reject-bench / review;
- candidates blocked by stale/partial/contradictory/manual dependency;
- candidates with unresolved truth;
- candidates missing sector/correlation evidence;
- candidates missing invalidation;
- packets with `owner_approval_required=true` count;
- mutation/execution permission violations count.

## WF43-specific stats

- rows appended;
- prior rows modified count, expected `0`;
- known-at-time field count;
- realized-outcome field count;
- owner-decision rows with explicit approval/rejection evidence;
- stale-note flags emitted;
- no-rewrite validator status.

## WF48-specific stats

- ownership decision recorded: yes/no;
- regime script direct Markdown writes allowed: yes/no;
- validator gates present count;
- proposal artifacts emitted count if review-only route chosen;
- canonical exception documented: yes/no.

## WF49-specific stats

- key exposed in command/chat/artifact: yes/no, expected no;
- child-process key inheritance verified: yes/no;
- FRED-backed scripts passing without missing-key warnings count;
- macro artifacts improved from manual/partial to current/fresh count;
- secret-prefix scan hits count, expected `0`.

---

# Program-level recommendation

Do not try to jump directly from today’s review-object layer to autonomous capital action. The correct target is **high-grade Level-3 recommendation support**:

- automatically surface material events;
- rank review objects;
- generate capital-deployment recommendation packets;
- preserve point-in-time outcome history;
- show everything in the Command Center;
- fail soft/closed when evidence is stale or contradictory;
- stop at explicit owner approval.

The fastest safe path is: **WF40 proof/handoff -> WF44 -> WF45 -> WF46 -> WF47 -> WF41 -> WF42 -> WF43**, with **WF48/WF49 handled only through explicit operator gates** when their authority or data-quality decisions become blocking.
