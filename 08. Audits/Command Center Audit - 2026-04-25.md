# Command Center Audit — 2026-04-25

**Auditor:** Claude (independent review layer per `CLAUDE.md`)
**Scope:** `tmp/veritas-command-center.html`, `scripts/generate_dashboard.py`, `scripts/dashboard-template.html`, full `scripts/` chain, `tmp/*.json` state, vault hygiene relative to the dashboard pipeline.
**Method:** Direct read of all generator and chain scripts; cross-check of every `tmp/*.json` artifact; live execution of `scripts/test_dashboard_acceptance.py` and `scripts/validate_dashboard_state.py`; vault-staleness pass on the dashboard-feeding notes.
**Prior reference:** `08. Audits/2026-04-22-dashboard-command-center-audit.md` (score 6.7/10 with three remediation phases).

---

## 1. Executive bottom line

The Command Center has materially improved since the 2026-04-22 audit. Phase 1 (trust repair) and most of Phase 2 (architecture repair) of that prior plan are now real code, not intentions. The validation framework is doing its job, the trust panel surfaces manual dependencies clearly, the acceptance test suite has six cases and they all pass, and `exec_freshness` correctly degrades to `usable_with_caution` when manual maintenance is owed.

This is now a credible operating console. It is not yet a high-trust unattended decision surface. Three concrete defects are actively misleading, and four structural gaps remain before this earns the right to be called complete.

**Revised score: 7.6 / 10.** Up from 6.7. The remaining 2.4 points are concentrated in delta honesty, watchlist-drift surfacing, chain-gating, and session-aware freshness.

**Conviction: High** that the three Priority 1 defects below are real and exploitable. **Medium** that the Priority 2 enhancements would meaningfully change behavior; they are quality investments, not crises.

---

## 2. What is now demonstrably working

- `generate_dashboard.py` v5 produces `dashboard-data.json`, `dashboard-delta.json`, `dashboard-validation.json`, and the rendered HTML in one pass with explicit logging.
- `assess_source()` correctly downgrades market and earnings to `usable_with_caution` because of manual Fed dependency and timing-sensitive earnings alerts; portfolio-config to `usable_with_caution` because it is human-maintained.
- `build_validation()` runs eight families of contradiction checks (posture vs MA flags, close vs claimed MA, computed vs reported `inBand`, computed vs reported `belowStop`, deployment-summary vs records, portfolio sums to 100%, single-position cap, sector concentration) and produces a structured warnings list with severity, scope, and ticker.
- The acceptance test suite covers missing field, partial upstream, stale source, posture/band contradiction, earnings-date change visibility, and a clean state-transition. All six pass on the live state.
- `validate_dashboard_state.py --strict` is wired to exit non-zero on critical issues; `2` for critical, `1` for warning, `0` clean.
- The `triggerToday` semantic gap from the prior audit is closed: ETN, JPM, NVDA all show `actionState=ALMOST` with `triggerToday=False` because they are extended above their bands. The "Wait for better price" label is honest.
- The Trust panel surfaces five manual dependencies with the right detail prose. Stop discipline correctly reads `bad — LMT below stop`. Sector concentration shows Tech at 30% of a 35% threshold. Cash 20% of a 5% minimum.
- The `dashboard-template.html` no longer renders missing numeric values as `0.00`. Spot-check confirmed `${esc(t.close ?? '—')}` and `value != null` patterns throughout.

---

## 3. Priority 1 — defects that mislead the operator now

### 3.1 The delta summary lies. Fix immediately.

`tmp/dashboard-delta.json` currently reads:

```json
"changes": [
  {"type": "new_ticker", "ticker": "RTX"},
  {"type": "new_ticker", "ticker": "CAT"},
  {"type": "new_ticker", "ticker": "GS"}
],
"summary": "No material changes"
```

The dashboard's overview alert renders this as `"Changes since last run — No material changes."` while the underlying state shows three new coverage names. That is actively misleading prose on the most-watched panel.

Root cause: `compute_delta()` in `generate_dashboard.py` enumerates only nine specific change types when building the human summary string and excludes `new_ticker`, `earnings_date_change`, `source_status_change`, and `exec_freshness_change`. The detection loop produces those changes; the summary loop ignores them.

**Fix:** add the missing types to the summary parts loop, and add a final fallback so the function never says "No material changes" while `len(changes) > 0`. One unit test in `test_dashboard_acceptance.py`: insert a new ticker in `technical-refresh.json`, regenerate, assert summary contains "new ticker".

Severity: **critical** for trust. Code change is < 15 lines.

### 3.2 Earnings "NEW" alerts never surface as manual dependencies.

`tmp/earnings-calendar.json` produced seven watchlist alerts. Three of them (LMT, NVDA, BRK.B) are `DATE CHANGED` and the dashboard correctly bubbles them into `trust.manual_dependencies`. The other four (RTX, NOC, PLTR, SMCI) are `NEW -- not in vault watchlist` and are silently dropped from manual deps.

Concrete consequence: NOC is a defense name that just reported (next print 2026-07-21). The vault's Event Calendar has no entry for it, the Trust panel shows it nowhere, and the only place this appears in the rendered Command Center is buried at the bottom of the Earnings tab. A new earnings reality is entering the system without operator acknowledgement.

Root cause: `build_payload()` filters `watchlist_alerts` to `"DATE CHANGED" in alert` only. The "NEW" branch was never wired.

**Fix:** treat both `DATE CHANGED` and `NEW` as unconfirmed dependencies, with separate `status` values (`unconfirmed_change` vs `unconfirmed_addition`) so the UI can color them differently.

Severity: **critical** for vault-script alignment, which is exactly the boundary CLAUDE.md is supposed to defend.

### 3.3 Trigger Sheet `catalyst_blocker` carries stale prose.

The current ETN trigger sheet record reads:

```
catalyst_blocker: "Treat the unresolved Apr 30 to May 5 earnings window as timing-sensitive until directly confirmed"
```

`next_earnings_date` for ETN is now `2026-05-05` as a single confirmed date (or at least, single yfinance date). The "unresolved Apr 30 to May 5 window" prose is leftover from when the earnings date was disputed between two sources. The trigger-sheet generator hardcodes this human-style language; once written, it does not update unless a person rewrites it.

This is a textbook drift surface: the script-backed JSON layer is supposed to match what the human-authored vault layer believes, and stale prose embedded in the script artifact undermines that contract.

**Fix:** in `trigger_sheet_refresh.py`, derive `catalyst_blocker` text mechanically from `(next_earnings_date, days_to_earnings, earnings_calendar.watchlist_alerts)` so the sentence regenerates from data each run. Drop the hardcoded "Apr 30 to May 5" language entirely.

Severity: **warning** for trust calibration, but bears on every catalyst_blocker for every coverage name, not just ETN. This is a quiet integrity drift channel.

---

## 4. Priority 2 — structural gaps worth closing on the next pass

### 4.1 Silent coverage drop in `earnings_calendar_enrichment.py`.

CAT is in the script's `COVERAGE` map but not in `tmp/earnings-calendar.json` records. There is no warning surface saying "CAT was attempted and skipped." The script's failure log says `Fetch errors (0): none`. Either yfinance returned an empty earnings-date payload and the script silently filtered the record out, or the script's append logic only writes records when a date exists and never tracks the gap.

**Fix:** in `earnings_calendar_enrichment.py`, always append a record per coverage ticker, with `next_earnings_date=None` and a `note` field if the fetch produced no usable date. Add a watchlist alert for any coverage name that returned no date for two consecutive runs. This converts a silent gap into a flagged degradation, which is exactly what the prior audit's Phase 1 was supposed to enforce.

### 4.2 The chain does not gate on validation.

`run_finance_refresh_chain.py` runs `validate_dashboard_state.py --write` but does not fail the chain on a non-zero exit. The validator can return 1 (warning, with `--strict`) or 2 (critical) and the chain still publishes the dashboard.

**Fix:** make the chain fail when validation returns 2 (critical) by default, and fail on 1 (warning) under a `--strict` flag. Better still: add a final acceptance gate that runs `test_dashboard_acceptance.py` before the dashboard HTML is written. Acceptance failure should rename the previous good HTML to `tmp/veritas-command-center.last-good.html` and block the write rather than overwrite a working surface with a broken one.

### 4.3 No session-aware freshness.

This is the largest unaddressed item from the 2026-04-22 audit. Today is Saturday 2026-04-25; market-state was generated at 2026-04-25T00:01 UTC, so the data is roughly 22 hours old, but the underlying close is still `last_trade_date=2026-04-24` (Friday). On a Saturday, that is fine. On Monday morning at 9:25 ET, a 22-hour-old market-state file would be operationally stale even though it is under any of the current age thresholds.

**Fix:** introduce a `market_session_state` field with values `closed`, `pre_open`, `open`, `post_close`, `weekend` derived from current ET time. Adjust the `stale_after_hours` threshold dynamically:
- weekend / closed: existing thresholds
- pre_open or open: tighter thresholds (e.g. 4h for market data)
- post_close: same-day thresholds

Surface session-state as a pill in the header so the operator instantly knows whether the dashboard's age window is being interpreted in trading-hours mode or off-hours mode.

### 4.4 No vault freshness audit inside the dashboard.

`HEARTBEAT.md` defines a finance staleness check across the canonical notes, but the Command Center does not surface it. The script layer ignores the vault layer entirely. When `Macro Regime Dashboard.md` has not been updated in seven days while macro is moving, nothing in the Command Center says so.

**Fix:** add a `vault_freshness` payload block to `generate_dashboard.py` that walks the canonical notes (`02. Markets/Macro Regime Dashboard.md`, `03. Portfolio/Portfolio Snapshot.md`, etc.), reads file mtimes, parses any `Last updated:` line, and produces a per-note status. Render in a small "Vault sync" card on the Overview tab. This closes the loop CLAUDE.md insists on: scripts and vault are not allowed to drift apart.

### 4.5 Posture expectations still hardcoded in Python.

`posture_expectations` in `build_validation()` is a literal dict in `generate_dashboard.py`. The prior audit's principle was to push business semantics into config. This dict is small, but it is the same drift channel.

**Fix:** move to `tmp/portfolio-config.json` under a new `posture_expectations` key, fall back to the existing dict if the config field is absent.

---

## 5. Priority 3 — enhancements that change the operating loop

### 5.1 Persist a rolling `deployment-history.json`.

`dashboard-last.json` is overwritten every run. There is no way to reconstruct how the deployment board evolved across the last five trading days without reading prior commits. A weekly history file written on each `post-close` run would let you compute multi-day deltas, build a "names that have been ALMOST for 4+ sessions but never deployed" view, and add genuine memory to the system.

### 5.2 A "What changed" tab.

Even with the Priority 1 delta-summary fix, the delta data is buried in the Overview alert. Promote it to its own tab with structured panels:
- "New on the board" (new tickers, new earnings dates)
- "Crossed the band today" (entered/exited band)
- "Lost the stop" (entered below_stop)
- "Cleared a blocker" (earnings passed)

This is the prose Veritas should be reading at session start anyway. Surfacing it inside the dashboard reduces the re-derivation tax.

### 5.3 Vault-side close-the-loop hooks.

When the Command Center detects an earnings DATE CHANGED alert, the operator should be one click away from the vault note that owns it. Add a payload field `vault_owner: "05. Intelligence/Event Calendar.md"` per alert and surface it as a link in the Trust panel.

### 5.4 Schema validation on the input layer.

`generate_dashboard.py` is permissive about input shape. A Pydantic model per `tmp/*.json` source would convert today's "default to None and continue" pattern into "fail loudly with a precise error path." Cost is one Python module; benefit is that malformed inputs become loud rather than silent.

### 5.5 A 30-second written brief mode.

The Daily Executive Summary surface is the right home for this, but the Command Center could ship a compact "morning brief" tab generated mechanically from `today_action`, `manual_dependencies`, `delta`, and `validation`. Five paragraphs maximum. Use as a sanity check before reading the canonical notes — if the brief and the notes disagree, the system has drifted.

### 5.6 Footer should show pipeline freshness gap.

Current footer: `Generated 2026-04-25 22:08 UTC from governed tmp artifacts.` The fact that the chain itself ran at 02:19 UTC and only the dashboard generator has been re-rendered since is invisible. Add: `Chain last ran 20.0h ago; only the renderer ran since.` This is the real freshness number; the dashboard's own timestamp can be misleading if only the HTML rebuild was run.

---

## 6. Vault hygiene findings

All canonical notes are inside their stated freshness windows. No file is operationally stale per its own refresh policy. Three observations worth recording:

- `memory/2026-04-25.md` is a four-line entry covering ETN visual report work after midnight. It does not log today's RTX/CAT/GS additions to the technical refresh, the dashboard regeneration at 22:08 UTC, or this audit. Per CLAUDE.md's audit-trail standard, the file modifications driven by this audit should be appended.
- `02. Markets/Macro Regime Dashboard.md` was last meaningfully updated 2026-04-19/20 (file mtime 2026-04-21). Working data points cite 2026-04-17 to 2026-04-20 for Treasury yields. In a quiet macro week this is fine. With FOMC and the Apr 29 earnings cluster five trading days away, expect this to reach the staleness threshold by 2026-04-27.
- `01. Dashboards/Daily Executive Summary/2026-04-24.md` is the most recent daily exec. There is no 2026-04-25 file. Saturday is reasonable to skip, but `01. Dashboards/Monday Game Plan - 2026-04-27.md` already exists and is Monday-anchored. The flow is intact.

---

## 7. Recommended order of operations

If you want to spend time on this in priority order:

1. Fix the delta summary string (Priority 1.1). One commit, < 15 lines, immediate trust improvement.
2. Wire `NEW` watchlist alerts into manual_dependencies (Priority 1.2). One commit, ~10 lines, plus an acceptance-test case.
3. Make `catalyst_blocker` text data-driven in `trigger_sheet_refresh.py` (Priority 1.3). One commit, ~30 lines.
4. Backfill silent coverage drops in `earnings_calendar_enrichment.py` (Priority 2.1).
5. Gate `run_finance_refresh_chain.py` on validator and acceptance-test exit codes (Priority 2.2).
6. Add the `vault_freshness` payload block (Priority 2.4) — this is the most operationally valuable Priority 2 item.
7. Add session-aware freshness (Priority 2.3).
8. Move `posture_expectations` to config (Priority 2.5).
9. Persist `deployment-history.json` and add the "What changed" tab (Priority 3.1, 3.2).

Items 1, 2, 3 should fit in one sprint. Items 4 through 6 are the next sprint. Items 7 through 9 are quality investments worth pacing.

---

## 8. What I am explicitly not recommending

- A larger UI redesign. The current visual hierarchy is solid; the prior audit's 8.2/10 UX score still holds. Polishing visuals before tightening the four remaining truth defects above would repeat the original mistake of looking more finished than the data deserves.
- A move away from the static-HTML rendered model. The single-file artifact is auditable, diffable, and works offline. Switching to a server or React build would buy interactivity and lose review surface. Don't.
- Adding more tabs by default. The Command Center already has nine tabs. New surfaces (vault freshness, what changed, brief mode) should replace or merge with existing ones, not stack.

---

## 9. Acceptance for this audit

This audit is acceptable if:
- Every item in section 3 is reproducible by running the listed scripts and reading the listed JSON paths today (it is).
- The score change from 6.7 to 7.6 is anchored to specific resolved items from the prior audit (sections 2 and 5 of that file map directly to section 2 of this one).
- The recommendations in sections 3 and 4 are concrete enough that an implementer can begin without further clarification.

If the user disagrees with any score, finding, or priority, they should say so directly rather than ask me to soften it. CLAUDE.md is explicit about that.

---

*Last updated: 2026-04-25*
*Written by Claude per the operating mandate in `CLAUDE.md`. Audit logged in `memory/2026-04-25.md`.*
