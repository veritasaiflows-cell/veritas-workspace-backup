# Phase 4 Static-32 Removal Plan - 2026-09-27

Status: **applied to the live workspace 2026-09-27 ~09:36-09:42 by the PHASE4-DYNAMIC-SCOPE-20260927 lane (uncommitted; independent GPT-5.6 Sol QA verdict FAIL after 3 rounds with two HIGH findings open; NOT Main-accepted; implementer ran Muse Spark despite the owner-named GPT-6 Sol).** Owner direction: Randall, WebChat 2026-09-27 ~08:17, "continue and prepare to remove the static 32-name list" and ~08:40 "use GPT5.6 Sol for QA and GPT6-Sol for Implementation work". Parent record: `Phase 4 Tier Promotion and Demotion Design - 2026-09-07.md` (addendum 2026-09-23, "Static assumptions that must be removed").

## Conclusion

Removing the list is **behavior-neutral today**. The guarded-SQL dynamic entitlement returns exactly the same 32 names as the hard-coded list: 15 Tier A, 17 Tier B, 0 eligibility debt, and no symmetric difference (read-only probe, 2026-09-27 ~08:26 Phoenix). The work is code-only. It needs no canon, tier, schedule or config write. It does need one owner decision on the Option B gate (D2 below), and it should run through the approved proposal route (isolated slices plus independent QA), not Main-authored edits. That follows the 09-26 builder-incident rule, and the per-name writer is the next owner decision in the parent record.

## Inventory of static-32 assumptions

| # | Surface | What is hard-coded | Effect if scope changes |
|---|---|---|---|
| S1 | `scripts/yahoo_reference_level_matrix.py:24` | `SCOPED_TICKERS` (the 32), plus `YAHOO_SYMBOLS = {"BRK.B": "BRK-B"}` | Contract mode (`selected != SCOPED_TICKERS`, lines 616-628, 692-694, 761-824) refuses any other scope. A promoted name gets no band; a demoted name keeps being renewed. |
| S2 | `scripts/g6_yahoo32_sql_apply.py:67` | `EXPECTED_TRIPLE_COUNT = 32`, used in `extract_triples` (336), `validate_apply_artifact` (1376-1383) and the CLI summary check (1605); `rows=32` literals in output (1647, 1657) | The apply refuses any batch that is not exactly 32. |
| S3 | `scripts/yahoo_reference_evidence_collector.py:21` | A duplicate `SCOPED_TICKERS`, and refusal of unscoped tickers (260, 304) | Evidence collection only. Not called by the renewal or chain (no script imports it). Low priority. |
| S4 | `scripts/finance_sql_canon_access.py:1560-1561` | Default reporting envelope `phase3_initial_32` / `32` for `dynamic_entitlement_scope()` | This is a reporting envelope and never truncates. Default-argument callers are the controller (1042), analyst consensus (898, 915, 973), chain (109) and question router (115). They would report `overflow_tickers` once scope exceeds 32. `phase3f_external_canary_approval.py:479` treats overflow as a refusal; `phase3g_dynamic_execution.py:176` checks against the policy cap of 128. |
| S5 | `scripts/tier_entitlement_phase3d_observed_coverage.py:536,627` | `envelope_count=32` default | Historical Phase 3d coverage tool. Reporting only. |
| S6 | Tests | `test_g6_yahoo32_sql_apply.py` (fixture N=32, about 75 references), `test_yahoo_reference_level_matrix.py` (8), `test_yahoo_reference_evidence_collector.py` (4) | Most references are fixture sizes; the scope tests must change with S1-S2. |

Already dynamic, no change: the recurring chain and controller scope (`run_alerts_recommendations_chain.py` with `policy.max_scope_count = 128`), nightly gap repair, the alert-event ledger, and `weekly_band_renewal.py`, which takes whatever scope the matrix produces.

## Proposed design (diff proposal, not applied)

1. **One scope source (S1, S3).** Replace `SCOPED_TICKERS` with `resolve_band_scope(db)`, which calls `FinanceSqlCanonAccess(db).dynamic_entitlement_scope(envelope_name="band_renewal", envelope_count=policy.max_scope_count)`.
   - Fail closed on `DynamicEntitlementScopeError`, an empty scope or any overflow.
   - Take Yahoo symbols from `membership.yfinance_symbol` rather than a static map.
   - Stamp `scope_fingerprint`, `tier_breakdown` and the sorted ticker list into the matrix.
   - Contract mode requires the selected names to equal the resolved scope. `--ticker` stays a diagnostic.
2. **Variable-count apply with scope proof (S2).** Remove `EXPECTED_TRIPLE_COUNT`. At apply time, recompute the dynamic scope and refuse if:
   - the matrix lacks `scope_fingerprint`;
   - its fingerprint differs from the current one (scope moved between generation and apply); or
   - its tickers differ from the scope memberships.
   Keep **UPDATE-only**: a scoped name with no `reference_levels` row is refused. `validate_apply_artifact` checks `triple_count == len(before_rows) == len(recorded scope)`, and output prints the real count.
3. **Renewal audit.** `weekly_band_renewal.py` records the scope fingerprint and ticker diff against the last applied renewal in its packet and audit record.
4. **Reporting envelopes (S4, S5).** Change the default envelope to `None` (report the full scope) or to the policy cap. Before changing, prove each default-argument caller treats overflow as reporting only. The canary's overflow refusal stays.
5. **Tests.** Add cases for scopes of 31 and 33, fingerprint mismatch, scope change between dry run and apply, a scoped name missing from `reference_levels`, and a demoted name no longer renewed. Also prove the current 32 produce a byte-identical matrix ticker set.

## Owner decisions needed

- **D1: implementation route.** The recommendation is the accepted proposal route: an isolated implementation slice, independent QA, and Main integration, with leases on the three scripts and their tests. It can be bundled into the per-name transactional writer lane (P4-2) the parent record already names as the next decision. Doing both together avoids touching `g6_yahoo32_sql_apply.py` twice.
- **D2: Option B condition for scope changes.** The standing grant covers renewal "for the evaluated scope" and excludes "adding or removing names from scope". Once the list is dynamic, the renewal follows tier changes made elsewhere. The recommendation is a new auto-apply condition: *if the scope fingerprint differs from the last applied renewal, stop for owner review.* The first renewal after any promotion or demotion is then always reviewed, and a promoted name's first band never auto-applies. This amends the standing gate, so it needs Randall's words.
- **D3: rows for names outside the 200.** Promoting a name with no `reference_levels` row needs an INSERT-capable onboarding gate. That path does not exist and is out of scope here. Until it does, such a promotion stays monitor-only.

## Validation plan (when executed)

`python -B scripts/test_g6_yahoo32_sql_apply.py`, `python -B scripts/test_yahoo_reference_level_matrix.py`, `python -B -m pytest -q scripts/test_weekly_band_renewal.py scripts/test_g6_hermetic_full_chain_packet.py scripts/test_alert_reference_baseline_freshness_guard.py`, and a no-write dry run of the renewal on a canon copy that shows the same 32-name set and zero drift. There is no live apply outside the normal Saturday Option B run.

## Not granted by this plan

Tier changes, promotion or demotion, canon writes, schedule/config/runtime changes, thesis acceptance, capital, orders, accounts, execution, or external delivery.
