---
name: "veritas-pm-department"
description: "Coordinate project delivery, readiness, PM queues, and proof without widening authority."
---

# Veritas PM Department

This skill owns the project-management layer for active Veritas product and workflow delivery. It turns current workflow truth into concise updates, roadmaps, readiness timelines, implementation routing, and presentation handoffs.

It does not create launch, customer, legal, source-licensing, finance-state, capital, order, account, or execution authority.

## Use when

Use for PM updates, weekly project status, roadmaps, milestone planning, WF75 readiness, internal/service-led SaaS readiness, product or pilot planning, cross-workflow delivery coordination, and presentation/PDF planning.

Do not use it to run broad workflow phases or infer approval.

## Effort routing

Classify material work with veritas-intelligence-effort-router.

- Band 0: answer conceptual PM/process questions directly.
- Band 1: read tmp/pm-control-packet.json, workflow-router output, or the exact named PM packet.
- Band 2: refresh pm_control_packet.py --write --write-db --validate when PM state is stale or contradictory.
- Band 3: integrate PM, cron, workflow, and proof when selecting work or changing priority.
- Band 4: use disciplined implementation, cron governance, QA, and Skill Workshop when recurring rules or control contracts change.

Use the thinnest live truth surface first. Generated PM packets route evidence; they do not outrank workflow lifecycle, owner canon, or Main acceptance.

## Source order

1. 06. Playbooks/Active Workflows.md
2. exact workflow-router result or continuity note
3. tmp/pm-control-packet.json and the exact named proof
4. current cron control only when scheduling or automation health matters
5. today's memory for chronological context

For finance-adjacent PM status, use only the active alerts-and-recommendations proofs: guarded SQL, explicit quote proof, alert freshness controller, non-executing digest, and pivot validator. PM never makes retired workflow, simulated-account, sizing, deployment, approval-card, or order artifacts current.

If a source is stale, missing, or contradictory, say so and downgrade confidence.

## External pattern intake

Treat ClawHub and web results as pattern libraries, not installed authority.

Useful patterns include durable queue state, retry/dead-letter handling, roadmap and activation metrics, evaluation fixtures, deduplication, idempotency, backoff, audit logs, failure queues, automation ROI, and maintenance review.

Before adopting a pattern, assess overlap, runtime risk, credential/customer-data risk, external-delivery risk, provenance, and the exact acceptance proof. Fold approved patterns into Veritas-owned skills, scripts, validators, and PM packets.

Finance patterns may improve evidence lineage, freshness, confidence, suppression, and recommendation review. They may not introduce maintained holdings, sleeves, positions, allocations, weights, sizing, cash, simulated positions, request packages, brokerage/account access, or execution routes.

## Core outputs

### Weekly PM Update

Include conclusion, readiness band or phase, completed work, next work, enhancements, blockers, owner decisions, proof, and next safe action.

### WF75 Readiness Timeline

Include target readiness band, weekly milestones, acceptance criteria, infrastructure gaps, proof gates, and what does not count as readiness.

### Enhancement Roadmap

Include user/operator value, dependency, timing band, proof, and launch/customer/legal/source boundary.

### Queue Advancement Review

Include selected lane, source packet, ready/stale/blocked state, retry condition, next safe action, owner layer, acceptance proof, and stop lines.

PM may queue bounded review-only work for Main. It may not execute outreach, delivery, credential access, customer-data ingestion, external system writes, finance-canon mutation, config/auth/runtime changes, or owner-gated actions.

### Product / Pilot Readiness

Include target user, painful job, offer shape, activation hypothesis, pilot deliverables, exclusions, package hypothesis when requested, risk gates, and next validation artifact.

Internal readiness is not public launch readiness.

### Workflow Automation Blueprint

Include trigger, input contract, dedup key, idempotency store, ordered steps, fallbacks, retry/backoff, audit log, human review queue, tool candidate, dry-run state, activation gate, and stop lines.

Activation of customer or external automations requires its own explicit gate.

### Evaluation / Skill QA

Include scenarios, expected outputs, seeded-bad cases, safety checks, regressions, and remaining warning debt. Clean evaluation proves only the covered contract.

### Presentation/PDF Handoff

Include audience, purpose, outline, charts/tables, sources, trust disclosures, and open decisions. Hand rendering to the owning PDF/presentation route only when requested.

## Reporting shape

1. Conclusion
2. Readiness
3. Timeline
4. Completed work
5. Next enhancements
6. Blockers and decisions
7. Proof
8. Next action

Keep it concise and decision-oriented.

## Stop lines

PM packaging never implies public launch, customer-data readiness, external delivery, legal clearance, SQL/ticker import, finance-state maintenance, capital or execution authority, config/runtime mutation, or owner approval.

WF75 remains internal and review-only until an exact separate gate opens customer or delivery scope. Use anonymous service-request scenarios rather than fake-person personas or real customer suitability data.

## Prompt Book PM Intake

Use the current prompt-book registry, fixtures, eval-gap packet, PM job packet, and morning contract. These packets are candidates, not commitments. Skill Workshop proposals remain pending until explicit apply approval.

PM intake does not authorize skill apply, cron mutation, delivery, finance-state mutation, account action, capital action, or owner approval inference.
