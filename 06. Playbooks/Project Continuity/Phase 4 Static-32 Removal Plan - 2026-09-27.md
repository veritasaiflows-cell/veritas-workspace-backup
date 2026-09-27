# Phase 4 Static-32 Removal Plan - 2026-09-27

Status: **accepted 2026-09-27 (late morning Phoenix); repaired on GitHub branch `operating-procedure-spine`. The Windows host must pull this branch before the Sat 10-03 09:00 renewal, or it runs the unrepaired `65c20533` copy.** Randall accepted the Muse Spark builder code as-is, waived further external QA, and directed that implementation and QA for this work stay with Claude in the GitHub session. Claude repaired both open HIGH QA findings with regression tests (see "Acceptance and repair" below). History: applied to the workspace 09:36-09:42 by lane PHASE4-DYNAMIC-SCOPE-20260927; GPT-5.6 Sol QA failed three rounds on those two findings; the implementer ran Muse Spark, not the owner-named GPT-6 Sol. Owner direction: Randall, WebChat 2026-09-27 ~08:17, "continue and prepare to remove the static 32-name list" and ~08:40 "use GPT5.6 Sol for QA and GPT6-Sol for Implementation work". Parent record: `Phase 4 Tier Promotion and Demotion Design - 2026-09-07.md` (addendum 2026-09-23, "Static assumptions that must be removed").

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
| S7 | `scripts/finance_sql_canon_access.py:602-605, 1222-1225` (found 2026-09-27 after acceptance) | The SQL guard requires exactly 200 `reference_levels` rows, 200 `evidence_freshness` rows and a 200-row baseline pin | Not part of the 32-name scope; the renewal is unaffected. It blocks D3: inserting a row for any of the 100 universe names without one fails the guard until the contract changes. |

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

## Acceptance and repair - 2026-09-27 (Claude, GitHub session)

Owner decision (Randall): "Proceed with all open items. Approved to accept code from Muse Spark as is and no need to rerun additional QA. Since we are in GitHub repository, all QA and implementation stays with Claude here. Proceed as recommended."

Repairs (both HIGH findings from QA round 3):

- **PRIOR_AUDIT_NONREGULAR_STALE_FALLBACK** (`scripts/weekly_band_renewal.py` `_prior_applied_names`). A symlink, directory, broken link or non-calendar date named like `<date>-applied.json` now stops the run at `needs_owner_review` ("applied audit record is invalid: ..."). Before, it was skipped and the name list was compared against an older renewal. The live audit directory holds only regular files (`2026-09-23-gate_passed_not_applied.json`, `2026-09-25-applied.json`), so the 10-03 run is unaffected. Replaced two tests that asserted the old fallback; 5 new tests fail on the pre-repair code.
- **UNSCOPED_VARIABLE_APPLY_BYPASSES_SCOPE_VERIFICATION** (`scripts/g6_yahoo32_sql_apply.py` `run_apply`). Every apply now needs a matrix scope block, a matching `--expected-scope-fingerprint`, a scope count equal to the batch, and `--verify-live-scope`, all checked before backup. `validate_apply_artifact` also rejects an apply record that is not scope- and live-verified. The unscoped legacy apply path is gone; dry runs stay permissive. The weekly renewal already passes every flag. Test fixtures now carry scope blocks and run the CLI through a test-only live-scope shim. The shim is embedded in the test files, so production code has no bypass hook.

Proof (Linux cloud checkout, 2026-09-27 ~11:40 Phoenix):

- `python -B scripts/test_g6_yahoo32_sql_apply.py`: 125/125 (4 new; `unverified_apply_refused_unscoped` and `_no_live_check` fail on pre-repair code with rc=0).
- `pytest scripts/test_weekly_band_renewal.py scripts/test_g6_dynamic_scope.py scripts/test_g6_hermetic_full_chain_packet.py scripts/test_alert_reference_baseline_freshness_guard.py`: 73 passed, 46 subtests. `test_yahoo_reference_level_matrix.py`: 24 OK. `test_alert_event_ledger.py` and `test_yahoo_daily_gap_repair.py`: 24 passed.
- Offline end-to-end on a scratch copy of the live canon (live file never opened for write):
  - dynamic scope is 32 (15 A + 17 B), identical to the 09-25 applied renewal's names, so the scope-change stop will not fire on 10-03;
  - an unflagged `--apply` was refused with the database unchanged;
  - a verified dry run reported 32 triples, 0 drift, no mutation;
  - a verified apply passed `apply_valid`;
  - `--rollback` was byte-exact.
- Caveat for this check only: the checkout stores `data/finance/universe-v1.json` with LF endings and lacks the uncommitted `tmp/sql-canon-consumer-migration-backlog.json`, so the guard's lineage-hash check was patched in-process to hash the CRLF form. The Windows host is unaffected.
- Not run here: the live Yahoo matrix (the cloud network policy denies `query1.finance.yahoo.com`). The first real proof is the Sat 10-03 09:00 Option B run.

D2 (scope-change stop) is now enforced, as Randall's 08:48 amendment to `state/finance/standing-approvals/band-renewal-option-b.json` anticipated.

**D3 is blocked by S7 and not built.** An insert-capable onboarding writer cannot pass the guarded-SQL contract, which is fixed at exactly 200 reference, evidence and pin rows. Onboarding also needs `evidence_freshness` rows and 5 + 4 lineage rows per name. No consumer exists yet: promotion needs the per-name tier writer (P4-2), which still waits on the scorer-readiness gate. Recommendation: build D3 together with a guard-contract change in the P4-2 lane. The new rule would say reference rows are a subset of the universe, the pin row count equals the reference row count, and every evaluated name has a row. Until then, a promoted name without a row stays monitor-only. Changing the guard contract needs Randall's explicit word.
