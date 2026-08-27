# Cron Reduction and Efficiency Audit - 2026-06-17

## Executive Judgment

Cron is operationally healthy, but oversized. Live scheduler proof shows 79 total jobs, 51 enabled jobs, and 28 disabled jobs. The current control layer is clean: cron control status is `ok`, escalation is `0`, blocked is `0`, stale is `0`, and contract drift is `0`.

The blunt finding: 51 enabled jobs is too many. The count is not excessive because the intelligence is bad; it is excessive because the system is scheduling individual proof fragments, handoffs, and status checks as separate jobs instead of scheduling a smaller number of deterministic phase runners.

Reducing to roughly half is possible without losing intelligence, but not by simply disabling 25 jobs today. The safe path is:

1. Consolidate duplicate handoffs and control checks first.
2. Build combined morning, midday, post-close, delivery, and runtime runners.
3. Shadow-run and compare proof artifacts.
4. Disable replaced jobs through `cron_patch_manager.py` only after validators stay clean.
5. Archive disabled clutter separately after owner approval.

Recommended enabled-job target: 25 to 27 jobs. Conservative first cut: 38 to 42 jobs. Final half-size target requires runner consolidation.

## Scope And Proof

Commands used:

```powershell
python scripts\cron_control_packet.py --write --validate
python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate
openclaw cron list --all --json
python scripts\concurrent_lane_manager.py --status --write --validate
```

Current proof:

| Surface | Result |
|---|---:|
| Total live cron jobs | 79 |
| Enabled cron jobs | 51 |
| Disabled cron jobs | 28 |
| Cron control status | ok |
| Escalation signals | 0 |
| Blocked cron signals | 0 |
| Stale cron signals | 0 |
| Requires-attention signals | 2 |
| Live scheduler last-run exceptions | 0 |
| Contract validator | ok |
| Contract drift | 0 |
| Missing contracts | 0 |
| SQL-canon cron health | ok |
| OTEL health | ok |

No cron schedule, config, auth, channel, runtime, portfolio, canon, paper/live, brokerage/account, money movement, or external-delivery mutation was performed by this audit.

## Current Enabled Job Shape

| Bucket | Enabled jobs | Audit read |
|---|---:|---|
| Finance Refresh/Review | 12 | Useful intelligence, but too fragmented across morning, post-close, layered audits, research, ticker-card, Sunday, and canon checks. |
| Runtime/Ops | 11 | Too many separate control and carry-forward surfaces. Several can merge into greenkeeper/control digest. |
| Finance Delivery Series | 7 | Strong merge candidate. Builder/handoff split creates extra jobs. |
| WF78/Tier A Routing | 6 | Important, but silent Tier A probes and owner-review proof can be consolidated after wrapper proof. |
| WF85 Paper/Alerts | 4 | Keep quality, reduce separate morning/midday card/radar jobs after combined paper review runner exists. |
| WF87 Autonomy/Paper | 3 | Merge into morning/midday paper/autonomy runners. |
| WF68 Alerts | 2 | Merge producer and grouped handoff once digest contract is unified. |
| WF67/WF86 Paper Read/Reconcile | 2 | Merge into one paper-state/reconciliation runner. |
| Macro | 1 | Keep as a stable single-command Mini wrapper. |
| Learning/Greenkeeper | 1 | Candidate to merge with nightly runtime digest after proof. |
| Other | 2 | Weekly analyst/printable intelligence should stay, but Sunday surfaces can combine. |

Model distribution:

| Model path | Enabled jobs | Audit read |
|---|---:|---|
| `openai/gpt-5.4` | 21 | Too many full-model jobs. Keep for finance/paper/radar quality until consolidated wrappers prove stable. |
| `openai/gpt-5.4-mini` | 20 | Good direction for deterministic wrappers. Still too many separate invocations. |
| Main/system events | 7 | Mostly handoffs. Biggest low-risk clutter class. |
| Spark | 3 | Keep only bounded proof/canary/control digest work; do not expand. |

## Waste Classes Found

1. Handoff split waste: Several jobs only wake main after a builder already wrote artifacts. These can be folded into the builder output plus the PM/main-session dispatcher.

2. Control-plane duplicate checks: Auto-green watchdog, operating leverage trigger, morning control digest, post-close control digest, layered audits, SQL coverage guard, and weekly OS maintenance overlap in what they refresh or inspect.

3. Market-hours over-fragmentation: The morning cluster separately runs Tier A silent readiness, WF85 radar, paper cards, WF87 fresh gate, WF87 command center, and delivery builder. The midday/post-close cluster repeats the pattern.

4. Builder/handoff duplication: Finance Delivery Series has daily, weekly, and monthly builders plus separate handoffs. That is 7 jobs for a surface that should be 3 jobs.

5. Disabled-job clutter: 28 disabled jobs do not cost daily runtime, but they increase audit noise and rollback ambiguity. Several are obsolete one-shots, old alert senders, disabled canaries, and retired main-session handoffs.

6. Tool-call waste inside agent-turn jobs: Some jobs correctly call a wrapper, but others still ask the model to run multiple commands. Jobs should generally invoke one deterministic wrapper command and let the wrapper own internal sequencing.

## Reduction Target

| Stage | Enabled count target | Reduction | Description |
|---|---:|---:|---|
| Current | 51 | 0 | Operationally clean, too many enabled jobs. |
| Phase 1: low-risk handoff/control consolidation | 38 to 42 | 9 to 13 | Disable/merge duplicated handoffs and control-plane checks after one clean combined digest. |
| Phase 2: market/paper runner consolidation | 29 to 32 | 19 to 22 | Replace morning/midday paper, Tier A, WF85, WF87, WF68 fragments with 3 to 4 phase runners. |
| Phase 3: delivery/runtime cleanup | 25 to 27 | 24 to 26 | Merge delivery series, runtime digest, future-session, WF74/OTEL, and weekly guard surfaces. |

Half-size target is realistic. The safe target is 26 enabled jobs. The hard stop is proof parity: do not remove a job until its replacement keeps the same critical artifacts fresh.

## Proposed Target Architecture

Cron should schedule operating windows, not every artifact.

Recommended final enabled inventory:

| Target job group | Proposed jobs | Notes |
|---|---:|---|
| Premarket finance inputs | 4 | Macro, sector/matrix, morning finance chain, WF78 daily core. |
| Morning market/paper review | 2 | One market readiness/paper radar/card runner plus optional WF68 alert producer if material alerts remain separate. |
| Midday market/paper review | 2 | One midday radar/card/autonomy runner plus optional alert digest if not folded into WF68. |
| Post-close finance/current state | 4 | Post-close finance chain, research freshness, ticker-card/current-state, post-close control digest. |
| Runtime/continuity | 5 | OTEL retention, OTEL/local digest, future-session packet, main-session dispatcher, security/runtime hardening. |
| Weekly/monthly/deep review | 8 to 10 | Analyst consensus, weekly/monthly delivery, weekly OS/cron authority, Sunday printable/research reset, canon/SQL coverage, cleanup dry-run, improvement radar. |
| Total | 25 to 27 | Keeps intelligence, reduces fragmented wakeups. |

## Job-Level Disposition

Legend:

- Keep: preserve until a specific replacement exists.
- Merge: create a consolidated runner, shadow-run, then disable replaced jobs.
- Retire: disable after confirming no unique output remains.
- Cadence: reduce frequency or fold into weekly/monthly runner.

| Current enabled job | Cadence | Disposition | Replacement / action |
|---|---|---|---|
| Runtime - OTEL Collector Log Retention | Daily 03:30 | Keep | Single-command Mini wrapper is appropriate. |
| Macro - Energy and Geopolitical Inputs Refresh | Daily 05:35 | Keep | Already repaired into deterministic Mini wrapper. |
| Finance - Sector Allocation Decision Matrix | Weekdays 05:58 | Merge later | Fold into premarket finance input runner after macro/sector parity proof. |
| Finance - Weekday Morning Review Refresh | Weekdays 06:05 | Keep | Core approved morning chain. Do not cut before replacement proof. |
| Finance - WF78 Daily Freshness and Promotion Proof | Weekdays 06:08 | Keep | Core WF78/WF84/WF85 freshness proof. |
| Finance - Layered Morning Advancement Audit | Weekdays 06:15 | Merge | Fold into morning control digest or morning finance runner. |
| Finance - WF78 Open-Ready Owner Review Proof | Weekdays 06:20 | Merge | Fold into morning market/paper consolidator after artifacts match. |
| Runtime - Future Session Packet Refresh | Daily 06:30,18:30 | Cadence | Reduce to once nightly plus closeout-triggered refresh, or fold into main dispatcher/closeout. |
| Finance - Silent Tier A Intraday Market Readiness Probe | Weekdays 06:42 | Merge | Fold into morning market readiness/paper consolidator. Preserve silent/no-delivery behavior. |
| Finance - WF85 Paper Deployment Telegram Radar | Weekdays 06:42 | Merge | Keep two-paper-radar intent, but consolidate with readiness/card runner. |
| Finance - WF87 Market-Hours Fresh Gate Probe | Weekdays 06:45,11:45 | Merge | Fold into morning and midday paper/autonomy consolidators. |
| Finance Delivery Series - Daily Market Read Builder | Weekdays 06:50 | Merge | Combine with daily delivery handoff; possibly source from morning finance chain. |
| Finance - WF87 Autonomy Command Center Refresh | Weekdays 06:50,11:50 | Merge | Fold into paper/autonomy consolidators. |
| Finance Delivery Series - Daily Market Read Handoff | Weekdays 06:58 | Retire after merge | Builder should write the handoff packet; main dispatcher should pick it up. |
| Cron - Main Session Auto-Green Watchdog | Daily 07:10,14:10 | Merge | Combine with operating-leverage check and PM dispatcher into one main action controller. |
| Finance - Morning Control Digest Proof Refresh | Weekdays 07:12 | Merge | Combine with post-close control digest as one generic control digest runner. |
| Finance - Silent Tier A Confirmation Market Readiness Probe | Weekdays 07:14 | Merge | Fold into morning readiness runner; no separate job unless first-hour volatility proves necessary. |
| Operating Leverage - Escalation Trigger Check | Weekdays 07:15,14:15 | Merge | Fold into auto-green/main action controller. |
| Finance - Morning Paper Deployment Recommendation Cards | Weekdays 07:18 | Merge | Fold into morning market/paper consolidator. |
| PM - Main Session Continuation Dispatcher | Daily 07:20,14:20 | Keep as target | This should become the main pickup job that absorbs watchdog/operating leverage checks. |
| Finance - WF68 Intraday Alert Producer | Weekdays 08:05 | Merge later | Keep until WF68 producer and grouped digest have one contract. |
| Finance - Sunday Weekly Printable Intelligence Refresh | Sunday 08:00 | Merge | Combine with Sunday research reset and weekly delivery output. |
| Finance Delivery Series - Monthly Direction and Deep Dive Builder | First Saturday 08:30 | Merge | Combine monthly builder and handoff into one monthly delivery job. |
| Finance Delivery Series - Monthly Handoff | First Saturday 08:45 | Retire after merge | Monthly builder should produce handoff packet. |
| Finance - Sunday Generated Artifact Cleanup Dry Run | Sunday 09:15 | Cadence | Keep weekly, but fold into WF76/weekly OS maintenance if output is only cleanup candidates. |
| Finance - Sunday Research Opportunity Reset | Sunday 09:35 | Merge | Combine with Sunday printable/weekly reset job. |
| Finance - Main Session Sunday Weekly Artifact/Note Sync Handoff | Sunday 09:55 | Retire after merge | Should be absorbed by Sunday weekly packet plus main dispatcher. |
| Finance - WF85 Post-Refresh Paper Deployment Telegram Radar | Weekdays 11:30 | Merge | Fold into midday market/paper consolidator while preserving two scheduled radar windows. |
| Finance - Midday Paper Deployment Recommendation Cards | Weekdays 11:55 | Merge | Fold into midday market/paper consolidator. |
| Finance - Silent Tier A Late-Session Market Readiness Probe | Weekdays 12:07 | Merge | Fold into midday/late-session market readiness runner. |
| Finance - WF68 Grouped Alert Digest Handoff | Weekdays 13:10 | Merge | Fold with WF68 producer or post-close digest once alert contract is unified. |
| Finance - Weekday Post-Close Review Refresh | Weekdays 13:20 | Keep | Core approved post-close chain. |
| Finance - WF63/WF67 Paper Position Read-Only Refresh | Weekdays 13:50 | Merge | Fold into paper-state/reconciliation runner with WF86. |
| Finance - Ticker Card Freshness Owner Runner | Weekdays 13:55 | Merge later | Fold into post-close current-state runner after ticker-card freshness proof. |
| Finance - Research Freshness and Opportunity Review | Weekdays 14:05 | Merge later | Fold into post-close current-state runner after proof. |
| Finance - WF86 Daily Shadow and Paper Reconciliation | Weekdays 14:36 | Merge | Fold with WF63/WF67 paper position refresh. |
| SQL Coverage - Daily Control Plane Guard | Friday 14:55 | Merge | Fold into WF76 weekly cron/OS maintenance or weekly SQL/canon guard. |
| Finance - Daily Canon Drift Freshness Gate | Daily 15:00 | Cadence | Reduce to post-close/weekend depending on canon-drift risk; keep proof quality. |
| Finance - Post-Close Control Digest Consolidated Handoff | Weekdays 15:12 | Merge | Become generic morning/post-close control digest runner, or absorb layered post-close audit. |
| Finance - Layered Post-Close Advancement Audit | Weekdays 15:20 | Merge | Fold into post-close control digest. |
| Finance - Autonomy Spine Readiness Rollup | Weekdays 15:25 | Merge | Fold into WF87 command center or post-close control digest. |
| WF77 Weekly Analyst Consensus Refresh - Tier A/B Review | Monday 15:30 | Keep | Useful weekly external-consensus refresh. |
| Runtime - Weekly OS Improvement Radar Proof Refresh | Sunday 16:20 | Merge | Combine with weekly OS improvement review or WF76. |
| Runtime - Weekly OS Improvement Radar Review | Sunday 16:30 | Retire after merge | Handoff/review job should be folded into proof refresh plus main dispatcher. |
| Finance Delivery Series - Weekly Market Read Builder | Sunday 17:05 | Merge | Combine with weekly performance builder and weekly handoff. |
| Finance Delivery Series - Weekly Performance Builder | Friday 17:20 | Merge | Fold into one weekly delivery builder unless Friday timing is materially required. |
| Finance Delivery Series - Weekly Handoff | Sunday 17:15 | Retire after merge | Weekly builder should write handoff packet. |
| Security Audit - Daily Bounded Hardening | Daily 17:10 | Cadence | Move to 3x/week or fold daily lightweight check into runtime digest; keep weekly full proof. |
| WF76 - Weekly Cron Authority and OS Maintenance | Sunday 18:05 | Keep as target | This should absorb SQL coverage, weekly improvement radar, and cleanup dry-run if proof allows. |
| WF74 - Learning Loop Telegram Digest | Daily 18:15 | Merge later | Fold with runtime learning/OTEL digest if user-facing digest quality is preserved. |
| Ops - OTEL Local Digest | Daily 21:40 | Merge / Mini migrate | Keep output quality, simplify to daily profile and move to Mini one-command wrapper; optionally combine WF74 runtime learning summary. |

## Highest-Value Consolidations

### 1. Finance Delivery Series: 7 jobs to 3 jobs

Current enabled jobs:

- Daily Market Read Builder
- Daily Market Read Handoff
- Weekly Market Read Builder
- Weekly Performance Builder
- Weekly Handoff
- Monthly Direction and Deep Dive Builder
- Monthly Handoff

Target:

- `Finance Delivery Series - Daily Builder and Handoff`
- `Finance Delivery Series - Weekly Builder and Handoff`
- `Finance Delivery Series - Monthly Builder and Handoff`

Expected savings: 4 enabled jobs.

Quality requirement: builder writes the human digest, machine JSON, and main-session handoff marker in one run.

### 2. Control Plane: 8 to 3 or 4 jobs

Current overlap:

- Main Session Auto-Green Watchdog
- Operating Leverage Escalation Trigger Check
- Morning Control Digest Proof Refresh
- Post-Close Control Digest Consolidated Handoff
- Layered Morning Advancement Audit
- Layered Post-Close Advancement Audit
- SQL Coverage Guard
- Weekly OS Improvement Radar Review/Proof pair

Target:

- `Main Session Action Dispatcher` twice daily
- `Cron Control Digest Runner` morning/post-close
- `WF76 Weekly Cron/OS/SQL Authority Maintenance`
- Optional `Security Runtime Hardening` if kept separate

Expected savings: 5 to 7 enabled jobs.

Quality requirement: `cron_control_packet`, `pm_control_packet`, `main_session_greenkeeper_controller`, `cron_contract_validator`, and `changed_file_validator_router` remain fresh from the consolidated path.

### 3. Market/Paper Cluster: 13 jobs to 4 jobs

Current cluster:

- Silent Tier A intraday, confirmation, and late-session probes
- WF85 morning and midday Telegram radar jobs
- Morning and midday paper deployment cards
- WF87 fresh gate and command center
- WF63/WF67 paper position refresh
- WF86 shadow and reconciliation
- WF68 producer and grouped digest

Target:

- `Morning Market Readiness and Paper Review Consolidator`
- `Midday Market Readiness and Paper Review Consolidator`
- `Post-Close Paper State and Shadow Reconciliation`
- `WF68 Alert Producer and Digest`

Expected savings: 8 to 9 enabled jobs.

Quality requirement: preserve no-delivery silent probes, preserve exactly bounded Telegram radar behavior, preserve WF67 paper-only guardrails, preserve no execution authority, and preserve artifact freshness for WF85/WF87/WF86/WF63.

### 4. Runtime/Continuity: 6 to 3 or 4 jobs

Current overlap:

- Future Session Packet Refresh twice daily
- WF74 Learning Loop Telegram Digest
- Ops OTEL Local Digest
- OTEL Collector Log Retention
- Security Daily Bounded Hardening
- Weekly OS Improvement Radar pair

Target:

- `OTEL Collector Log Retention`
- `Runtime Learning and OTEL Digest`
- `Future Session Packet Refresh` once nightly and closeout-triggered
- `Security/OS Weekly Maintenance` plus lightweight daily check inside runtime digest

Expected savings: 2 to 4 enabled jobs.

Quality requirement: keep OTEL digest quality but reduce internal tool fanout via daily/full profiles.

## Disabled Job Cleanup

The 28 disabled jobs are not active runtime waste, but they are audit and rollback noise. They should be handled after enabled-job consolidation.

Priority archive/delete candidates, after explicit owner approval and rollback proof:

- Old main-session handoffs replaced by consolidated control digest:
  - Main Session Morning Artifact/Note Sync Handoff
  - Main Session Post-Close Artifact/Note Sync Handoff
  - Main Session Research Opportunity Sync Handoff
  - Main Session Sunday Research Opportunity Sync Handoff
  - Main Session WF68 Intraday Alert Handoff
- Old send-capable Tier A opportunity probes replaced by silent probes:
  - Tier A Intraday Opportunity Probe
  - Tier A Confirmation Opportunity Probe
  - Tier A Late-Session Opportunity Probe
- Old open-ready paper/Telegram duplicates:
  - Open-Ready Paper Deployment Recommendation Cards
  - WF85 Open-Ready Telegram Radar
  - WF68 Telegram Shadow Alert Notifier
- Failed canaries and obsolete one-shots:
  - GPT54mini canary jobs with error status
  - old reminders/rollback one-shots
  - stale WF67 one-shot reconciliation jobs
- Paused product-lane jobs:
  - WF75 weekly builder/handoff should remain disabled unless WF75 resumes.

Cleanup path must use the DB lifecycle/archive discipline: reference review, backup/rollback, validator proof, and owner approval before delete/archive.

## Proposed Implementation Plan

### Phase 0: Freeze And Instrument

Do not disable more jobs until consolidation wrappers exist.

Add a generated `cron_reduction_inventory` proof surface that records:

- enabled count
- disabled count
- grouped jobs
- candidate replacement runner
- required output artifacts
- current replacement status
- validator commands

Acceptance:

```powershell
python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate
python scripts\cron_control_packet.py --write --validate
```

### Phase 1: Low-Risk Handoff And Control Reduction

Build or update:

- `scripts\cron_control_digest_runner.py`
- `scripts\finance_delivery_series_consolidated_runner.py`
- `scripts\runtime_ops_consolidated_digest.py`

Then disable replaced handoff/control jobs through `cron_patch_manager.py`.

Expected result: 51 enabled to 38-42 enabled.

### Phase 2: Market/Paper Consolidators

Build:

- `scripts\morning_market_paper_consolidated_runner.py`
- `scripts\midday_market_paper_consolidated_runner.py`
- `scripts\postclose_paper_reconciliation_runner.py`
- optional `scripts\wf68_alert_digest_consolidated_runner.py`

Run shadow comparisons for at least one market day:

- compare WF85 radar artifacts
- compare paper recommendation card artifacts
- compare WF87 command/fresh-gate artifacts
- compare WF63/WF86 paper-state artifacts
- compare WF68 alert digest artifacts
- confirm Telegram delivery count and content are unchanged where delivery is intended

Expected result: 38-42 enabled to 29-32 enabled.

### Phase 3: Runtime And Weekly Cadence Cleanup

Reduce:

- future-session packet from twice daily to once nightly plus closeout-triggered
- daily security hardening to lightweight daily plus weekly full proof, or 3x/week if acceptable
- daily canon drift to post-close/weekend cadence if drift history supports it
- OTEL local digest to daily Mini profile plus weekly full profile
- Sunday research/printable/reset into one weekly intelligence reset

Expected result: 29-32 enabled to 25-27 enabled.

### Phase 4: Disabled Job Archive

After 7 clean days on the reduced set:

- archive obsolete disabled jobs
- keep only rollback candidates with current descriptions
- remove failed canaries and one-shot residue after reference review

This reduces total visible scheduler clutter, not just enabled count.

## Validation Gates Before Each Disable

Every reduction batch must pass:

```powershell
python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\cron_signal_scorecard.py --write --validate
python scripts\escalation_trigger.py --write --validate
python scripts\cron_control_packet.py --write --validate
python scripts\pm_control_packet.py --write --write-db --validate
python scripts\main_session_greenkeeper_controller.py --refresh-frontdoors --write --validate --append-ledger
python scripts\changed_file_validator_router.py --write --validate
```

Critical post-disable checks:

- enabled count moves down as expected
- contract drift remains 0
- missing expected artifact contracts remains 0
- stale/blocked/urgent cron counts stay 0
- paper/live/account authority remains blocked
- no Telegram alert duplication returns
- no finance card/radar/readiness artifact loses freshness
- PM/control closeout remains green or warning-only with known governance warnings

## What Not To Cut Blindly

Do not blindly disable:

- Weekday Morning Review Refresh
- Weekday Post-Close Review Refresh
- Macro Energy and Geopolitical Inputs Refresh
- WF78 Daily Freshness and Promotion Proof
- WF85 paper radar jobs before consolidated radar parity exists
- WF63/WF67 and WF86 paper-state jobs before paper reconciliation parity exists
- WF68 alert producer before grouped digest parity exists
- OTEL collector log retention

These jobs carry real signal or safety coverage. They can be merged, but only after replacement proof.

## Efficiency Rules Going Forward

1. One cron job should call one deterministic wrapper command.
2. Wrapper scripts may run multiple internal proof commands, but should emit one machine JSON status and one operator action.
3. Handoff jobs should not exist if the producer can write a handoff packet and the main dispatcher already scans it.
4. Market-hours finance jobs should be windowed by purpose: premarket, morning, midday, post-close.
5. Delivery and digest builders should own their own handoff metadata.
6. Disabled jobs should have a retention date, rollback reason, and archive decision.
7. Mini should own deterministic wrapper runs where output is proof/summary. Full GPT-5.4 should remain only where synthesis quality materially matters.
8. Spark should stay bounded to exact proof/canary/control digest work, not broad finance or tool-heavy jobs.

## Recommendation

Proceed with cron thinning as an implementation project, not a manual cleanup.

Best next action:

1. Build the Phase 1 consolidated control/delivery runners.
2. Shadow-run them once.
3. Apply a dry-run cron patch plan showing which jobs will be disabled and which new jobs replace them.
4. If proof is clean, approve the first disable batch.

Expected first approved batch should reduce enabled jobs from 51 to about 40 without intelligence loss. The final 25-27 target is achievable after market/paper consolidators prove artifact parity for one clean market day.

## Boundary

This audit is review and implementation planning only. It does not authorize cron schedule mutation, config/auth/channel/runtime mutation, destructive cleanup, portfolio/canon mutation, capital deployment, paper/live execution, brokerage/account action, money movement, customer/public delivery, or owner approval inference.
