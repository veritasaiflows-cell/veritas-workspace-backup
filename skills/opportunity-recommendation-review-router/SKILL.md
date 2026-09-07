---
name: "opportunity-recommendation-review-router"
description: "Retired compatibility redirect to the alerts-and-recommendations intelligence router."
---

# Retired Opportunity Review Router

This skill is a compatibility tombstone. It owns no workflow and performs no finance operation.

When an old reference invokes it:

1. route classification and evidence effort to `veritas-intelligence-effort-router`
2. route the user-facing answer shape to `veritas-response-contract`
3. use guarded SQL plus `run_alerts_recommendations_chain.py` for current finance evidence
4. label the invocation as a retired-route redirect

Do not read or rebuild old portfolio, paper, deployment, order, sizing, or execution artifacts.

This tombstone grants no maintained account or portfolio state, no canon mutation, no external delivery, no account access, no capital authority, and no execution route. Remove it only after active reference scans prove no caller remains.
