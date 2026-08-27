# Finance State

`state/finance/` is the durable finance machine-state directory.

## Current Canon Candidate

- `finance-canon.sqlite` - first approved SQL machine-canon candidate for the finance universe and answer-path scope layer.

It currently records:

- 100 active universe rows.
- 42 legacy production answer-path rows.
- 58 Tier C `review_100_monitor` rows.
- source artifact references, validator run statuses, archive candidates, and audit events.

## Proof Route

Build and validate with:

```powershell
python scripts\finance_sql_canon.py --write --validate --approval-reference "<owner approval reference>"
```

Primary proof artifacts:

- `tmp/finance-sql-canon-promotion.json`
- `tmp/finance-sql-canon-legacy-42-archive-plan.json`
- `backups/finance-sql-canon-promotion/<run_id>/manifest.json`

## Boundaries

- This SQL canon candidate does not grant portfolio mutation, canonical note mutation, customer/external delivery, sizing/cash/risk-rule authority, paper/live execution, brokerage/account action, or money movement.
- The 42-row legacy answer path is planned for archive after reference checks and consumer cutover proof, not during the first promotion pass.
- JSON universe files remain rebuild/audit mirrors; Markdown remains the human judgment layer.
