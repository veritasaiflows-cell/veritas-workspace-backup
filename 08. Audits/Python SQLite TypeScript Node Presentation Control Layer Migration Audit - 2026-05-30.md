# Python + SQLite + TypeScript/Node Presentation-Control Layer Migration Audit - 2026-05-30

## Conclusion

The recommended migration is not a rewrite. It is a layered operating model for WF75 while the Retail Investor Finance Intelligence SaaS readiness sprint is in progress:

- Python remains the workflow, finance artifact, validator, and automation engine.
- JSON remains the audit/proof surface and rebuild source for generated artifacts.
- SQLite becomes the fast local index/control-plane layer for stable contracts and hot lookup paths.
- TypeScript/Node becomes the presentation, schema, local UI, HTML/PDF, and operator-control layer.

This should be treated as a WF75 acceleration track, not a separate product pivot. It supports the existing 6-10 week path toward 55-65% internal/service-led SaaS readiness. It does not authorize public launch, customer data, external delivery, legal/compliance readiness, source-licensing assumptions, portfolio/canon mutation, paper/live execution, or owner approval inference.

## Current WF75 Posture

WF75 is the active primary lane for the Retail Investor Finance Intelligence SaaS infrastructure-first sprint.

Current live posture from `06. Playbooks/Active Workflows.md`:

- Primary goal lock: Retail Investor Finance Intelligence SaaS.
- Current lane: WF75 infrastructure-first product readiness sprint.
- Target: 6-10 week internal/service-led readiness path toward 55-65%.
- Active route: anonymous service scenarios, local operator console/control cockpit, renderer/export proof, scenario library, PM handoff, SQLite WAL control-plane proof, JSON-to-SQL promotion index, and authority-matrix proof.
- Real customer use remains blocked.

Current proof surfaces include:

- `tmp/wf75-service-led-saas-readiness-plan.json`
- `tmp/wf75-service-state-current.json`
- `tmp/wf75-service-state.sqlite`
- `tmp/wf75-service-state-sqlite.json`
- `tmp/wf75-operator-console.json`
- `tmp/wf75-operator-console.html`
- `tmp/wf75-renderer-export-regression.json`
- `tmp/wf75-scenario-template-library.json`
- `tmp/wf75-artifact-only-pm-handoff.json`
- `tmp/wf75-pm-readiness-brief.json`
- `tmp/wf75-pm-readiness-brief.pdf`
- `tmp/json-sql-promotion-index.json`
- `tmp/json-sql-promotion-index.sqlite`
- `tmp/authority-matrix.json`

## Current Technical State

### Python

Python is already the strongest layer in the workspace.

Current uses:

- Artifact generation.
- Finance intelligence refresh.
- Validators and guardrails.
- SQLite writers.
- PM handoff generation.
- Renderer/export proof.
- Workflow automation and cron proof.
- Authority matrices and stop-line packets.

Python should remain the owner of workflow truth production.

### SQLite

SQLite is already active, but scoped.

Current known SQLite posture:

- `tmp/veritas-artifact-index.sqlite`: derived artifact/proof index.
- `tmp/json-sql-promotion-index.sqlite`: derived JSON-to-SQL promotion index.
- `tmp/wf75-service-state.sqlite`: WF75 local WAL control plane.
- `state/finance/finance-canon.sqlite`: finance universe/scope SQL machine-canon candidate only, not full finance canon.
- `tmp/veritas-canon-cache.sqlite`: bounded 265-row proof/cache.
- `tmp/wf67-paper-position-state.sqlite`: paper-position visibility only.
- `tmp/finance-intelligence-state.sqlite`: finance state support surface.

Important current JSON-to-SQL promotion proof:

- `tmp/json-sql-promotion-index.json` status: `ok`.
- Posture: `json_source_sql_derived_index_only`.
- Table counts include promotion registry, JSON documents, macro events, macro metrics, macro judgments, WF75 service runs, WF75 queue items, research opportunity items, and decision packets.
- Authority boundary explicitly says JSON source of truth, SQLite derived index only, review-only, no canon/portfolio/approval/capital/customer/external/execution authority.

SQLite should be expanded as a derived index/control-plane layer, not as an authority source.

### TypeScript/Node

Local Node is available:

- Node.js: `v24.15.0`
- npm: `11.12.1`

Current gap:

- No root `package.json`.
- No root `tsconfig.json`.
- TypeScript is not installed as a workspace dependency.
- Existing JavaScript is mostly `scripts/dashboard-js/*.js`.

TypeScript/Node should be introduced in a scoped `tools/node/` package, not at workspace root at first.

## Target Architecture

The intended target shape:

```text
Python
  produces validated JSON artifacts
  runs finance/workflow validators
  writes SQLite indexes/control-plane rows
  owns automation and guardrails

JSON
  remains proof, audit, rebuild source, and artifact boundary
  carries schema_version, generated_at, source paths, and authority flags

SQLite
  indexes stable JSON contracts
  supports hot lookup paths, queue state, PM lane state, freshness, blockers
  remains rebuildable and derived unless an exact approved gate says otherwise

TypeScript/Node
  validates schemas for UI contracts
  renders local cockpit views
  builds HTML/PDF surfaces
  provides local-only read-only control UI
  improves operator ergonomics without changing authority
```

Recommended folder shape:

```text
tools/node/
  package.json
  tsconfig.json
  src/
    schemas/
    readers/
    renderers/
    cockpit/
    pm/
    finance/
  dist/
```

Do not create a broad root Node app until the first scoped package proves value.

## Why This Migration Is Worth Doing

The workspace currently has strong artifact production but too much human/agent friction around:

- finding the right proof artifact;
- comparing stale vs fresh surfaces;
- seeing multi-lane WF75 status;
- generating PM handoff and PDF surfaces;
- checking source-trust and authority status;
- turning stable JSON contracts into reusable views;
- using the operator console as the primary sprint control surface.

The expected efficiency gain after a mature implementation is roughly:

- 40-70% faster status/blocker/artifact lookup.
- 30-60% faster dashboard, PM handoff, and PDF generation.
- 25-50% less rework around stable JSON contract consumption.
- 30-50% faster workflow-state debugging.
- 25-40% overall implementation velocity improvement once the cockpit and indexes are actually used.

This is not mainly about raw compute speed. It is about reducing operator and agent context-switching cost.

## What Should Move To SQLite

Promote stable JSON contracts to SQLite indexes only when they meet this test:

- schema is versioned;
- artifact is generated repeatedly;
- fields are queried repeatedly;
- source JSON remains available;
- authority boundary is explicit;
- index can be rebuilt from proof artifacts;
- consumers need fast filtering, joining, freshness checks, or PM status aggregation.

Good candidates:

- WF75 service runs.
- WF75 queue items.
- WF75 artifact refs.
- PM lane state.
- PM blockers.
- PM next actions.
- PM readiness snapshots.
- JSON-to-SQL promotion registry rows.
- Market intelligence events.
- Daily review objects.
- Macro events, metrics, and judgment drafts.
- Recommendation/outcome ledger rows.
- Source-trust findings.
- Artifact freshness rows.
- Ticker-card metadata and coverage state.

Do not promote:

- secrets;
- real customer identity;
- customer portfolio/suitability/risk profile;
- brokerage/account data;
- approval state unless owner approval artifact exists and is scoped;
- live/paper execution commands;
- legal/compliance/source-licensing claims as if cleared.

## What TypeScript/Node Should Own

TypeScript/Node should own presentation and contract ergonomics:

- local operator cockpit;
- PM lane board;
- blocker board;
- readiness timeline;
- artifact proof links;
- schema validation wrappers for UI-facing JSON;
- HTML/PDF rendering;
- local-only static site or loopback server;
- UI regression checks with Playwright when needed.

TypeScript/Node should not own:

- finance truth generation;
- portfolio/canon mutation;
- trading or paper execution;
- owner approval state;
- broad workflow orchestration;
- credential handling;
- customer data handling.

## PM Multi-Lane Automation Model

The PM layer should become a derived program-state engine over artifacts.

Program:

- WF75 Retail Investor Finance Intelligence SaaS readiness.

Lanes:

- product/service-state;
- operator console/control cockpit;
- finance engine coverage;
- alert/event intelligence;
- SQL/index layer;
- PM handoff/PDF;
- QA/source trust;
- authority/compliance.

Automated PM questions:

1. What moved?
2. What is blocked?
3. What is stale?
4. What is the next safe action?
5. Did readiness increase, decrease, or stay flat?

Recommended PM outputs:

- `tmp/pm-program-state.json`
- `tmp/pm-lane-scoreboard.json`
- `tmp/pm-next-actions.json`
- `tmp/pm-blocker-register.json`
- `tmp/pm-readiness-snapshots.json`
- future SQLite index: `tmp/pm-program-state.sqlite`

Recommended SQLite tables:

- `pm_lanes`
- `pm_milestones`
- `pm_blockers`
- `pm_artifact_freshness`
- `pm_readiness_scores`
- `pm_decisions_needed`
- `pm_weekly_snapshots`

## Migration Phases

### Phase 0 - Document And Gate

Status: this audit.

Purpose:

- document architecture;
- preserve pickup context;
- define boundaries;
- prevent future rewrite drift.

Acceptance:

- audit exists in `08. Audits/`;
- daily memory points to it;
- no runtime/config/authority change made.

### Phase 1 - TypeScript Foundation

Estimated time: 0.5-1 day.

Deliverables:

- `tools/node/package.json`
- `tools/node/tsconfig.json`
- TypeScript installed locally under `tools/node`
- basic build script
- basic test/validate script
- read-only JSON reader
- first schema definitions for selected WF75 artifacts

Candidate dependencies:

- `typescript`
- `tsx` or equivalent runner
- `zod` or `ajv`
- optional later: `playwright`

Acceptance:

- Node package builds locally.
- No workspace-root package pollution unless deliberately approved.
- No config/auth/channel/runtime mutation.
- No finance authority change.
- No customer data or external delivery.

### Phase 2 - PM Program-State Generator

Estimated time: 1-2 days.

Primary owner language: Python.

Deliverables:

- `scripts/pm_program_state.py`
- `tmp/pm-program-state.json`
- `tmp/pm-lane-scoreboard.json`
- `tmp/pm-next-actions.json`
- `tmp/pm-blocker-register.json`

Inputs:

- Active Workflows.
- WF75 readiness plan.
- WF75 operator console.
- PM handoff.
- PM readiness brief.
- JSON-to-SQL promotion index.
- Harness scorecard.
- Authority matrix.
- Artifact freshness/current-window surfaces.

Acceptance:

- program state reports lane status, blockers, stale proof, next actions, and readiness contribution;
- all authority flags remain false where required;
- output is review-only and local;
- stale/missing proof downgrades confidence.

### Phase 3 - PM/Operator SQLite Index

Estimated time: 1-3 days.

Primary owner language: Python + SQLite.

Deliverables:

- `tmp/pm-program-state.sqlite`
- table schema for lanes, blockers, milestones, freshness, decisions, weekly snapshots;
- rebuild command from JSON proof;
- validation command;
- integrity check and foreign-key check;
- indexes for hot lookup fields.

Acceptance:

- SQLite can be fully rebuilt from JSON.
- WAL/busy_timeout/foreign_keys are set where appropriate.
- JSON remains proof.
- SQLite remains derived index/control-plane only.
- No customer, approval, execution, canon, portfolio, or external-delivery authority.

### Phase 4 - TypeScript Local PM Cockpit

Estimated time: 2-4 days.

Primary owner language: TypeScript/Node.

Deliverables:

- static/local PM cockpit renderer;
- lane board;
- blocker register view;
- readiness timeline view;
- artifact proof links;
- next-actions panel;
- authority boundary banner;
- optional local-only server if static file is insufficient.

Acceptance:

- cockpit reads `tmp/pm-program-state.json` and/or SQLite-derived JSON exports;
- UI is local-only;
- no external delivery;
- no command execution by UI;
- no owner approval inferred from green status;
- no sensitive/customer/account data.

### Phase 5 - HTML/PDF Export Integration

Estimated time: 2-5 days.

Primary owner language: TypeScript/Node plus existing Python proof generation.

Deliverables:

- consistent PM weekly HTML/PDF renderer;
- Playwright/Edge export path if needed;
- regression proof;
- source artifact manifest;
- export-size and render-success validation.

Acceptance:

- PDF/HTML generated from proof state;
- PDF status and source checks recorded;
- render failure fails closed;
- export does not imply public/customer/legal/compliance readiness.

### Phase 6 - Finance Cockpit Views

Estimated time: 3-7 days.

Primary owner language: TypeScript/Node presentation over Python/SQLite data.

Deliverables:

- ticker coverage view;
- market-intelligence event view;
- source-trust findings view;
- artifact freshness view;
- recommendation/outcome review view;
- no-action/no-approval boundary labels.

Acceptance:

- uses WF77/WF78/source-trust artifacts;
- material finance claims still require source-open proof;
- no live/paper/account authority;
- no recommendation becomes approval;
- no customer personalization.

## Suggested First Implementation Slice

First slice should be narrow:

1. Create `scripts/pm_program_state.py`.
2. Generate `tmp/pm-program-state.json`, `tmp/pm-lane-scoreboard.json`, and `tmp/pm-next-actions.json`.
3. Add validation that required source artifacts exist and are parseable.
4. Add authority-boundary checks.
5. Add a TypeScript package only after the PM JSON contracts are stable enough to render.

Reason:

- This gives immediate PM automation value.
- It does not require frontend decisions first.
- It keeps Python as the source artifact integrator.
- It gives TypeScript a clean contract to consume.

## Timeline

Minimum useful implementation:

- 1 day: Phase 1 foundation plus one proof renderer or schema reader.
- 2-3 days: PM program-state generator plus lane scoreboard.
- 3-5 days: PM/operator cockpit over the derived PM state.
- 1-2 weeks: mature local PM/operator/finance cockpit with SQLite index, HTML/PDF output, regression proof, and source-trust views.

Full product-grade SaaS application:

- 4-8+ weeks after the internal control layer is stable.

Do not confuse internal control-cockpit readiness with public SaaS readiness.

## Stop Lines

This migration must not:

- rewrite the finance engine before proving the presentation/control layer;
- move secrets into SQLite or UI artifacts;
- introduce real customer data;
- enable external delivery;
- enable Telegram/Discord/email/channel delivery;
- create public launch claims;
- imply legal/compliance/source-licensing clearance;
- mutate portfolio/canon notes outside exact approved gates;
- create paper/live/account/trading authority;
- infer owner approval from green validation;
- make SQLite a second conflicting source of truth.

## Risk Register

| Risk | Severity | Mitigation |
|---|---:|---|
| SQL becomes treated as truth rather than derived index | High | Keep JSON source paths, schema versions, hashes, rebuild commands, and authority flags in every table family. |
| TypeScript app becomes a second workflow engine | Medium | Keep TS read-only/presentation-first until a specific local-control command is approved. |
| PM readiness percentage becomes false precision | Medium | Use readiness bands and confidence labels, not exact product-readiness claims. |
| Frontend work distracts from WF75 infrastructure | Medium | Start with PM program-state generator and one cockpit slice only. |
| Customer/legal/source-licensing claims leak into UI | High | Authority banner and schema gate on every PM/cockpit/export artifact. |
| Root workspace package creates dependency noise | Low/Medium | Put Node package under `tools/node/` first. |
| SQLite DB lifecycle gets messy | Medium | Register DB in lifecycle manifest and make every DB rebuildable or clearly live-scoped. |

## Pickup Checklist

When resuming this migration:

1. Read this audit.
2. Read `06. Playbooks/Active Workflows.md`.
3. Read `tmp/wf75-operator-console.json`.
4. Read `tmp/wf75-service-led-saas-readiness-plan.json`.
5. Read `tmp/json-sql-promotion-index.json`.
6. Check Node state:

```powershell
node --version
npm --version
```

7. Check current TypeScript package state:

```powershell
Test-Path tools\node\package.json
Test-Path tools\node\tsconfig.json
```

8. Build Phase 2 before broad UI work unless `pm_program_state.py` already exists.
9. Validate artifacts before claiming readiness.
10. Keep all outputs review-only and local.

## Recommended Next Action

Implement Phase 2 first:

```text
scripts/pm_program_state.py
tmp/pm-program-state.json
tmp/pm-lane-scoreboard.json
tmp/pm-next-actions.json
tmp/pm-blocker-register.json
```

Then create the TypeScript/Node package to render those PM contracts.

This order keeps the architecture honest: proof and state first, UI second.

