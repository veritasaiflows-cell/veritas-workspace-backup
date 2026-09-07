# Current Capital-Deployment Recommendation Packets

- Rendered: `2026-08-28T13:24:42Z`
- Source: `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- Source generated: `2026-08-28T13:24:42Z`
- Window: `morning`
- Status: **ok**
- Proposal count: `17`

## Authority

Randall has approved the **portfolio note/model mutation workflow under guardrails**. This report is still a review-only surface: it does not itself apply a packet, infer per-packet owner approval, place trades, touch accounts, or grant execution entitlement.

- Approved scope: main-session standing approval for bounded workspace portfolio note/model/canon maintenance under WF58/WF56 guardrails
- Blocked scope: live trade/account actions, brokerage orders, money movement, and unscoped execution entitlement remain blocked; paper submit/cancel is s...
- Gated note/model mutation allowed by posture: `true`
- Packet apply allowed in this bundle: `false`
- Per-packet owner approval inferred: `false`
- Trade/account action allowed: `false`

## Summary table

| Ticker | Current | Recommendation | Entry-band | Catalyst | Official bridge | Apply? |
|---|---|---|---|---|---|---:|
| AMD | ENTRY POLICY REVIEW | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| BKNG | BENCH | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| BRK.B | BENCH | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| CVX | WATCH / RESEARCH NEEDED | no_new_approval | ABOVE_BAND_WAIT | CLEAR | available_review_only | false |
| ETN | DEPLOYABLE NOW | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| GE | ENTRY POLICY REVIEW | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| ITA | PROMOTION REVIEW | no_new_approval | ABOVE_BAND_WAIT | UNKNOWN | missing_ticker_manual_fallback_required | false |
| JPM | ALMOST DEPLOYABLE | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| LLY | ENTRY POLICY REVIEW | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| LMT | BENCH | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| MSFT | ALMOST DEPLOYABLE | no_new_approval | ABOVE_BAND_WAIT | CLEAR | available_review_only | false |
| NVDA | ALMOST DEPLOYABLE | no_new_approval | ABOVE_BAND_WAIT | CLEAR | available_review_only | false |
| PH | PROMOTION REVIEW | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| PLTR | WATCH / RESEARCH NEEDED | no_new_approval | ABOVE_BAND_WAIT | CLEAR | available_review_only | false |
| VRT | PROMOTION REVIEW | no_new_approval | IN_BAND | CLEAR | available_review_only | false |
| XLB | PROMOTION REVIEW | no_new_approval | ABOVE_BAND_WAIT | UNKNOWN | missing_ticker_manual_fallback_required | false |
| XOM | BENCH | no_new_approval | IN_BAND | CLEAR | available_review_only | false |

## Packet details

### AMD

- Proposal id: `morning:AMD:capital-deployment-review:2026-08-28`
- Current state: ENTRY POLICY REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched_via_period_alias
- Adjusted EPS bridge: official_captured
- Guidance bridge: official_captured
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: AMD surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 295.33-342.53; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: event-driven AI watch
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=official_captured,...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### BKNG

- Proposal id: `morning:BKNG:capital-deployment-review:2026-08-28`
- Current state: BENCH
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: BKNG surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 164.05-170.91; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: Consumer Discretionary Tier 1 research candidate approved for w...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### BRK.B

- Proposal id: `morning:BRK.B:capital-deployment-review:2026-08-28`
- Current state: BENCH
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: BRK.B surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 489.78-498.19; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; Next earnings 2026-11-07 (85d out); workflow stop line is active; blockers: wf85_wait_...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### CVX

- Proposal id: `morning:CVX:capital-deployment-review:2026-08-28`
- Current state: WATCH / RESEARCH NEEDED
- Recommendation posture: no_new_approval
- Entry-band status: ABOVE_BAND_WAIT
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: CVX surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 186.91-196.41; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: secondary energy read-through
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### ETN

- Proposal id: `morning:ETN:capital-deployment-review:2026-08-28`
- Current state: DEPLOYABLE NOW
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: official_captured
- Guidance bridge: official_captured
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: ETN surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 387.67–404.02; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact; owner-gated action Tier 1 explicit add on 2026-05-10 af...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=official_captured,...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; Next earnings 2026-11-03 (81d out); workflow stop line is active; blockers: wf85_wait_...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### GE

- Proposal id: `morning:GE:capital-deployment-review:2026-08-28`
- Current state: ENTRY POLICY REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: GE surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 299.03-311.84; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: promoted 2026-05-15 to machine-tracked aerospace quality / defe...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; workflow stop line is active; dashboard validation has 12 critical issue(s); blockers:...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### ITA

- Proposal id: `morning:ITA:capital-deployment-review:2026-08-28`
- Current state: PROMOTION REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: ABOVE_BAND_WAIT
- Catalyst state: UNKNOWN
- Official earnings bridge: missing_ticker_manual_fallback_required
- SEC reconciliation: -
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: ITA surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 212.15-223.44; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: Owner-promoted 2026-05-18 to review-only paper-candidate queue...
  - official_earnings_reason: Official earnings bridge status is missing_ticker_manual_fallback_required; official evidence=manual_required/review_only; adjusted EPS=m...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: official earnings bridge / IR reconciliation context is missing; manual earnings-quality review required before capital judgment; state-h...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### JPM

- Proposal id: `morning:JPM:capital-deployment-review:2026-08-28`
- Current state: ALMOST DEPLOYABLE
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: JPM surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 304.96–315.95; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact; prior owner approval recorded on 2026-05-07, but curren...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; Next earnings 2026-10-13 (60d out); workflow stop line is active; blockers: wf85_wait_...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### LLY

- Proposal id: `morning:LLY:capital-deployment-review:2026-08-28`
- Current state: ENTRY POLICY REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: LLY surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 907.64-969.88; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: Workflow 7 Healthcare watch-lane pilot — preferred sector leade...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### LMT

- Proposal id: `morning:LMT:capital-deployment-review:2026-08-28`
- Current state: BENCH
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched_via_period_alias
- Adjusted EPS bridge: not_disclosed_in_release
- Guidance bridge: partial
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: LMT surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 548.51-582.27; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact but active model weight suspended while below-stop repai...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=not_disclosed_in_r...
  - risk_blocker_reason: Risk/catalyst blocker context: Catalyst blocker from portfolio-config: Repair mode remains active until a fresh support base forms after...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### MSFT

- Proposal id: `morning:MSFT:capital-deployment-review:2026-08-28`
- Current state: ALMOST DEPLOYABLE
- Recommendation posture: no_new_approval
- Entry-band status: ABOVE_BAND_WAIT
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: sec_lag_wait
- Adjusted EPS bridge: official_captured
- Guidance bridge: not_disclosed_in_release
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: MSFT surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 389.64-412.56; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact; owner-gated action staged manual candidacy recorded on...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=official_captured,...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; Next earnings 2026-10-28 (75d out); workflow stop line is active; blockers: wf85_wait_...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### NVDA

- Proposal id: `morning:NVDA:capital-deployment-review:2026-08-28`
- Current state: ALMOST DEPLOYABLE
- Recommendation posture: no_new_approval
- Entry-band status: ABOVE_BAND_WAIT
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: official_captured
- Guidance bridge: official_captured
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: NVDA surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 202.81–212.23; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact / thesis strengthened by Q1 FY2027 post-earnings officia...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=official_captured,...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; Last earnings reported 2026-05-20; post-earnings review confirmed; next print not yet...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### PH

- Proposal id: `morning:PH:capital-deployment-review:2026-08-28`
- Current state: PROMOTION REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: official_captured
- Guidance bridge: official_captured
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: PH surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 851.36-908.98; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: owner-gated action portfolio-review candidate 2026-05-15; best...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=official_captured,...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; workflow stop line is active; dashboard validation has 12 critical issue(s); blockers:...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### PLTR

- Proposal id: `morning:PLTR:capital-deployment-review:2026-08-28`
- Current state: WATCH / RESEARCH NEEDED
- Recommendation posture: no_new_approval
- Entry-band status: ABOVE_BAND_WAIT
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: PLTR surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 137.37-149.53; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: higher-risk tactical narrative
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### VRT

- Proposal id: `morning:VRT:capital-deployment-review:2026-08-28`
- Current state: PROMOTION REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: VRT surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 300.02–319.13; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: Owner-promoted 2026-05-29 into formal AI-power tactical challen...
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=source_verified_manual_reconciliation_pending/review_only; ad...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; Next earnings 2026-10-21 (68d out); workflow stop line is active; blockers: wf85_wait_...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### XLB

- Proposal id: `morning:XLB:capital-deployment-review:2026-08-28`
- Current state: PROMOTION REVIEW
- Recommendation posture: no_new_approval
- Entry-band status: ABOVE_BAND_WAIT
- Catalyst state: UNKNOWN
- Official earnings bridge: missing_ticker_manual_fallback_required
- SEC reconciliation: -
- Adjusted EPS bridge: manual_required
- Guidance bridge: manual_required
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: XLB surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 49.84-51.68; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: Owner-promoted 2026-05-30 into formal Materials ETF starter-pla...
  - official_earnings_reason: Official earnings bridge status is missing_ticker_manual_fallback_required; official evidence=manual_required/review_only; adjusted EPS=m...
  - risk_blocker_reason: Risk/catalyst blocker context: wf85_wait_no_chase; band proposal remains review-only / non-applyable; workflow stop line is active; block...
  - missing_evidence_reason: official earnings bridge / IR reconciliation context is missing; manual earnings-quality review required before capital judgment; state-h...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

### XOM

- Proposal id: `morning:XOM:capital-deployment-review:2026-08-28`
- Current state: BENCH
- Recommendation posture: no_new_approval
- Entry-band status: IN_BAND
- Catalyst state: CLEAR
- Official earnings bridge: available_review_only
- SEC reconciliation: matched
- Adjusted EPS bridge: not_disclosed_in_release
- Guidance bridge: partial
- Official bridge manual review required: `true`
- Why this is here / why not action yet:
  - setup_reason: XOM surfaced from ranked daily review because current state is ALMOST DEPLOYABLE and recommendation class is no_new_approval.
  - entry_reason: Entry context is ABOVE_BAND_WAIT against configured band 150.24-158.44; this is setup context, not approval.
  - fundamental_reason: WF65 fundamental context status is available_review_only; thesis context: intact long-term, weaker near-term
  - official_earnings_reason: Official earnings bridge status is available_review_only; official evidence=manual_confirmed/review_only; adjusted EPS=not_disclosed_in_r...
  - risk_blocker_reason: Risk/catalyst blocker context: Catalyst blocker from portfolio-config: Keep benched until the next one to two EIA reads plus Hormuz and Q...
  - missing_evidence_reason: state-history / owner-outcome retention is not wired; no predictive outcome score is available; official earnings bridge remains manual-r...
- Owner decision required: `true`
- Packet apply allowed: `false`
- Trade/account action allowed: `false`
- Stop lines:
  - Owner decision required before any portfolio state changes.
  - No canonical note, portfolio, size, sleeve, cash, or account-action mutation is authorized.
  - Recommendation has unresolved blockers or missing evidence.

## Required next step

Use the JSON packet plus validators before any note/model mutation. If an exact apply helper or patch preview is introduced, it must preserve the blocked trade/account boundary and run post-apply validation.
