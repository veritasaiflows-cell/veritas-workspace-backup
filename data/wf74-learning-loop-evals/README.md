# WF74 Learning-Loop Evaluation Fixtures

This directory stores durable regression cases consumed by `scripts/wf74_learning_loop_eval_harness.py` and `scripts/wf74_outcome_feedback_ingestor.py`.

## Authority

- Fixtures are local evaluation inputs and review evidence only.
- They do not authorize self-modification, training, runtime/config changes, finance canon or portfolio mutation, capital deployment, execution, or external delivery.
- The owning workflow is WF74; current workflow and decision truth remains in its validated packets and owner surfaces.

## Producer And Proof

- Primary file: `cases.json`.
- Producers: the bounded WF74 feedback/evaluation scripts named above.
- Proof: run the WF74 learning-loop evaluation harness and its focused tests.

## Retention

Keep cases that protect a real regression or graded outcome. Remove or archive fixtures only after reference review and explicit cleanup approval.
