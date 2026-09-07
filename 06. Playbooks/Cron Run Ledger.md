# Cron Run Ledger

Status: current control pointer. Pre-pivot narrative run entries were retired on 2026-08-29 and remain recoverable in repository history; they are not scheduler truth.

## Current truth surfaces

- live scheduler state: `openclaw cron list --json`
- active contracts: `state/cron/contracts/active/`
- retired contracts: `state/cron/contracts/retired/`
- freshness proof: `tmp/cron-freshness-spine.json`
- control packet: `tmp/cron-control-packet.json`
- operator ledger: `tmp/cron-operator-ledger.json`

`status=ok` on a proof producer means the packet was generated successfully. Fleet health additionally requires zero enabled scheduler errors, zero blocked or stale required jobs, zero contract drift/missing contracts, zero live scheduler exceptions, and `should_wake_main_session=false`.

## Finance scheduler contract

Enabled finance jobs may invoke only the guarded alert-evidence and recommendations chain, alert boundary validation, SQL coverage, approved macro evidence, and analyst-consensus evidence refresh. Legacy portfolio, tier-promotion, deployment, paper, order, account, or execution producers remain retired and disabled.

Do not force external-delivery jobs merely to clear historical state. Do not force retired jobs. Schedule, delivery, config, channel, or runtime changes require Randall's explicit gate.

## Recording rule

Machine proof owns exact timestamps, job IDs, results, and failure counts. Durable narrative is added only for a material incident, retirement, architecture decision, or recovery that is not already clear from generated proof.
