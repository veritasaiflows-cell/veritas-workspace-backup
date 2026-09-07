# Training

Durable Randall-facing training assets live here. Machine proof and scratch outputs still belong in `tmp/`; this folder is for reviewable learning material, practice decks, and future app-ready simulation surfaces.

## WF75 Academy

Current path: `training/wf75-academy/`

Regenerate:

```powershell
python scripts\wf75_training_desk.py --write --write-md --write-training-assets --validate
```

Current outputs:

- `wf75-academy-current.json` - source training contract
- `wf75-academy-current.md` - human-readable curriculum
- `wf75-academy-book.docx` - cumulative lesson book for later review
- `wf75-academy-handout.html` - printable handout source
- `wf75-academy-handout.pdf` - review handout
- `wf75-academy-activity-deck.pptx` - PowerPoint activity deck
- `wf75-academy-simulation-deck.html` - browser-based interactive practice deck
- `wf75-academy-manifest.json` - proof, output paths, and authority boundary

Recommended review model:

- Word book: durable cumulative reference, best for later review and adding future lessons.
- PDF: printable/static handout generated from the current lesson book.
- PPTX: guided live-session/activity deck.
- HTML simulation: active browser practice and future app substrate.
- Chat: explain-back, scoring, correction, and adaptive coaching.

The assets are regenerated from `scripts/wf75_training_desk.py`; they are expected to change as lesson modules are added or improved. The Word book is the closest thing to the stable long-term "course book."

Boundary: internal readiness training only. No real customer data, outreach, credentials, customer-system implementation, external delivery, public launch, spending/subscriptions, guaranteed ROI/revenue claims, legal/compliance/security readiness claims, or certification claims.

## Interactive Training Builder

Current path: `training/interactive-training-builder/`

Build and validate:

```powershell
python scripts\interactive_training_builder.py --write --validate
python scripts\test_interactive_training_builder.py
python scripts\interactive_training_qa_validator.py --write --validate
python scripts\interactive_training_scorm_smoke_validator.py --write --validate
python scripts\interactive_training_xapi_ledger.py --write --validate
python scripts\interactive_training_screen_capture.py --write --validate
python scripts\interactive_training_catalog_builder.py --write --validate
```

Current outputs:

- `training/index.html` - local catalog / launcher front door for all generated modules
- `catalog.json` - machine-readable catalog built from manifests, QA proof, SCORM proof, and ledger proof
- `sample-wf75-boundary-module.json` - schema-backed source module
- `sample-wf75-boundary-module.html` - local interactive HTML runtime
- `sample-wf75-boundary-module.xapi.json` - local xAPI-style seed statements
- `sample-wf75-boundary-module-scorm.zip` - SCORM 1.2 package scaffold
- `wf75-hvac-outreach-module.json/html/xapi.json` - converted HVAC outreach practice module
- `wf75-hvac-outreach-module-scorm.zip` - SCORM 1.2 package for the HVAC practice module
- `sec-evidence-review-module.json/html/xapi.json` - SEC evidence review practice module
- `sec-evidence-review-module-scorm.zip` - SCORM 1.2 package for the SEC evidence review module
- `otel-proof-validator-module.json/html/xapi.json` - OTEL proof and validator practice module
- `otel-proof-validator-module-scorm.zip` - SCORM 1.2 package for the OTEL proof/validator module
- `openclaw-day1-gateway-module.json/html/xapi.json` - OpenClaw Day 1 Gateway/Control UI practice module
- `openclaw-day1-gateway-module-scorm.zip` - SCORM 1.2 package for the OpenClaw Day 1 module
- `authoring-checklist.md` - module authoring checklist and proof sequence
- `component-library.json/.md` - reusable component contract for lessons, quizzes, scenarios, checklists, boundary acknowledgements, xAPI, SCORM, and QA
- `qa-screenshots/` - Playwright desktop/mobile screenshots from the local QA pass
- `scorm-smoke-screenshots/` - local mock-LMS SCORM smoke screenshots
- `standards-upgrade-evaluation.json/.md` - H5P, Adapt, xAPI, SCORM, cmi5, and WCAG/Playwright/axe evaluation
- `*-manifest.json` - generated output and validation manifests
- `tmp/interactive-training-qa-validation.json` - browser/accessibility proof
- `tmp/interactive-training-scorm-smoke-validation.json` - local SCORM package/runtime smoke proof
- `tmp/interactive-training-xapi-ledger-proof.json` - local loopback xAPI ledger smoke proof
- `tmp/interactive-training-catalog-proof.json` - catalog/launcher validation proof

Use this builder for reusable interactive modules before promoting training work into heavier e-learning tooling. It is static and local-first: scoring, progress, and xAPI-style events stay in the browser unless the learner exports them. The generated HTML also includes SCORM 1.2 runtime calls when loaded inside an LMS; without an LMS it falls back to local browser behavior.

The catalog launcher is the operator front door. Open `training\index.html` in Microsoft Edge to launch modules, resume browser-local progress, download SCORM zips, inspect manifests, open xAPI seed files, and jump to QA/SCORM screenshot proof.

The catalog also links the local authoring resources. Use `authoring-checklist.md` before adding the next module, and use `component-library.md` / `component-library.json` to reuse the established interaction patterns instead of inventing a new module shape.

## Teaching walkthroughs ($0)

Watch-only lessons live in `training/interactive-training-builder/walkthroughs/`.
Day 1 is `walkthroughs/openclaw-day1.html`. Open it from the catalog or from the Day 1 module player.
You watch these. You do not record them.

Optional later `.webm`/`.mp4` files can still live in `training/interactive-training-builder/recordings/`.
That path is not required for Day 1. No LMS, no YouTube, no upload, no external media URLs.

The optional xAPI ledger is local loopback only. Start it only when you want module events written to a local JSONL ledger:

```powershell
python scripts\interactive_training_xapi_ledger.py --serve
```

Then enable ledger capture inside `training\index.html`. Generated modules read the catalog's browser setting and POST only to `http://127.0.0.1:8766/xapi`. If the collector is not running, modules continue using local browser storage and downloadable event export.

The QA layer is local and dependency-backed: Playwright opens generated HTML in installed Microsoft Edge, axe-core checks accessibility, and screenshots prove desktop/mobile rendering. It does not publish content or send learner data.

The SCORM smoke layer is also local. It checks each SCORM zip for `imsmanifest.xml`, launch HTML, module JSON, xAPI seed data, SCORM 1.2 SCO metadata, and required runtime markers. It then opens the packaged `index.html` with a mock LMS API and proves `LMSInitialize`, `LMSSetValue`, `LMSCommit`, and `LMSFinish` calls occur without downgrading completion back to incomplete.

Boundary: internal training only. No external LMS/LRS is configured, no learner data is sent externally, no public delivery is approved, and no customer data, credentials, outreach, production access, or owner approval is inferred.
