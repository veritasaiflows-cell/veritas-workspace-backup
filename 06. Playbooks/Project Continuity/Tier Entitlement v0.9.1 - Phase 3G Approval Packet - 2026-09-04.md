# Tier Entitlement v0.9.1 — Phase 3G Approval Packet

- **Prepared**: 2026-09-04, Veritas Main
- **Owner decision required**: Randall
- **Status**: proposal only. No scheduler, contract, or payload was mutated in preparing this packet.
- **Authority requested**: recurring-contract payload cutover from a hardcoded 18-ticker scope to the guarded-SQL dynamic Tier A+B scope. Nothing else.

---

## 1. Correction to the earlier framing

I previously described 3G as wiring the dynamic scope into the recurring contracts, which implied a scheduler/payload change. That is not accurate, and the difference changes the decision.

**In all three consumers, the dynamic scope is resolved and gated but never drives the ticker list.**

| Module | `--dynamic-entitlement-scope` behavior today |
|---|---|
| `run_alerts_recommendations_chain.py:651-667` | Preview/gate only. Prints scope, `return`s before `stage_plan()`. Never executes a run. |
| `alert_level_freshness_controller.py:930-945` | Preview/gate only. `return`s before `build_payload()`. |
| `analyst_consensus_refresh.py:932-970` | Gate is enforced inside the real execution path, but `tickers` is never replaced by the scope members. `build_artifact(tickers)` still uses the explicit `--tickers` list. |

So 3G is an **implementation phase across three modules plus contract updates**, not a configuration flip. Adding flags to the cron payloads today would either produce a preview-and-exit no-op (chain, freshness) or enforce a gate that changes nothing (analyst consensus).

---

## 2. Current state evidence

**Dynamic scope resolves cleanly.** Live preview at 2026-09-04:

- count 32 — Tier A 15, Tier B 17
- source `guarded_sql:universe_membership.tier`
- fingerprint `2acd2c9c41a7798b7fb9456953d1cf6f8fed693044e27184ad72f184598cc07c`
- overflow 0, integrity breaches 0

The fingerprint is unchanged from the first bounded provider run on 2026-09-03, so scope is stable.

**Hardcoded scope in production is 18 names**, duplicated in two places:

- `run_alerts_recommendations_chain.py:75-78` (`ALERT_TICKERS`)
- `alert_level_freshness_controller.py:59-62` (`TRACKED_TICKERS`)
- plus the literal `--tickers` list in the weekly analyst-consensus contract payload

**Standing provider policy** (`state/dynamic-entitlement-provider-policy.json`, approved 2026-09-02 15:17 MST): enabled, components `analyst_consensus` and `alert_level_freshness`, provider `yfinance` only, max scope 128, max 2 attempts per member, 900s run cap, 400 provider calls/day, fail-closed on exhaustion.

**Gate origin allowlist** is `{"phase3f_dynamic_entitlement"}` (`finance_sql_canon_access.py:247`). All CLI defaults are `ad_hoc`, which fails closed.

---

## 3. Affected recurring contracts — five, not four

Earlier continuity notes say four. The live count is five.

| Contract | Schedule (Phoenix) | Current scope source |
|---|---|---|
| `finance-weekday-morning-review-refresh` | 06:05 Mon–Fri | `ALERT_TICKERS` (18) |
| `finance-intraday-ticker-data-repair-controller` | `*/15` 06:00–13:59 Mon–Fri | `ALERT_TICKERS` (18) |
| `finance-weekday-post-close-review-refresh` | 13:20 Mon–Fri | `ALERT_TICKERS` (18) |
| `finance-sunday-weekly-alerts-recommendations-chain` | 08:00 Sun | `ALERT_TICKERS` (18) |
| `finance-weekly-analyst-consensus-evidence-refresh` | 15:30 Mon | literal `--tickers` (18) |

---

## 4. Provider-load analysis

**yfinance (governed by the standing policy).** The only component that actually calls a provider today is `analyst_consensus_refresh`. A grep of `alert_level_freshness_controller.py` finds no provider call sites at all, so the policy's allowance for that component is forward-looking rather than active. Weekly analyst consensus at 32 names × up to 2 attempts = **64 calls/week against a 400/day budget**. Comfortable.

**Alpaca (NOT governed by this policy).** The chain's quote path uses `intraday_quote_snapshot_proof.py` against Alpaca, which the dynamic entitlement policy does not cover. `fetch_snapshots` batches all symbols into a single request, so 18 → 32 names changes symbols-per-request, not request count. Load impact is negligible.

**Gap worth naming (verified 2026-09-04):** the Alpaca read path has no daily call budget or ledger equivalent to the yfinance one. A grep of `intraday_quote_snapshot_proof.py` for `reserve_provider_calls`, `daily_budget`, and any ledger reference returns nothing — the standing policy's `allowed_providers` is `["yfinance"]` only, so this path is genuinely outside its envelope rather than implicitly covered.

What *is* enforced on that path is authority, not volume: paper-named market-data credentials only (`ALPACA_PAPER_API_KEY_ID` / `ALPACA_PAPER_API_SECRET_KEY`), `GET`-only with POST/PATCH/PUT/DELETE blocked, and a `live_brokerage_endpoint_detected` tripwire that raises `BlockedRun` (`intraday_quote_snapshot_proof.py:206-209`). Note the tripwire tests the module's own constant URL, so it guards against a future edit to `DATA_BASE_URL` rather than against caller input.

So the asymmetry is a **rate/cost governance** gap, not a capital or account-authority gap. It is read-only and batched, which is why it has not bitten. Closing it would mean extending the standing policy to a second provider — an owner decision, not something to infer from this packet.

---

## 5. The real blocker: 3G before 3D adds 14 non-actionable names

The 14 names the cutover would add are exactly the ones the review contract lists as coverage gaps:

- **Tier A (5)**: CME, ITA, LIN, META, PH
- **Tier B (9)**: BKNG, ECL, GE, KTOS, NFLX, SMCI, TMUS, VMC, WMB

Phase 3D observed coverage (`tmp/tier-entitlement-v091-phase3d-observed-coverage.json`) reports **reference_level 0 of 32 observed, lineage 0 of 32, freshness 0 of 32, recommendation_card 0 of 32**, and the attention queue at 32 `no_owner_surface`. The 18 active names carry bands from human canon in `03. Alerts and Recommendations/`; the 14 additions do not.

**Consequence:** cutting over now expands the loop to 32 names of which 14 can produce no band-entry, invalidation, or no-chase signal. They would sit permanently in freshness-review or monitor-only state, adding noise to every digest without adding decision value, and diluting the signal in the daily Telegram message.

---

## 6. Recommendation

**Do not approve the 3G cutover yet.** Sequence it after reference-level provisioning for the 14 additions. Approving it now buys a larger ticker count and a worse digest.

Recommended order:

1. **3D-lite**: provision reference bands, invalidation levels, and source lineage for the 14 gap names. This is the load-bearing work and it is owner-judgment heavy — bands and invalidation thresholds are yours to accept.
2. **3G implementation**: replace the preview-only branches in the three modules with a real dynamic-scope execution path, behind the existing gate, with the hardcoded lists removed.
3. **3G cutover**: update the five contract payloads. Separate approval.
4. **3H**: one market-week burn-in and acceptance.

If you would rather see scope breadth sooner, a defensible middle path is to cut over **analyst consensus only** — it is weekly, well inside budget, has a real execution path already, and consensus evidence is useful for the 14 names even before they have bands. That is a materially smaller decision and I can bring it as its own one-page gate.

---

## 7. Rollback

Every step is reversible. Contract payloads are versioned in `state/cron-contracts/` with drift comparison on `payload.argv`; reverting means restoring the prior argv and re-running contract validation. The module changes are ordinary source edits under git. The gate origin allowlist stays unchanged, so reverting `--scope-origin` to `ad_hoc` fails closed to today's behavior with zero provider calls.

## 8. What this packet does NOT request

No capital, order, brokerage, account, or money-movement authority. No paper or live execution. No guarded-SQL tier or membership writes (that remains Phase 4). No canon mutation. No config, auth, credential, network, channel, or runtime change. No external or public delivery. Owner approval is not inferred for any of these.
