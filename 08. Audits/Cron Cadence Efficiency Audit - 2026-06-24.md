# Cron Cadence Efficiency Audit - 2026-06-24

## Bottom Line

Cron cadence needs tightening, but not by bluntly reducing market-window jobs today.

Current proof shows most contracts are registered, but the live cron surface is still too busy, has one current contract drift, and has active blocker signals:

- `cron_contract_validator.py --require-contracts --fail-on-drift --fail-on-prompt-bloat --write --validate`: current `status=error`, contracts `33`, drift `1`, missing `0`.
- `cron_reduction_inventory.py --write --validate`: `status=ok`, enabled jobs `45`, contracts `14`, inventory target Phase 1 `38-42`, Phase 2 `29-32`, final `25-27`.
- `cron_freshness_spine.py --write --validate`: validation `ok`, status `blocked`, blocked count `7`, enabled jobs `45`, disabled jobs `38`.
- `cron_control_packet.py --write --validate`: status `ok`, escalation signals `7`.
- `market_open_repair_cadence.py --write --validate`: status `warning`, validation `ok`, repair queue `42`.
- `cron_patch_manager.py --name "Finance - Midday Paper Deployment Recommendation Cards" --write --validate`: status `ok`, validation `warning`, `empty_patch`; no schedule patch was generated or applied.

The correct next move is a schedule-diff packet after blocker repair and shadow proof, not immediate schedule mutation.

## Current Cadence Map

| Cadence | Current surfaces |
|---|---|
| Intraday / market-window | Tier A silent readiness probes at `06:42`, `07:14`, `12:07`; WF85 radar at `06:42` and `11:30`; WF87 gate/command center around `06:45/06:50` and `11:45/11:50`; WF68 alerts at `08:05` and `13:05`. |
| Daily / weekday | Morning finance refresh `06:05`; WF78 daily proof `06:08`; open-ready/recommendation cards `06:20`; opportunity controller `06:25`; research freshness `14:05`; ticker-card freshness `13:55`; SQL coverage `14:55`; canon drift `15:00`. |
| Post-close | Post-close finance refresh `13:20`; paper reconciliation `14:40`; control digest `15:22`. |
| Weekly | Sunday research reset; weekly printable intelligence; WF76 cron authority; runtime OS improvement radar; WF77 analyst consensus Monday. |
| Monthly | Monthly delivery/deep-dive exists in runner-contract planning, but no first-class enabled monthly contract was found in `state/cron-contracts`. |
| Ad hoc / gated | One-shot paper/WF67 jobs, cron patch packets, phase parity proofs, market-window shadow reduction packets. |

## Findings

1. **Over-refreshing is real.**
   Enabled cron count is still `45`, above Phase 1 target `38-42` and far above final target `25-27`.

2. **Intraday finance work overlaps.**
   WF85, WF87, Tier A probes, and WF68 refresh related market-window evidence separately. This is duplicated work by function, not necessarily duplicate job identity.

3. **SQL coverage likely runs too often.**
   Daily SQL coverage is probably excessive outside active SQL migration or parity-repair lanes. The better default is weekly or changed-file-triggered coverage.

4. **Control-surface churn remains.**
   Several unrelated producers refresh cron/control artifacts. Preferred posture is dedicated cron-control ownership and fewer side-effect refreshes from unrelated jobs.

5. **Some current data is under-repaired, not over-refreshed.**
   Market-open cadence proof still reports blocked WF78 daily core/tier routing, blocked decision factory, blocked WF85 market-hours readiness, a non-empty repair queue, and morning-card soft failures.

6. **Ordering mismatch likely exists.**
   `finance-midday-paper-deployment-recommendation-cards` runs at `11:55`, after the `11:30` post-refresh radar that likely consumes card state. That should be inspected before any schedule patch.

7. **One live contract drift is current.**
   `Finance - Midday Paper Deployment Recommendation Cards` contract expects schedule `20 11 * * 1-5` and description "before the 11:30 post-refresh radar"; live scheduler has `55 11 * * 1-5` and description "after the 11:50 WF87 command-center refresh." The conservative patch manager produced `empty_patch` because schedule mutation is blocked without a separate exact diff/apply path.

8. **Current blocked surfaces should be repaired before reduction.**
   Cron control currently reports seven escalation signals: morning/midday paper cards, ticker-card freshness, WF78 daily proof, WF78 opportunity controller, OTEL local digest, and WF74 learning digest.

## Recommended Cadence Policy

| Cadence | Should own |
|---|---|
| Intraday / market-window | Price-sensitive market readiness, WF85/WF87 paper/radar checks, WF68 alert production, execution-fresh quote gates, deployment readiness. |
| Post-close | Final quote overlays, post-close finance refresh, paper reconciliation, next-session board prep. |
| Daily | Macro/energy/geopolitical inputs, canon drift, research freshness, ticker-card owner refresh, WF78/WF84/WF85 freshness/routing, OTEL digest, runtime audit packets, memory review/promotion unless duplication is proven. |
| Weekly | Analyst consensus, OS improvement radar, cron authority review, SQL coverage when no active SQL migration lane exists, Sunday finance reset and printable intelligence. |
| Monthly | Finance delivery monthly direction/deep dive, packaging-style reports, broad OS/archive hygiene, deep strategy reviews. Do not promote monthly surfaces until upstream daily/weekly proof is stable. |
| Ad hoc only | Schedule patches, cron migration/phase parity, destructive cleanup/archive, paper execution prep, portfolio/canon applies, live/customer/external actions. |

## Inspect Before Any Schedule Patch

- `state/cron-contracts/*.json`
- `tmp/cron-control-packet.json`
- `tmp/cron-freshness-spine.json`
- `tmp/cron-contract-validator.json`
- `tmp/cron-reduction-inventory.json`
- `tmp/cron-runner-contracts.json`
- `tmp/cron-phase1-shadow-parity.json`
- `tmp/cron-phase2-shadow-parity.json`
- `tmp/cron-phase3-cadence-plan.json`
- `tmp/cron-reduction-next-patch-plan.json`
- `tmp/market-open-repair-cadence.json`
- `scripts/cron_contract_validator.py`
- `scripts/cron_freshness_spine.py`
- `scripts/cron_control_packet.py`
- `scripts/cron_reduction_inventory.py`
- `scripts/market_open_repair_cadence.py`
- `scripts/morning_market_paper_consolidated_runner.py`
- `scripts/midday_market_paper_consolidated_runner.py`

## Recommended Next Actions

1. **P0 - Repair current blocked finance freshness surfaces before cutting cadence.**
   Why: reducing market-window jobs while WF78/WF85 readiness is blocked would make the system quieter but less true.

2. **P1 - Prepare a cron cadence diff packet after blocked surfaces are repaired.**
   Why: schedule changes need exact diff, rollback, and validation proof.

3. **P1 - Resolve or intentionally rebaseline the midday paper-card schedule drift.**
   Why: current contract says the card builder should precede the 11:30 radar, but the live job still runs at 11:55.

4. **P2 - Move slow surfaces toward weekly/monthly or changed-file-triggered cadence.**
   Likely first candidates: SQL coverage outside migration lanes, broad OS/archive hygiene, packaging-style reports, and deep strategy reviews.

5. **P2 - Inspect the midday paper-card/radar ordering.**
   Why: a consumer appears to run before a likely producer.

## Stop Lines

No cron schedule mutation from this audit.

Do not:

- mutate cron schedules without a narrow diff packet and Randall approval
- mutate finance canon, portfolio, cash, sizing, or risk state
- take paper/live/brokerage/account action
- send external/customer/public delivery
- reduce intraday finance jobs until Phase 2 market-window shadow proof is clean
- loosen freshness thresholds to hide domain blockers

## Source

This audit integrates a read-only subagent cadence review plus live local proof from cron control, freshness, reduction, and market-open cadence packets. The subagent made no file edits, ran no schedule mutations, and used only local workspace files.
