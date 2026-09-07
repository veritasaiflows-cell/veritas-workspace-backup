# WF43 Post-Cron Validation Report

Generated: 2026-05-11T00:35Z

## Verdict

WF43 durable state-history proof remains **clean**.

## Required validation

Command passed:

```bash
python scripts\state_history_capture.py validate
```

Output:

```text
state_history_validation_passed rows=2 path=data/state-history/state-history-v1.jsonl
```

## Durable row inspection

- Durable path: `data/state-history/state-history-v1.jsonl`
- Row count: `2`
- Latest capture run: `20260510T232051Z_postclose_ee2357cf8e68`
- Latest captured at UTC: `2026-05-10T23:20:51Z`
- Row type: `state_snapshot_v1`
- Schema version: `1`
- Window: `post-close`

Latest-row counts:

- Deployment states: `10`
- Band statuses: `19`
- Review objects: `12`
- Capital deployment recommendations: `6`
- Market-intelligence events: `14`
- Known gaps: `4`
- Source artifacts: `6`

## Authority check

All authority flags remain false / historical-review-only:

- `consumer_posture`: `historical_review_only`
- `canonical_note_mutation_allowed`: `false`
- `deployment_state_mutation_allowed`: `false`
- `model_driven_deployment_allowed`: `false`
- `model_training_enabled`: `false`
- `owner_approval_granted`: `false`
- `portfolio_mutation_allowed`: `false`
- `trade_execution_allowed`: `false`

## Future outcomes check

Future outcome fields remain empty:

- `owner_decision`: `null`
- `owner_decision_at_utc`: `null`
- `owner_decision_provenance`: `null`
- `outcome_notes`: `[]`
- `realized_outcomes`: `[]`
- `realized_outcomes_updated_at_utc`: `null`

## Provenance check

- Source artifact count: `6`
- All source artifacts exist: yes
- All source artifacts have SHA-256 hashes: yes

## Cron context checked

- WF40 daily security audit cron history was checked for job `d2cbac10-f1fb-4060-8445-cb13f3dfc6be`.
- Latest ordinary 17:10 cron envelope was `ok`, but its run-history proof summary was the earlier failed closed result before the later WF40 residual-exception fix.
- Current proof artifact after the exception patch shows `proof_status=ok`, `audit_status=warning`, `audit_stop_line=false`, and `errors=[]`.
- WF43 reminder job `aa406457-1955-42e9-b8da-f173d411754c` was visible as running/current; no separate prior run history entries were available.

## Handoff judgment

WF43 stays **durable-proof-passed**.

The reminder's requested WF53 sector/correlation handoff is now superseded by current control-surface truth: WF53 is already `v1 implemented / QA accepted`, and the active next workflow is WF55 probability-readiness report / validator gate. No queue regression to WF53 was made.

## Mutations avoided

No config, auth, external-channel, canonical finance-note, portfolio/deployment-state, trade, or owner-approval mutation was made.
