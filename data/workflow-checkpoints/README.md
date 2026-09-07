# Workflow Checkpoint Configurations

This directory stores durable JSON configuration for `scripts/workflow_checkpoint_runner.py` and related checkpointed workflow controllers.

## Authority

- These files define deterministic local workflow sequencing and inputs.
- Runtime checkpoint state lives under `state/workflow-checkpoints/`; generated proof lives under `tmp/`.
- A clean checkpoint does not create canon, portfolio, capital, paper/live execution, account, runtime/config, customer, or external-delivery authority.

## Producer And Proof

- Configurations: `wf74-wf88.json`, `wf84-wf85.json`, and `implementation-closeout.json`.
- Owners: the named workflow scripts and the workflow checkpoint runner.
- Proof: run `scripts/test_workflow_checkpoint_runner.py` and the workflow-specific checkpoint tests.

## Retention

Retain while referenced by active workflow runners or vector-memory source registration. Archive only after reference review and explicit cleanup approval.
