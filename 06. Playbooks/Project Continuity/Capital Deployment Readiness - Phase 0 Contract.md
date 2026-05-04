# Capital Deployment Readiness — Phase 0 Contract

**Project:** Capital Deployment Readiness
**Phase:** 0 — Contract definition
**Author:** Claude (IC)
**Date:** 2026-05-01
**Status:** Complete — awaiting operator review

---

## 1. What this document is

This is the formal definition of the deployment-readiness contract for the Veritas OS. It establishes what "deployable now" means, what the readiness vocabulary means, where authoritative inputs come from, how false positives form, and what trust conditions override otherwise-attractive deployment candidates.

This is a Phase 0 contract pass. No code, surface, or canonical note has been changed. Everything here is definitional. Phase 1 (artifact audit against this contract) requires operator confirmation before beginning.

---

## 2. The deployment-readiness contract

A name is **deployable now** in this OS if and only if:

1. All five deployment gates pass (from `Deployment Trigger Sheet.md`), AND
2. System trust is not degraded to the point that any gate's inputs are unreliable, AND
3. The name's own workflow state is decision-grade (not WATCH or REPAIR without human promotion), AND
4. The operator has reviewed the morning stack explicitly — no automated promotion to action without human pass-over.

The five gates are:
- **Thesis gate:** Thesis remains intact. No material earnings, macro, sector, or company-specific degradation.
- **Macro/regime gate:** Current regime supports the name and sector. Do not fight the macro tape.
- **Technical gate:** Price is in or near the preferred zone, or structure confirmed. Support and invalidation are defined.
- **Catalyst gate:** No avoidable binary event too close unless plan is explicitly event-driven.
- **Risk/sizing gate:** Position fits Risk Rules. Stop/invalidation is explicit. Reward-to-risk is acceptable.

If any gate fails, the name is not deployable. If system trust is degraded, the result ceiling drops even when all five gates nominally pass.

The Deployment Trigger Sheet is the canonical human decision layer. The `tmp/trigger-sheet.json` and `tmp/positioning-ranking.json` are evidence inputs that inform it, not replacements for it. When machine output and note layer disagree, the note layer wins, and the disagreement must be explained.

---

## 3. Readiness-state vocabulary

Six states. All are defined below. TRUST BLOCKED is new — added by this contract.

| State | Meaning | Required conditions | Operator action |
|---|---|---|---|
| **DEPLOYABLE NOW** | All five gates pass, system trust is clean, entry is justified | Five gates pass + trust clean + workflow_state ≠ WATCH + human reviewed | Confirm and act |
| **ALMOST DEPLOYABLE** | Thesis intact, one blocking condition remains (typically price not yet in band, or one gate just short) | At least 4/5 gates pass; no hard block | Wait for condition; review next session |
| **BLOCKED** | Real catalyst or event prevents action | Earnings block active, or explicit event block | Do not act; re-evaluate after event |
| **DO NOT TOUCH** | Risk, structure, or uncertainty too poor | below_stop = true, or repair mode + no new setup | Off the board entirely |
| **WATCH / RESEARCH NEEDED** | Not decision-grade; missing levels or thesis depth | No human-validated entry band, no confirmed stop | Do not deploy; complete research first |
| **TRUST BLOCKED** | Machine trust degraded; otherwise-attractive name cannot be treated as deployable | Any active trust-override condition (Section 5) | No action until trust restored or manual gate cleared |

**State hierarchy:** TRUST BLOCKED overrides any name-level state. A name that would otherwise be DEPLOYABLE NOW becomes TRUST BLOCKED when trust conditions trigger. This override is explicit and visible — it must not be buried in a score component.

**ALMOST DEPLOYABLE is not permission to deploy.** It means conditions are constructive but the specific trigger has not been met. Do not treat proximity to band as equivalent to being in band.

---

## 4. Source-owner-reader-cadence table

### Machine artifact layer

| Artifact | Who writes it | Who reads it | Canonical or derived | Cadence | Staleness threshold | Notes |
|---|---|---|---|---|---|---|
| `tmp/technical-refresh.json` | `run_finance_refresh_chain.py` | deployment-check, trigger-sheet | Derived | Daily post-close | 36h | Price, MA, band inputs |
| `tmp/market-state.json` | `run_finance_refresh_chain.py` | regime-scores, trigger-sheet | Derived | Daily; pre-market + post-close | 24h | Macro snapshot; FedWatch missing |
| `tmp/deployment-check.json` | Scripts post technical+market | trigger-sheet, operator | Derived | After technical + market | 24h | Deployment state per name |
| `tmp/trigger-sheet.json` | Scripts post deployment-check | positioning-ranking, dashboard, operator | Derived — NOT canonical | After deployment-check | 24h | **Key**: this does not replace note layer |
| `tmp/regime-scores.json` | Scripts post market-state | positioning-ranking | Derived | After market-state | 36h | Scores per name per regime |
| `tmp/positioning-ranking.json` | Scripts post trigger + regime | Operator morning review | Derived — NOT canonical | After trigger + regime-scores | 24h | Priority order; subject to false positives |
| `tmp/dashboard-validation.json` | Validator script | run-summary, operator | Derived — trust signal | After all upstream artifacts | 24h | Warning count drives trust state |
| `tmp/run-summary-post-close.json` | `run_finance_refresh_chain.py` | Operator morning review | Derived — **trust-state authoritative** | Post-close | 24h | `fallback_state` and downstream gates are binding |
| `tmp/policy-expectations.json` | Scripts (CME primary; manual fallback) | macro gate in trigger-sheet | Derived — currently degraded | Daily | 24h | CME primary at 404; manual fallback active |

### Canonical note layer

| File | Who writes it | Who reads it | Cadence | Staleness threshold | Notes |
|---|---|---|---|---|---|
| `03. Portfolio/Deployment Trigger Sheet.md` | Operator / Claude on standing authority | **Morning deployment decision** | After technical refresh, earnings, macro regime changes | 7 days max; 5 days for active setups | This is the canonical deployment decision layer. Machine output informs it; does not overwrite it. |
| `03. Portfolio/Portfolio Snapshot.md` | Operator / Claude | Portfolio-level review | After trigger sheet changes, earnings, macro shifts | 7 days max | Owns posture, weights, concentration flags |
| `07. Risk/Risk Rules.md` | Operator | All sizing decisions | On operator update only | Standing; review quarterly | Non-negotiable sizing and escalation rules |
| `05. Intelligence/Weekly Positioning Review.md` | Operator / Claude | Weekly operating stance | Weekly (Sunday or Monday) | 7 days | Canonical weekly operating map |
| `01. Dashboards/Executive Brief.md` | Operator / Claude | Session orientation | After meaningful developments | 48h warning threshold | Orientation surface; not a canonical decision source |

### Morning operator read order

For a valid morning deployment decision, read in this sequence:

1. `tmp/run-summary-post-close.json` → determine trust state and stop_line
2. `tmp/dashboard-validation.json` → count and classify active warnings
3. `tmp/trigger-sheet.json` → action states and blockers per name
4. `tmp/positioning-ranking.json` → priority order (read through the trust filter)
5. `03. Portfolio/Deployment Trigger Sheet.md` → human interpretation and final state

**Do not skip step 1.** If `stop_line = true`, stop the stack entirely. If `fallback_state.used = true`, DEPLOYABLE NOW is suspended before reading further.

---

## 5. False-positive pathways

Each pathway describes how a name can appear deployable in machine output when the correct answer is "not yet" or "no."

### FP-1 — Machine-in-band without thesis depth

**How it happens:** `in_entry_band: true` triggers DEPLOYABLE NOW in deployment-check and trigger-sheet. The check does not validate thesis depth or note-layer readiness. A name with `workflow_state: WATCH` and `thesis_status: "under active review"` can reach DEPLOYABLE NOW purely on price.

**Current instance:** GS ranks #1 in positioning-ranking.json as DEPLOYABLE NOW. Its own trigger-sheet record says `why: "Name is tracked, but not yet decision-grade because explicit entry and stop are still missing"` and `workflow_state: WATCH`. The machine and the note directly contradict each other.

**Mitigation contract:** A name with `workflow_state = WATCH` cannot be DEPLOYABLE NOW regardless of price. Cap at ALMOST DEPLOYABLE with explicit human promotion required before any upgrade.

---

### FP-2 — Stale earnings block after print

**How it happens:** `earnings_blocked: true` persists after the earnings event passes. The block does not auto-clear based on event date. Once the block finally clears (by whatever mechanism), the name may jump immediately from BLOCKED to ALMOST DEPLOYABLE or DEPLOYABLE NOW without a post-earnings human review of setup quality.

**Current instances:** AMZN, GOOG, MSFT show `earnings_blocked: true` with 83–91 days to next earnings. Their April 29 prints already happened. The block is stale. Dashboard validation flags this as `earnings_block_window_unexpected` for all three.

**Dual failure mode:** (a) The name stays falsely BLOCKED longer than it should — masking a legitimate post-earnings opportunity. (b) When the block eventually clears, it may promote without review — creating a false readiness signal.

**Mitigation contract:** Earnings block expiry must trigger a `REQUIRES POST-EARNINGS REVIEW` state, not automatic promotion. A human review gate interposes before re-promotion. Block clearance via date flip alone is not sufficient.

---

### FP-3 — Post-earnings name with stale pre-print setup

**How it happens:** A name just reported earnings. Pre-print bands and setup logic are obsolete. Machine bands are calculated from pre-print prices. The name appears constructive because the prior setup holds numerically, but the setup itself has not been revalidated for the new post-earnings context.

**Current instance:** CAT has `days_to_earnings: -1` (reported 2026-04-30). Trigger-sheet shows ALMOST DEPLOYABLE with `why: "Name is tracked, but not yet decision-grade because explicit entry and stop are still missing"`. No post-earnings note exists. The pre-print setup is stale by definition.

**Mitigation contract:** Any name with `days_to_earnings ≤ 0` and no confirmed post-earnings human review note is capped at `WATCH / REVIEW NEEDED` regardless of machine state. Re-promotion requires an explicit post-earnings setup note.

---

### FP-4 — Stale entry band on an otherwise-constructive name

**How it happens:** Entry bands can drift stale relative to current price and MA structure. A stale band can place a name falsely in-band (creating a false DEPLOYABLE NOW signal) or falsely out-of-band (masking a real opportunity). Dashboard validation identifies this but the downstream machine states do not always reflect it.

**Current instances:** 10 bands flagged stale in `dashboard-validation.json`: ETN, GOOG, AMZN, VRT, RTX, CAT, CVX, PLTR, KTOS, SLV.

**Mitigation contract:** Names with a `band_staleness` warning for their ticker cannot exceed ALMOST DEPLOYABLE. Band must be refreshed and human-confirmed in the trigger-sheet note before DEPLOYABLE NOW is valid.

---

### FP-5 — Near-earnings ALMOST DEPLOYABLE with no explicit catalyst gate applied

**How it happens:** The earnings block only activates within a defined pre-earnings window (typically 0–14 days by code logic). A name with earnings in 5–7 days may show ALMOST DEPLOYABLE because it is technically not "earnings blocked" yet. The catalyst_risk score component is low, depressing total score, but the action_state label does not reflect the real decision constraint.

**Current instance:** ETN has earnings in 4 days. Machine shows ALMOST DEPLOYABLE. Catalyst_risk = 2/5. The action_state says "almost deployable" — an operator focused on the label could treat ETN as ready when the real judgment is: do not size into a name 4 days before its print unless the plan is explicitly event-driven.

**Mitigation contract:** Names with `days_to_earnings ≤ 7` and `catalyst_risk_score ≤ 2` carry a `NEAR-EARNINGS CAUTION` qualifier on the action state. Sizing is capped at half the normal tier unless the plan is explicitly event-driven and documented.

---

### FP-6 — Macro gate operating on degraded inputs

**How it happens:** The macro/regime gate is one of the five required gates. Regime scores and macro fit assessments are computed from `market-state.json` and `policy-expectations.json`. Currently: Fed target is hardcoded, FedWatch is unavailable (CME 404), and policy expectations run on manual fallback. A name passes the macro gate based on a regime assessment that is partially manually maintained.

**Current instance:** All regime_fit scores in regime-scores.json are computed against a macro backdrop that has active `macro_manual_dependency` and `policy_expectations_fallback_source` warnings.

**Mitigation contract:** When `macro_manual_dependency` or `policy_expectations_fallback_source` is active, the macro gate passes with a `DEGRADED` qualifier. Any DEPLOYABLE NOW result during degraded macro trust must carry that qualifier explicitly in the morning review surface. Operator must acknowledge it, not just read past it.

---

### FP-7 — Priority ranking bonus overrides semantic readiness state

**How it happens:** `positioning-ranking.json` applies score bonuses (+2 for near-band, +3 for in-band + DEPLOYABLE) that boost a name's priority rank independent of thesis depth or note-layer validation. A name with weak fundamental conviction and no decision-grade setup can rank above a name with strong conviction that is slightly out of band. The machine says "act on X first" when the real answer is "X isn't ready."

**Current instance:** GS ranks #1 (score 20, fundamental_conviction=3, thesis "under active review") over JPM (#2, score 20, fundamental_conviction=5, thesis "intact"). The machine prioritizes GS; the correct answer is JPM is the only defensible candidate.

**Mitigation contract:** Names with `workflow_state = WATCH` or `thesis_status = "under active review"` are capped at Secondary priority bucket regardless of score. Score bonuses cannot move them into Highest Priority until human promotion.

---

## 6. Trust-override rules

When any condition in this table is true, the stated deployment ceiling applies. These are additive — multiple active conditions compound. The most restrictive condition governs.

| Condition | Source artifact | Effect |
|---|---|---|
| `stop_line = true` | run-summary-post-close.json | **Full system halt.** No deployment decisions. All names downgraded to WATCH minimum. No action until stop_line clears with operator confirmation. |
| `fallback_state.used = true` | run-summary-post-close.json | DEPLOYABLE NOW suspended system-wide. Ceiling drops to ALMOST DEPLOYABLE. Manual operator confirmation required before any action on any name. |
| `canonical_note_mutation_allowed = false` | run-summary-post-close.json | No automated note updates to Deployment Trigger Sheet or Portfolio Snapshot. Human writes only. |
| `presentation_allowed = false` | run-summary-post-close.json | Dashboard surfaces should not be treated as authoritative publication. Read for evidence, not for clean sign-off. |
| `dashboard_validation overall = "warning"` | dashboard-validation.json | Operator must explicitly pass over all active warnings before treating any name as DEPLOYABLE NOW. Not a hard block, but a required review step. |
| `timing_sensitive_earnings_dates` warning active | dashboard-validation.json | Any name in warning scope cannot be promoted past ALMOST DEPLOYABLE until earnings date confirmed directly from IR. |
| `earnings_block_window_unexpected` warning active | dashboard-validation.json | Affected name's block may be stale or erroneous. Do not lift block or confirm clearance based on machine output alone. Human review required. |
| `macro_manual_dependency` warning active | dashboard-validation.json | Macro gate passes with DEGRADED qualifier only. DEPLOYABLE NOW results carry explicit macro-degraded caveat. |
| `policy_expectations_fallback_source` warning active | dashboard-validation.json | Same as macro_manual_dependency: macro gate is partially manual. Treat policy-sensitive names with extra caution. |
| Name `workflow_state = WATCH` | trigger-sheet.json | Cannot be DEPLOYABLE NOW regardless of technical state. Cap at ALMOST DEPLOYABLE. Explicit human promotion to decision-grade required before any upgrade. |
| Name `thesis_status = "under active review"` | trigger-sheet.json | Cannot be ranked Highest Priority. Capped at Secondary. Thesis review must complete before deployment priority elevation. |
| Name `days_to_earnings ≤ 7` AND `catalyst_risk_score ≤ 2` | trigger-sheet.json + regime-scores.json | NEAR-EARNINGS CAUTION: sizing capped at half normal tier. Not a hard block unless `earnings_blocked = true`. Operator must explicitly accept pre-print exposure. |
| Name `days_to_earnings ≤ 0` AND no confirmed post-earnings review | trigger-sheet.json | Cap at WATCH / REVIEW NEEDED. Post-earnings setup validation required before any re-promotion. |
| Name in `band_staleness` warning scope | dashboard-validation.json | Cannot exceed ALMOST DEPLOYABLE. Band refresh and human confirmation required before DEPLOYABLE NOW. |
| Name `below_stop = true` | deployment-check.json | **Hard block.** DO NOT TOUCH regardless of any other signal. |
| Name `deployment_state = "BELOW STOP"` | deployment-check.json | Same as above. Hard block. |

### Current trust state as of 2026-05-01 morning

Based on `run-summary-post-close.json`, `dashboard-validation.json`, and `trigger-sheet.json`:

**Active trust-override conditions:**
- `fallback_state.used = true` → DEPLOYABLE NOW suspended system-wide
- `canonical_note_mutation_allowed = false` → human-write-only on notes
- `presentation_allowed = false` → surfaces are evidence, not publication
- `dashboard_validation overall = "warning"` → operator pass-over required
- `timing_sensitive_earnings_dates` → BRK.B, NVDA dates unconfirmed
- `earnings_block_window_unexpected` → AMZN, GOOG, MSFT blocks stale post-Apr-29 prints
- `macro_manual_dependency` → macro gate degraded
- `policy_expectations_fallback_source` → CME 404, manual fallback active

**Net effect on each name this morning:**

| Name | Machine state | Trust-override verdict | Reason |
|---|---|---|---|
| GS | DEPLOYABLE NOW (#1) | **TRUST BLOCKED** | workflow_state=WATCH; FP-1; fallback_state active; thesis not decision-grade |
| JPM | ALMOST DEPLOYABLE | ALMOST DEPLOYABLE (confirmed) | Thesis intact, no trust blocker specific to this name; still pullback-only |
| NVDA | ALMOST DEPLOYABLE | ALMOST DEPLOYABLE with NEAR-EARNINGS CAUTION | Days to earnings=19, catalyst_risk=4; unconfirmed date adds FP-5 risk |
| VRT | ALMOST DEPLOYABLE | TRUST BLOCKED (partial) | workflow_state=WATCH; no human-validated entry band; FP-1 |
| CAT | ALMOST DEPLOYABLE | WATCH / REVIEW NEEDED | days_to_earnings=-1; post-earnings review not complete; FP-3 |
| ETN | ALMOST DEPLOYABLE | ALMOST DEPLOYABLE with NEAR-EARNINGS CAUTION | Earnings in 4 days; stale band warning; FP-5 |
| AMZN | BLOCKED | BLOCKED (but stale — review post-Apr-29 print) | FP-2: earnings block may be stale; post-earnings review needed |
| GOOG | BLOCKED | BLOCKED (but stale — review post-Apr-29 print) | FP-2: earnings block may be stale; post-earnings review needed |
| MSFT | BLOCKED | BLOCKED (but stale — review post-Apr-29 print) | FP-2: earnings block may be stale; post-earnings review needed |
| LMT | DO NOT TOUCH | DO NOT TOUCH (confirmed) | below_stop=true; repair mode |
| RTX | DO NOT TOUCH | DO NOT TOUCH (confirmed) | below_stop=true; below all MAs |
| BRK.B | DO NOT TOUCH | DO NOT TOUCH + NEAR-EARNINGS CAUTION | below all MAs; earnings in 1 day unconfirmed |
| XOM | WATCH | WATCH (confirmed) | No entry band; post-May-1 earnings requalification pending |

**Highest-confidence morning call:** JPM is the only name that survives trust-override review in a constructive state. It is not DEPLOYABLE NOW (still above band), but it is the sole legitimate monitor candidate for a pullback entry.

---

## 7. Operator decisions required before Phase 1

The following cannot be resolved by contract definition alone. Operator judgment is required:

1. **GS false positive — confirm or reject promotion path.** Should GS be allowed into ALMOST DEPLOYABLE pending a thesis-depth review? Or does it stay WATCH until a full deployment-grade note exists? This determines whether Phase 1 includes GS as a near-term candidate.

2. **Post-Apr-29 earnings review for AMZN, GOOG, MSFT.** These prints happened. The blocks are stale. Before Phase 1 re-evaluates these names, a post-earnings review note must be written and their states formally updated. Phase 1 cannot assess these names without that review.

3. **CAT post-earnings state.** CAT reported 2026-04-30. No note exists for the post-earnings setup. Is it a bench/repair case, or does the setup still hold? This must be answered before CAT is treated as anything but WATCH.

4. **ETN earnings timing and sizing decision.** Earnings are in 4 days. The near-earnings caution rule limits sizing. Does the operator want to accept reduced-size pre-print exposure in ETN, or is the correct call to wait for the May 5 print? This is a deployment decision, not a contract question.

5. **Macro trust remediation priority.** FedWatch (CME 404) and manual Fed target are degrading macro gate confidence. Is fixing FedWatch sourcing a near-term priority, or is manual maintenance acceptable for the current deployment cycle? This affects Phase 3 scope.

6. **NEAR-EARNINGS CAUTION threshold.** This contract uses 7 days as the near-earnings caution window. Is 7 days the right threshold, or does the operator want a different window (e.g., 5 days or 10 days)?

---

## 8. What Phase 1 should do

Phase 1 (Current-stack audit) should:
- Audit each artifact in Section 4 against the contract criteria above
- Identify where existing artifacts already support readiness per this contract, and where they mislead
- Produce a gap list: what machine-layer changes are needed to surface trust-override state visibly
- Identify the minimum set of morning artifacts that would support a reliable human deployment decision under this contract

Phase 1 should not:
- Change any canonical note
- Change any script behavior
- Treat any current "DEPLOYABLE NOW" machine state as confirmed without passing through this contract's trust-override table

---

*This document is the Phase 0 deliverable for the Capital Deployment Readiness project.*
*All definitional. Nothing executed.*
*Do not proceed to Phase 1 without operator confirmation and resolution of the seven operator-decision items in Section 7.*
