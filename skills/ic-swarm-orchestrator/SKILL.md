---
name: ic-swarm-orchestrator
description: Orchestrate multi-contractor (IC) OpenClaw workflows where one lane generates/reasons and another verifies or pushes back before final synthesis. Use when running parallel or staged Claude/Gemini/subagent passes, defining fallback order, enforcing completion handshakes, and preventing partial or fake-green conclusions.
---

# IC Swarm Orchestrator

## Contract
Run bounded multi-lane passes with explicit roles:
1) Reasoner/Generator
2) Verifier/Challenger
3) Veritas final synthesis

Never let helper lanes publish final queue state alone.
For early automation lanes, default helper scope to contract-building, audit, contradiction, or QA unless the workflow contract explicitly widens authority.

## Role routing
Read `06. Playbooks/Automation Orchestration Protocol.md` first for the canonical lane-routing, fallback, and operator-posture rules.

This skill should not maintain a second routing doctrine.
Its job is to define the lane contract, handshake, and merge discipline after routing is chosen.

Treat all external lane references as operator-maintained posture, not permanent truth. Validate live availability before use.

## Effort posture
Use the effort posture and model-routing guidance from `06. Playbooks/Automation Orchestration Protocol.md`.
If the live environment or current operator protocol does not prove a lane/effort path, do not invent one here.

## Fallback order
Use the fallback order from `06. Playbooks/Automation Orchestration Protocol.md`.
Remove undefined or unproven routing labels rather than pretending they exist.
Treat 429/capacity failures as lane availability failures, not evidence.

## Completion handshake
Before synthesis, define expected lanes and require all to resolve.
- If one finishes first, hold final closeout.
- If one fails, retry once then fallback.
- Publish one merged decision only after all expected lanes complete or are explicitly abandoned.

Do not issue an executive-summary-style closeout until acceptance evidence and checkpoint posture are explicit.

## Quality gates
1. Scope gate: one bounded question and acceptance criteria.
2. Output gate: each lane returns explicit verdict + assumptions + key risks.
3. Conflict gate: if lanes disagree materially, run one rebuttal/challenge round.
4. Synthesis gate: Veritas states final recommendation, confidence, and next action.

## Anti-patterns
- No two-writer collisions on canonical notes.
- No "parallel for parallel’s sake" with no merge contract.
- No partial synthesis while expected lanes are still running.
- No fake-green promotion when warnings/trust gates remain.

## Suggested output template
- decision
- lane verdicts (Gemini / Claude / subagent)
- conflicts resolved
- confidence
- implementation action
- blocker or follow-up gate
