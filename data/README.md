# Data Directory

`data/` holds durable source and registry inputs used by workspace automation.

## Authority

- Data files are durable inputs and audit mirrors, not owner approval or execution authority.
- When a data family is promoted into a `state/` SQL canon candidate, the data file remains a rebuild/audit surface unless a later proof packet says otherwise.
- Do not place scratch proof, generated packets, or temporary exports here; those belong under `tmp/`.

## Current Subdirectories

- `finance/` - finance universe registry and related durable finance inputs.
- `wf74-learning-loop-evals/` - bounded regression fixtures for the WF74 learning-loop evaluator; review/proof input only.
- `workflow-checkpoints/` - deterministic checkpoint-runner configuration; runtime state is stored separately under `state/workflow-checkpoints/`.

## Current Root Files

- `vector-memory-sources.json` - the governed source registry for local vector-memory indexing. It routes retrieval inputs and grants no canon, approval, execution, or external-delivery authority.
