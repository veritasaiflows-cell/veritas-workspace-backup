# WF55 Paper Lifecycle Taxonomy Proposal - 2026-05-19

Status: proposal only. The current validator does not yet support explicit paper lifecycle labels.

Recommended labels: `paper_order_accepted_unfilled`, `paper_order_filled`, `paper_order_partially_filled`, `paper_order_expired_unfilled`, `paper_order_cancelled_unfilled`, `paper_order_rejected`, `paper_position_observed`, and `paper_position_closed`.

Do not rewrite the existing ETN/MSFT sidecar rows. If a later pass adopts these labels, add them to the validator allowlist, add targeted tests, and append superseding rows only when evidence supports them.
