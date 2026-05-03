# Skill Quality Standard

## Purpose

Define the minimum standard for a workspace skill to remain trusted, reviewable, and worth keeping.

This is the contract WF17 was missing.
It prevents the skill layer from becoming an ungoverned pile of prompts with unclear ownership or stale routing assumptions.

## Minimum required fields for a trustworthy skill

Every active workspace skill should make these things clear either in its own `SKILL.md` or in the skills governance index:

1. **Scope boundary**
   - what the skill owns
   - what it explicitly defers
2. **Model posture**
   - whether it is model-agnostic
   - whether it assumes OpenClaw default routing
   - whether it expects a specific external or judgment lane
   - whether any named model reference is operator-maintained and may drift
3. **Tested / validated state**
   - last tested date
   - validation method
   - current known limitation if any
4. **Deprecation trigger**
   - what condition should cause the skill to be reviewed, replaced, merged, or retired

## Minimum acceptance bar for an active skill

A skill is trustworthy enough to stay active only when:
- its scope is not ambiguous
- its output contract is readable and bounded
- it does not silently claim ownership outside its lane
- its model posture is current enough not to misroute work
- it has been validated at least at the level appropriate for the skill type
- its deprecation trigger is named

If one of those is missing, the skill should be reviewed before it is relied on for major workflow work.

## Validation tiers

### Tier 1 — Eligibility / structure check
Good enough for:
- most prompt-only or routing skills
- early governance/hardening passes

Examples:
- `openclaw skills check`
- direct inspection for scope, posture, and boundaries

### Tier 2 — Functional local proof
Good enough for:
- skills that depend on a live protocol, local script, or real file contract

Examples:
- targeted protocol cross-reference check
- script/help invocation when the skill depends on a local toolchain
- inspection of the owning workflow note or playbook against the skill contract

### Tier 3 — Live workflow proof
Use when:
- the skill drives a meaningful workflow that can lie about readiness if only structurally checked

Examples:
- bounded live workflow pass
- QA audit on the workflow the skill claims to govern

## Model-posture rule

Skills should not hard-code stale model assumptions casually.

Allowed postures:
- **model-agnostic**
- **OpenClaw defaults**
- **specific external lane preferred, operator-maintained**
- **specific model reference required, verify before use**

If a skill names a model or external lane:
- treat that reference as operator-maintained unless it is validated live frequently
- do not let a stale model reference silently become routing truth

## Deprecation triggers

At minimum, every active skill should be reviewed for deprecation when one or more are true:
- its owner scope now belongs to a newer canonical skill or playbook
- its model posture is stale enough to misroute work
- its workflow or protocol has been retired or superseded
- it repeatedly causes scope drift or false-green behavior
- it overlaps another active skill strongly enough that both create confusion
- it has not been tested since a major control-plane or runtime change

## No-skill-sprawl rule

The workspace should not keep adding skills without a governance trigger.

Trigger review when any of these happen:
- active workspace skill count exceeds **20**
- 3 or more skills overlap one lane strongly
- a new skill would duplicate an existing protocol or playbook rather than clarify it
- a skill has gone stale enough that it needs operator explanation every time it is used

When the trigger fires:
1. update the skills governance index
2. classify skills as keep / merge / review / deprecate
3. do not open more new skills until the overlap is understood

## Commit checkpoint obligation for skill-governance work

If a pass changes:
- multiple skills
- protocol files that govern skill behavior
- or the skills governance layer itself

then the pass should end with an explicit commit-checkpoint decision before the next major workflow opens.

## Where this standard is enforced

Use this file together with:
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Skills Governance Index.md`

## Current validation posture

As of 2026-05-03:
- minimum structural validation for the active workspace skill set is `openclaw skills check`
- model-specific references should be treated as operator-maintained unless a workflow proves them live
