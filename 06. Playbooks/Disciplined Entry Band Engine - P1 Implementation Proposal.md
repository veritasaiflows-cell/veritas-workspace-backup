# Disciplined Entry Band Engine — P1 Implementation Proposal

**Status:** PROPOSAL — review-only, owner-gated. No code written, no SQL/schema mutation, no canon change. Actual build opens only on Randall's approval.
**Owner:** Veritas main session
**Requested by:** Randall — 2026-08-18 ("proceed with default recommendations")
**Parent spec:** `06. Playbooks/Disciplined Entry Band Engine Spec.md` (§8 P1)
**Lane:** `DISCIPLINED-BAND-ENGINE-P1-20260818`
**Authority class:** `finance_sensitive` + `owner_gated` — SQL canon schema change via the gated-apply path only.

---

## 0. Confirmed owner decisions (spec §10, accepted 2026-08-18)

1. **Extension auto-drop threshold:** fixed **8%** primary; ATR distance reported as secondary flag. *(P2 — informs schema fact columns only in P1.)*
2. **Staleness alert:** BOTH, OR-combined — band age **> 30 days** OR price **> 2 ATR** from band midpoint. *(P2.)*
3. **Ratchet policy:** **hard-cap by default** (disciplined band cannot rise faster than the 200-day) **+ explicit owner-override** through the `entry_band` gate. *(P3.)*
4. **Build order:** **P1 alone, first.** ← this proposal.
5. **Valuation overlay:** out of v1; purely technical/structural. Valuation stays an explicit later option (P4).

Only decision 4 is in scope for this proposal. The others are recorded so P1's schema leaves clean seams for P2/P3.

## 1. What P1 fixes — grounded in live state (verified 2026-08-18)

| Finding | Evidence |
|---|---|
| `reference_levels` is a **single flat band** table — one band per ticker, no tracking/disciplined separation. | Schema: `reference_price_low/high`, `reference_invalidation_level`, `reference_band_status`, one `authority_class`. |
| **All 200 rows are currently sourced from `tmp/band-proposals.json`** (the Keltner/MA tracking/reclaim band). | `SELECT authority_class, COUNT(*)` → 200 rows all `reference_metadata_review_only_no_deployment_authority`, `source_artifact_path='tmp/band-proposals.json'`. |
| AMD's canon row = **469.87–501.89** (reclaim band), **not** the written **295.33–342.53**. | Live row, `source_generated_at_utc=2026-08-18T13:46:13Z` — today's cron overwrote it again. |
| The disciplined/written band exists **only outside SQL** — `tmp/entry-band-data/<TICKER>.json → preferred_band` and the Technical Entry & Invalidation Sheet markdown. | AMD `preferred_band` = `{low:295.33, high:342.53, stop:271.73, set:"2026-05-06"}`. |

**Net:** SQL canon holds **no disciplined band at all**. Because the review pipeline reads `reference_levels`, canon presents the price-chasing band as if it were the buy zone. That is the root of the AMD churn, stated precisely.

## 2. Scope — P1 only

Additive two-band schema + honest labeling + disciplined backfill + daily-write enforcement. **No** new engine (P3), **no** extension auto-drop (P2), **no** valuation (P4).

### 2.1 Schema (additive, low churn)
Keep the existing `reference_*` columns **as the explicit tracking band** (they already hold `band-proposals` values). Add disciplined-band columns:

- `disciplined_band_low`, `disciplined_band_high`, `disciplined_stop` — REAL
- `disciplined_levels_set_at` — TEXT (owner-set date, e.g. AMD 2026-05-06)
- `disciplined_level_trigger` — TEXT (event that last moved the levels; audit)
- `disciplined_source_artifact_path` — TEXT
- `disciplined_authority_class` — TEXT, constant `canonical_written_band`
- `prior_disciplined_json` — TEXT (append-only prior value on any change)

**Rationale:** additive avoids breaking the 17 `reference_levels` consumers. Renaming `reference_*`→`tracking_*` is deferred to avoid churn; the label is documented instead.

### 2.2 Labeling fix
- `reference_*` columns documented + labeled as **tracking / alert-only** authority.
- `disciplined_*` columns = **canonical written band** the no-chase gate binds to.
- Repoint the buy-zone read in `portfolio_mutation_proposal_generator.py` and `daily_review_objects.py` to `disciplined_*`; `reference_*` (tracking) informs only "getting close" proximity, never the deploy decision.

### 2.3 Backfill
Populate `disciplined_*` from `tmp/entry-band-data/<TICKER>.json → preferred_band` (last owner-set written values), carrying `set` date and source path. Fallback order: `preferred_band` → Technical Entry & Invalidation Sheet → flag `NEEDS_OWNER_BAND` (no silent guess).

### 2.4 Daily-write enforcement (the core discipline guarantee)
Patch `reference_levels_derived_refresh_apply.py` so the daily refresh writes **only** the tracking (`reference_*`) + fact columns. Make it **structurally incapable** of writing `disciplined_*`. Disciplined levels move **only** through the `entry_band` gate (`auto_apply_entry_band_maintenance.py`) with a logged trigger. This is what stops the daily cron from ever re-chasing the disciplined band the way it does today.

## 3. Surfaces

**Write (build lane):**
- New schema migration script (additive columns; backup + rollback packet).
- New disciplined-band backfill script (source: `entry-band-data` `preferred_band`).
- Patch `reference_levels_derived_refresh_apply.py` (+ `_dry_run`) — exclude `disciplined_*` from daily writes.
- Repoint consumer reads: `portfolio_mutation_proposal_generator.py`, `daily_review_objects.py`.

**Reuse (no duplication):**
- `tmp/entry-band-data/*.json` `preferred_band` — backfill source of truth.
- `auto_apply_entry_band_maintenance.py` — the existing bounded `entry_band` apply gate for any disciplined level change.
- `reference_levels_derived_refresh_apply.py`'s existing backup / transaction / rollback-packet pattern — reuse for the migration.

**Read-first (build lane):** `reference_levels` schema, the `derived_refresh_apply` + `_dry_run` pair, and the two consumers above.

## 4. Validators / acceptance proof (build-lane exit criteria)

1. **Schema migration** applies with backup + rollback packet + post-apply validation (reuse `derived_refresh_apply` pattern). Rollback drill proven.
2. **Backfill proof:** AMD `disciplined` = 295.33–342.53 stop 271.73 (`set 2026-05-06`); `tracking` = 469.87–501.89. Both present, correctly labeled; no ticker silently guessed.
3. **Enforcement proof:** daily refresh dry-run asserts `disciplined_*` byte-unchanged after a run.
4. **Consumer proof:** no-chase gate reads AMD as **+50% above the disciplined band (ABOVE_BAND_WAIT)**, not `NEAR_BAND` — the churn is gone at the read layer.
5. **Authority proof:** `capital_deployment_approved=false`, `trade_or_execution_approved=false` throughout; SQL mutation only via the gated-apply path.

## 5. Adjacent blocker — flagged, NOT absorbed into P1

Today's 06:47 MST cron reported an **apply-count discrepancy on this exact `reference_levels` apply path**: 4 execution-eligible reported vs 2 explicit execution-band records in the audit artifact; audit records dry-run / no SQL write, so no canonical change was confirmed. That is an **audit/apply reconciliation integrity bug**, separate from labeling. Recommend a small **separate hygiene lane** to reconcile the count — P1 must not silently swallow it. Flagging so it stays tracked.

## 6. Authority boundary (unchanged)

Review-only proposal. The actual build lane opens **only** on Randall's explicit go. Schema/canon changes run through the gated-apply path (scoped proposal, diff/preview hash, standing-approval artifact, validator proof, backup/rollback, post-apply validation, audit trail). No capital deployment, trade, paper, brokerage, account, or money-movement authority; no approval inferred from this document.

## 7. Recommended route

Router run (`project_implementation_router.py`, preflight/proposed, no dispatch) → `tmp/disciplined-band-engine-p1-route.json`.

- **Router default route:** `persistent_isolated_agent` (Terra) for the bounded build (schema migration + backfill + enforcement patch). It **fails closed** — status `blocked` pending a **fresh workspace-local transport proof**, which must be established at build time before dispatch. No silent Main fallback.
- **Main-owned steps:** the authority-sensitive **gated apply to canon** and **final QA/integration** stay on Main regardless of where the bounded build runs.
- **Split at build time:** either (a) establish fresh Terra transport proof → dispatch the bounded schema/backfill/patch to a persistent isolated agent → Main does the gated apply + acceptance proof (§4); or (b) justify Main-only for the whole lane as authority-sensitive. Decide when the build lane opens.

## 8. Hand-off / continuity

- **Deliverable:** this proposal (review-only). No code, no SQL, no canon mutation.
- **Blocked on:** Randall's approval to open the P1 build lane, plus route confirmation (§7).
- **On approval:** open `DISCIPLINED-BAND-ENGINE-P1-20260818` build lane, lease the exact write surfaces (§3), execute through the gated-apply path with the §4 acceptance proof.
- **Separately:** the §5 apply-count reconciliation as its own hygiene lane.
