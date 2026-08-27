# Interactive Training Authoring Checklist

Generated UTC: 2026-07-04T14:40:03Z

Use this checklist before adding or revising a local interactive training module.

## Module Contract

- Define `module_id`, `title`, `audience`, `summary`, `learning_objectives`, lessons, interactions, and xAPI metadata.
- Set `authority_boundary.internal_training_only=true`.
- Keep `external_delivery_approved`, `customer_data_allowed`, `credential_access_allowed`, and `owner_approval_inferred` false.
- Add any domain-specific blocked flags such as collector/runtime/config, finance/canon, outreach, account, paper/live, or capital authority.
- Use only supported interaction types: scenario, multiple_choice, checklist, reflection, and boundary_ack.
- Include at least one boundary acknowledgement when the module touches action authority.

## Component Choices

- Available components: lesson, multiple_choice, checklist, scenario, reflection, boundary_ack, local_xapi, scorm_package, browser_qa.
- Use lessons for concise concepts, multiple choice for recognition, checklist for minimum proof fields, scenario for operator judgment, reflection for explain-back, and boundary_ack for stop-line confirmation.
- Every interaction needs a stable `id`, clear prompt, and `xapi_object`.
- Multiple-choice items need one correct choice and feedback for each option.
- Scenario and boundary acknowledgement items need an expected answer.

## Proof And Packaging

- Run `python scripts\interactive_training_builder.py --write --validate`.
- Run `python scripts\test_interactive_training_builder.py`.
- Run `python scripts\interactive_training_qa_validator.py --write --validate`.
- Run `python scripts\interactive_training_scorm_smoke_validator.py --write --validate`.
- Run `python scripts\interactive_training_catalog_builder.py --write --validate`.
- Review `tmp\interactive-training-builder-proof.json`, `tmp\interactive-training-qa-validation.json`, `tmp\interactive-training-scorm-smoke-validation.json`, and `tmp\interactive-training-catalog-proof.json`.

## Stop Lines

- Do not configure an external LMS or LRS from module authoring.
- Do not add learner/customer data transport.
- Do not approve public delivery, outreach, account action, portfolio/canon mutation, paper/live execution, or capital deployment.
- Do not broaden runtime, collector, cron, channel, credential, or config authority through training content.
