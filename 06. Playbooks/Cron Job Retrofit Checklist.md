# Cron Job Retrofit Checklist

## Purpose

Compare an enabled job with its active contract and runtime proof before claiming it is green. Historical finance-refresh sibling definitions are retired.

## Checklist

For each enabled job verify:

1. job ID, name, owner, schedule, timezone, session target, timeout, and delivery mode match the active contract;
2. payload kind and exact command or prompt match the contract;
3. every expected artifact is registered, exists when required, parses, and is within its freshness limit;
4. prompt integrity, payload drift, and missing-artifact counts are zero;
5. scheduler status is `ok` with zero consecutive errors;
6. transitive producers and consumers are active and within the same authority boundary;
7. warnings describe domain truth and are not mislabeled as scheduler success or failure;
8. rollback and owner-gate rules are explicit for any material scheduler mutation;
9. no generated proof is treated as approval;
10. the final cron-control packet reports zero blocked, zero stale, zero scheduler exceptions, and no main-session wake signal.

## Finance acceptance

Enabled finance jobs may invoke only the alerts-and-recommendations chain and its bounded evidence feeders:

- guarded finance SQL validation;
- explicit active-symbol quote proof;
- alert freshness and suppression controller;
- morning, midday, post-close, and weekly non-executing digests;
- macro, analyst-consensus, and SQL-coverage evidence refreshes;
- the alerts-OS boundary validator.

No enabled job or transitive consumer may recreate retired finance-state, simulated-account, deployment, sizing, approval-card, order, or execution artifacts.

## Proof order

```powershell
python scripts\cron_operator_ledger.py --write --write-md --validate
python scripts\cron_efficiency_review_runner.py --write --validate
python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\cron_control_packet.py --write --validate
```

Do not force delivery jobs, retired jobs, or unsafe producers merely to erase historical status. A job is green only when scheduler, contract, artifact, freshness, transitive-route, and authority checks all agree.
