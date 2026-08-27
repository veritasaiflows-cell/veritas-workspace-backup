---
name: "code-review-auditor"
description: "Deprecate into QA router"
---

# Code Review Auditor

Deprecated compatibility router.

Use `workspace-qa-pass` for code review, script review, validator review, manifest review, workflow change review, generated-artifact review, stale-proof review, authority-boundary review, and implementation closeout QA.

## Status

`code-review-auditor` is retained only as a compatibility fallback while references are drained. It no longer owns independent review doctrine. The useful code-review posture, producer-consumer checks, authority boundaries, validation checks, and findings-first output format belong in `workspace-qa-pass`.

## Router Rule

When this skill is triggered:

1. Load `workspace-qa-pass` instead.
2. Treat the task as bounded QA unless the user explicitly asks for a historical comparison or cleanup of this deprecated skill.
3. Preserve the same authority boundary: review is not owner approval, deployment authority, finance/canon authority, paper/live/account authority, config/runtime authority, external-delivery authority, or destructive-cleanup authority.

## Allowed

- Point the operator to `workspace-qa-pass` for live QA/review work.
- Help identify remaining references that should be routed to `workspace-qa-pass`.
- Remain as a temporary fallback during the consolidation window.

## Blocked

- Do not expand this skill with new review doctrine.
- Do not treat this fallback as a separate review owner.
- Do not approve finance, paper/live execution, account action, external delivery, portfolio/canon mutation, deployment, config/runtime changes, or destructive cleanup.
- Do not delete this skill without a separate reference-review and explicit cleanup approval.

## Deactivation Gate

This skill can move from deprecated fallback to archive/delete consideration only after:

- `workspace-qa-pass` contains all required review doctrine.
- `openclaw skills check` and `skill_workshop_body_guard.py --write --validate` pass.
- A reference/residue scan shows no active owner surfaces require direct `code-review-auditor` routing.
- The skills governance index and consolidation matrix are updated.
- Randall explicitly approves archive/delete or disablement.

Until then, keep this skill visible only as a router and compatibility marker.
