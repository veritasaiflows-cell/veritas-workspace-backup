# Retired — Active Model Prompt Queue

Status: Retired on 2026-08-29 during the alerts-and-recommendations OS cutover.

This queue encoded obsolete finance-state and deployment diagnostics. None of its prompts are current, ready, approved, or safe to dispatch.

Current model/helper routing is owned by:

- `scripts/project_implementation_router.py`
- `skills/veritas-model-routing-helper-lanes/SKILL.md`
- the concurrent lane register and exact task owner

Current finance work routes through guarded SQL, explicit quote evidence, the alert freshness controller, and non-executing recommendation outputs. Retired prompt text must not be reconstructed from history or treated as approval.

No capital, order, brokerage, account, simulated-account, external-delivery, finance-canon, or schedule authority is granted by this tombstone.
