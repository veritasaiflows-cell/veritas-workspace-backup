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
- Use **Gemini Pro** as preferred IC for implementation, scripts, and broad research.
- Use **Claude** for harder judgment-heavy review and high-stakes challenge passes.
- Use spawned OpenClaw subagents for bounded file-grounded implementation.

## Effort posture
- Hard judgment/trust decisions: Claude `--effort high` (or higher when needed).
- Mechanical verification/coding scans: Gemini Pro with concise bounded prompt.
- Small low-risk checks: lower prompt depth and tighter scope.

## Fallback order
If preferred lane is unavailable:
1. ACP harness lane (if available)
2. local CLI lane (`gemini -m gemini-3.1-pro-preview -p ...` / `claude -p ...`)
3. spawned subagent with same decision contract

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
