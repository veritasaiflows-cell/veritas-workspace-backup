# WF65 Claude Final Hardening Pass Prompt

## Role
You are the independent hard-judgment reviewer for WF65 - Fundamental Metrics Tracker V1. Do not edit files unless Randall/Veritas explicitly asks for an implementation pass. Treat this as a read-only challenger review.

## Goal
Audit the completed WF65 V1.5 official bank-capital supplement and autonomy hardening for false-green risk, stale evidence risk, authority creep, and dashboard/control-surface drift.

## Files/artifacts to inspect
- `scripts/bank_native_sec_concept_probe.py`
- `scripts/fundamental_metrics_refresh.py`
- `scripts/validate_fundamental_metrics.py`
- `scripts/dashboard_payload.py`
- `scripts/dashboard-js/07a-fundamentals.js`
- `scripts/test_dashboard_acceptance.py`
- `scripts/chain_manifest.py`
- `scripts/current_window_artifact_index.py`
- `data/fundamentals/company-ir-metadata.json`
- `tmp/bank-native-sec-concept-probe.json`
- `tmp/fundamental-metrics-current.json`
- `tmp/fundamental-metrics-validation.json`
- `tmp/dashboard-data.json`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/current-window-artifacts.json`
- `03. Portfolio/Execution Board.md`
- `06. Playbooks/Active Workflows.md`
- `06. Playbooks/Project Continuity/Workflow 65 - Fundamental Metrics Tracker V1.md`

## Known intended state
- Authority is review-only. No canonical note mutation, portfolio mutation, deployment entitlement, owner approval inference, sizing/sleeve/cash/risk-rule change, brokerage/account action, paper/live order, or trade authority.
- SEC companyfacts probe remains partial for banks; CET1 and Tier 1 risk-based ratios are manual-source fields, not SEC-companyfacts-derived fields.
- JPM official manual-confirmed capital evidence:
  - CET1 risk-based: 14.3% Standardized / 14.1% Advanced; primary/binding = Advanced 14.1%.
  - Tier 1 risk-based: 15.2% Standardized / 15.1% Advanced; primary/binding = Advanced 15.1%.
  - TBV/share: official 108.87, overriding the prior SEC-companyfacts proxy.
- GS official manual-confirmed capital evidence:
  - CET1 risk-based: 12.5% Standardized / 13.3% Advanced; primary = Standardized/lower reported 12.5%.
  - Tier 1 risk-based: 14.1% Standardized / 15.1% Advanced; primary = Standardized/lower reported 14.1%.
  - Tier 1 leverage ratio: 5.9%, separate and explicitly NOT risk-based.
- Populated bank risk-based ratios must require `manual_confirmed` trust, official source URL/section/period, and `risk_based_capital_no_derived_ratio=true`.
- Tier 1 leverage / SLR must never substitute for CET1 or Tier 1 risk-based ratios.
- Chain manifests should run `bank_native_sec_concept_probe.py --write` before `fundamental_metrics_refresh.py` in morning, post-close, post-earnings, and Sunday windows.
- `bank_native_sec_status` should be `partial` for JPM/GS rows with SEC-resolved bank fields; dashboard payload should expose `bankNativeSecStatus=partial`.
- Validator should fail critical if SEC-resolved bank rows are missing probe/payload timestamps or if the bank-native probe is more than 15 minutes older than the fundamentals payload; a probe timestamp newer than the payload may remain a rerun warning.
- Current proof should be: fundamental validator 0 critical / 2 warnings (`BRK.B`, `XOM` SEC conflicts); targeted stale-probe mutation returns critical `bank_native_probe_stale` for JPM and GS; dashboard validation 0 critical / 1 expected NVDA event-risk warning; dashboard acceptance 26/26; current-window artifact index ok 38/38.

## Audit questions
1. Does any code still fake, derive, or backfill CET1/Tier 1 risk-based ratios from capital/RWA, leverage ratio, yfinance, or SEC-companyfacts proxies?
2. Are JPM/GS official values correctly sourced and clearly separated by framework/basis?
3. Is JPM TBV/share now official/manual-confirmed, and is GS TBV/share still clearly not official manual-confirmed?
4. Does dashboard wording avoid saying official confirmed risk-based ratios are still manual-required while still preserving review-only/manual-source posture?
5. Do validators catch missing/untrusted official bank ratios, missing source URL, missing no-derived guard, stale probe, bank-inappropriate industrial FCF anomalies, and leverage-ratio substitution?
6. Does chain/autonomy ordering plus validator critical behavior prevent fundamentals from quietly using stale or missing bank-native probe evidence?
7. Do continuity/control surfaces preserve JPM/GS execution blockers and avoid implying deployment readiness?
8. Are any new artifacts or dashboard fields acting as a second source of portfolio truth?

## Required output
Return:
- Verdict: PASS / PASS WITH GAPS / FAIL
- Critical blockers, if any
- Warning-grade gaps, if any
- Specific file/line or artifact-path evidence
- Recommended smallest safe fixes
- Explicit authority verdict: whether any trade/account/portfolio/deployment authority widened

Do not conclude PASS if any populated CET1/Tier 1 risk-based field can be traced to a derived calculation or leverage proxy instead of official manual-confirmed source metadata.
