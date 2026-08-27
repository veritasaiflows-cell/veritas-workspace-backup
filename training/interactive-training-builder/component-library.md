# Interactive Training Component Library

Generated UTC: 2026-07-04T14:40:03Z

Reusable local components for schema-backed HTML training modules.

| Component | Purpose | Required fields |
|---|---|---|
| Lesson | Teach a compact concept before practice. | id, title, body, key_points |
| Multiple Choice | Check recognition of the safest or most accurate path. | id, type, title, prompt, choices, xapi_object |
| Checklist | Train minimum proof, approval, or handoff fields. | id, type, title, prompt, checklist_items, xapi_object |
| Scenario | Practice written operator judgment under uncertainty. | id, type, title, prompt, expected, rubric, xapi_object |
| Reflection | Capture explain-back and next-safe-action thinking. | id, type, title, prompt, rubric, xapi_object |
| Boundary Acknowledgement | Force explicit recognition of authority limits. | id, type, title, prompt, expected, xapi_object |
| Local xAPI Events | Record local started, answered, completed, passed, failed, and boundary review events. | xapi.activity_id, xapi.verbs |
| SCORM Package | Package the module for later LMS smoke/import testing. | index.html, module.json, xapi-seed.json, imsmanifest.xml |
| Browser QA | Prove desktop/mobile rendering, accessibility, console, and overflow behavior. | desktop screenshot, mobile screenshot, axe result, console result |

## Boundary

- Local files only.
- No external LMS/LRS configuration.
- No learner/customer data external transport.
- No public delivery approval.
- No owner approval inference.
