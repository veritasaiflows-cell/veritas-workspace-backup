---
name: workspace-qa-pass
description: Run a bounded high-signal QA audit on the Veritas workspace after meaningful automation, workflow, skill, script, or control-surface changes. Use when checking residual integrity risk, orchestration drift, trust-gate alignment, schema-guard coverage, atomic-write debt, skill hygiene, or whether a completed hardening pass actually closed the intended gaps without widening scope.
---

# Workspace QA Pass

Run an independent review. Do not act like the implementation lane defending its own patch.

## Purpose

Find the real remaining risk after a workstream lands:
- integrity debt
- orchestration drift
- control-surface debt
- doctrine/procedure mismatch
- stale or fake closure claims

Keep the pass bounded. Prefer evidence over broad redesign.

## Read first

Read only what the pass needs, but default to:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- the current workflow contract or playbook entry if the pass targets a named workflow
- the current daily note if the work happened today
- the changed files and the smallest useful neighboring files
- the most relevant prior audit in `08. Audits/`

If the pass is about skills, also read one or two strong local skills to match current workspace style.

## Boundaries

Do not widen into full architecture redesign.
Do not touch auth, network exposure, or permissions unless the requested QA task is explicitly about them.
Do not mutate canonical finance notes unless the task explicitly includes a note-layer fix.
Default outputs are an audit note, a bounded fix list, or a skill/workspace recommendation.

## Procedure

1. Reconstruct the claimed contract.
   - What was supposed to be hardened, prevented, or proven?
   - What was explicitly out of scope?

2. Inspect the live implementation surface.
   - Read the changed files, not just summaries.
   - Check adjacent orchestrators, helpers, validators, and output writers that can silently reintroduce drift.

3. Test for mismatch across five QA lenses.
   - **Trust enforcement:** do policy flags actually block behavior, or only describe it?
   - **Write integrity:** where do meaningful outputs still bypass shared atomic helpers?
   - **Schema honesty:** where do downstream consumers still assume happy-path shapes?
   - **Control surface:** what still depends on flaky session/runtime assumptions?
   - **Workspace hygiene:** did the work create new duplication, stale notes, vague ownership, or procedural spillover into core files?

4. Rank only concrete findings.
   - Prefer a short list of real residual risks.
   - Separate closed items from still-open debt.
   - Do not relitigate issues already fixed unless new evidence shows regression.

5. Recommend the next bounded tightening step.
   - Name the smallest next pass that materially improves trust.
   - Avoid giant omnibus cleanup plans.

6. Validate the QA artifact or skill you create.
   - Use the smallest meaningful check available: direct inspection, targeted grep/search, `openclaw skills check`, or another local validator.
   - If no validator exists, say that plainly.

## Evidence standard

Do not write generic advice.
Anchor findings in concrete files, commands, outputs, or observable workflow order.
Treat prior chat claims, stale audits, and detached-session state as supporting evidence only until live workspace state matches them.

## Output format

Return in this order:
- scope audited
- files inspected
- top findings
- recommended next pass
- validation run
- intentionally deferred items

## Default edit posture

If asked only for QA, prefer writing an audit note over making broad fixes.
If asked for a small repair too, keep it tightly tied to the findings and verify it.

## Good pass standard

A good QA pass should make it harder for the workspace to lie about its own state.
