# Interactive Training Builder Implementation Contract - 2026-07-03

## Objective

Create a reusable local full-stack foundation for HTML interactive trainings.

## Interpretation

Implement the first durable builder, not a public training platform. The current release produces schema-backed modules, static interactive HTML runtime, local xAPI-style events, SCORM package scaffolds with runtime API bridge calls, local SCORM smoke proof, standards evaluation notes, browser/accessibility validation proof, WF75 sample/HVAC, SEC evidence, OTEL proof modules, and generated authoring resources.

## Non-Goals

- No external hosting.
- No LMS or LRS account setup.
- No paid-tool subscription.
- No cron schedule mutation.
- No runtime/config/auth/channel mutation.
- No real customer data.
- No outreach, public delivery, payment collection, CRM import, credentials, or production access approval.

## Authority Class

Safe local implementation, internal training only. Public/customer delivery remains owner-gated.

## Source Surfaces

- `training/README.md`
- `scripts/wf75_training_desk.py`
- `scripts/wf75_hvac_outreach_training_stack.py`
- `scripts/otel_ops_control.py`
- `skills/otel-operations-analyst/SKILL.md`
- `memory/2026-05-31.md`
- `memory/2026-07-03.md`
- `memory/2026-07-04.md`

## Deliverables

- `schemas/interactive_training_module.schema.json`
- `scripts/interactive_training_builder.py`
- `scripts/test_interactive_training_builder.py`
- `training/interactive-training-builder/sample-wf75-boundary-module.html`
- `training/interactive-training-builder/sample-wf75-boundary-module.json`
- `training/interactive-training-builder/sample-wf75-boundary-module.xapi.json`
- `training/interactive-training-builder/sample-wf75-boundary-module-scorm.zip`
- `training/interactive-training-builder/wf75-hvac-outreach-module.html`
- `training/interactive-training-builder/wf75-hvac-outreach-module.json`
- `training/interactive-training-builder/wf75-hvac-outreach-module.xapi.json`
- `training/interactive-training-builder/wf75-hvac-outreach-module-scorm.zip`
- `training/interactive-training-builder/sec-evidence-review-module.html`
- `training/interactive-training-builder/sec-evidence-review-module.json`
- `training/interactive-training-builder/sec-evidence-review-module.xapi.json`
- `training/interactive-training-builder/sec-evidence-review-module-scorm.zip`
- `training/interactive-training-builder/otel-proof-validator-module.html`
- `training/interactive-training-builder/otel-proof-validator-module.json`
- `training/interactive-training-builder/otel-proof-validator-module.xapi.json`
- `training/interactive-training-builder/otel-proof-validator-module-scorm.zip`
- `training/interactive-training-builder/authoring-checklist.md`
- `training/interactive-training-builder/component-library.json`
- `training/interactive-training-builder/component-library.md`
- `training/interactive-training-builder/standards-upgrade-evaluation.json`
- `scripts/interactive_training_qa_validator.py`
- `scripts/interactive_training_qa_runner.mjs`
- `scripts/interactive_training_scorm_smoke_validator.py`
- `scripts/interactive_training_scorm_smoke_runner.mjs`
- `tmp/interactive-training-qa-validation.json`
- `tmp/interactive-training-scorm-smoke-validation.json`
- `tmp/interactive-training-builder-proof.json`

## Acceptance Proof

- Builder validates module structure and authority flags.
- HTML includes local scoring, progress, keyboard path, aria-live updates, and xAPI event export.
- SCORM packages are generated without external calls.
- SCORM runtime bridge calls are present and local fallback still works without an LMS.
- Local SCORM smoke test passes with mock LMS initialization, status/score/location/suspend-data writes, commit, finish, and no post-finish completion downgrade.
- Playwright/axe local QA passes on desktop and mobile screenshots.
- Tests pass.
- Changed-file validation and release contract are run before closeout.

## Stop Lines

Stop before any external delivery, LMS/LRS account mutation, customer data capture, credentials, config/runtime changes, public launch, paid subscription, or authority expansion.
