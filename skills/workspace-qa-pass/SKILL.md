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
- `06. Playbooks/Workspace Structure Protocol.md` and the latest workspace-hygiene audit when path, folder ownership, or generated-artifact placement are in scope
- the current daily note if the work happened today
- the changed files and the smallest useful neighboring files
- the most relevant prior audit in `08. Audits/`

If the pass is about skills, read `06. Playbooks/Skill Quality Standard.md` and `06. Playbooks/Skills Governance Index.md` as the style and governance anchor instead of anchoring the audit to a sample skill file.

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
   - If path truth or folder governance is implicated, inspect the ownership chain across `scripts/`, `tmp/`, `skills/`, documented root exceptions, and the governing structure docs instead of stopping at the changed file.

3. Test for mismatch across six QA lenses.
   - **Trust enforcement:** do policy flags actually block behavior, or only describe it?
   - **Write integrity:** where do meaningful outputs still bypass shared atomic helpers?
   - **Schema honesty:** where do downstream consumers still assume happy-path shapes?
   - **Contract propagation:** if a shared state vocabulary, JSON contract, or manifest changed, which adjacent consumers, ranking maps, fallback paths, validators, or presentation adapters still speak the old contract?
   - **Control surface:** what still depends on flaky session/runtime assumptions?
   - **Workspace hygiene:** did the work create new duplication, stale notes, vague ownership, reopened boundary drift, undocumented root exceptions, or procedural spillover into core files?

4. Rank only concrete findings.
   - Prefer a focused list of real residual risks over a broad inventory, but do not make findings so terse that they cannot be verified or acted on.
   - For each material finding, include: evidence/source file, why it matters, severity, owner or affected surface, recommended fix, and acceptance proof.
   - For closed items, name the proof that closed them; for open debt, name the next owner/pass when known.
   - Separate closed items from still-open debt.
   - Do not relitigate issues already fixed unless new evidence shows regression.

5. Recommend the next bounded tightening step.
   - Name the smallest next pass that materially improves trust.
   - Avoid giant omnibus cleanup plans.

6. Check closeout honesty.
   - Was checkpoint posture made explicit?
   - Do queue / registry / continuity note agree?
   - Is the next pass or adjacent candidate routing explicit instead of implied?

7. Validate the QA artifact or skill you create.
   - Use the smallest meaningful check available: direct inspection, targeted grep/search, `openclaw skills check`, or another local validator.
   - If workspace structure or truth-surface ownership was in scope, run `python scripts/workspace_boundary_check.py` and `python scripts/dashboard_truth_lint.py` when those validators exist.
   - If the audited change touched shared vocab, freshness fields, or output contracts, rerun at least one adjacent consumer/acceptance path and confirm the proof artifact is fresh enough to mean anything.
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

Top findings should be concise but sufficiently detailed. A useful finding has enough evidence and acceptance criteria that another lane can fix or verify it without reconstructing the audit from scratch.

## Default edit posture

If asked only for QA, prefer writing an audit note over making broad fixes.
If asked for a small repair too, keep it tightly tied to the findings and verify it.

## Good pass standard

A good QA pass should make it harder for the workspace to lie about its own state.
