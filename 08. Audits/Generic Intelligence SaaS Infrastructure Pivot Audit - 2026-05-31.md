# Generic Intelligence SaaS Infrastructure Pivot Audit - 2026-05-31

## Conclusion

Yes, the current WF75 SaaS infrastructure can support a pivot from a finance-only retail investor SaaS wrapper into a broader **generic intelligence operations system**, with small-business workflow automation as the fastest monetization wedge.

The honest version:

- The backend pattern is already generic enough: intake, scenario/request state, evidence or workflow analysis, operator queue, QA gates, renderer/export, PM handoff, and authority boundaries.
- The sellable offer should not be generic at first. Small business owners buy a concrete workflow outcome, not "generic AI intelligence."
- The best first non-finance wedge remains the parked **AI Workflow Clarity Sprint** / small-business workflow automation lane.
- This can fit inside the existing **6-10 week PM timeline for 55-65% internal/service-led SaaS completion** if the target is internal/operator-led infrastructure readiness.
- It does not mean public SaaS launch, real customer data readiness, multi-tenant app readiness, credential handling, external delivery readiness, or implementation automation readiness.

Recommended framing:

```text
Generic platform: Veritas Intelligence Operations Engine
First SMB wedge: Workflow Clarity Sprint
Core promise: map one painful workflow, identify practical automation opportunities, show risks, and produce an approval-ready plan without touching client systems.
```

## Current Source Truth

Current WF75 live posture:

- P0 remains Retail Investor Finance Intelligence SaaS unless Randall explicitly changes the primary goal.
- WF75 already contains a parked small-business Workflow Clarity lane.
- The 6-10 week readiness target is 55-65% **internal/service-led** readiness, not public launch readiness.
- Active infrastructure already includes service-state storage, SQLite WAL local control-plane proof, operator queue/status, operator console, renderer/export regression, scenario library, PM handoff, PM readiness PDF, authority matrix, and harness scorecard.

Relevant existing artifacts:

- `tmp/wf75-saas-service-readiness-plan.json` - original service-led SaaS plan for AI Workflow Clarity Sprint.
- `tmp/wf75-phase0-contract-artifacts.json` - SMB offer, intake, analysis, deliverable, QA, privacy contract.
- `tmp/wf75-phase1-fictional-demo-packet.json` - fictional HVAC missed-lead demo.
- `tmp/wf75-phase2-uiux-prototype.json` - customer/operator UI model for Workflow Clarity Sprint.
- `tmp/wf75-phase3-service-state-schema.json` - service-delivery SQL/current-state design for Workflow Clarity Sprint.
- `tmp/wf75-phase4-lead-prep-and-second-demo.json` - ICP, scripts, second fictional professional-services demo, pilot runbook.
- `tmp/wf75-service-led-saas-readiness-plan.json` - active 6-10 week internal/service-led readiness plan for retail finance.
- `tmp/wf75-service-state-current.json` - anonymous service-state proof.
- `tmp/wf75-service-state.sqlite` and `tmp/wf75-service-state-sqlite.json` - local WAL control-plane proof.
- `tmp/wf75-operator-console.json` and `.html` - local operator cockpit.
- `tmp/wf75-renderer-export-regression.json` - renderer/export QA harness.
- `tmp/wf75-scenario-template-library.json` - current anonymous scenario library.
- `tmp/authority-matrix.json` - approval-lane and stop-line spine.

## Pivot Thesis

The reusable product is not "a finance SaaS" or "an SMB automation SaaS." The reusable product is an **intelligence-to-action service infrastructure**:

1. Intake a messy request.
2. Normalize it into a structured scenario or service run.
3. Analyze it against evidence, workflow details, or operator rules.
4. Produce ranked recommendations.
5. Block overclaims, internal leaks, credentials, and unsafe delivery.
6. Route the result through operator review.
7. Render a clean customer-safe deliverable.
8. Track next actions, blockers, and PM readiness.

Finance is one high-value vertical. SMB workflow automation is another vertical. The shared infrastructure is the same service engine.

## What Carries Over Cleanly

| Existing WF75 Infrastructure | SMB Workflow Automation Equivalent |
|---|---|
| Anonymous service request scenario | Sanitized workflow-intake scenario |
| Ticker set / evidence inputs | Business workflow steps, tools, pain points, constraints |
| Finance evidence/freshness labels | Workflow evidence, intake completeness, sensitivity labels |
| Customer-safe finance brief | Customer-safe workflow automation plan |
| No-advice / no-execution validator | No-guarantee / no-credential / no-implementation-access validator |
| Operator queue | Delivery queue for audits, plans, QA, and follow-up |
| Renderer/export pipeline | Automation-plan PDF/HTML/Markdown renderer |
| PM handoff | Service delivery and pilot-readiness handoff |
| Authority matrix | Customer data, credentials, delivery, implementation, and outreach gates |

This is a strong architectural signal: the system is already closer to a reusable service infrastructure than a single-purpose finance app.

## What Does Not Carry Over Automatically

The following do not transfer for free:

- Real customer intake approval.
- Customer data storage policy.
- Retention/export/delete procedure for SMB data.
- Credential or system-access handling.
- External delivery channel approval.
- Public marketing/outreach approval.
- Done-for-you implementation authority.
- Legal, compliance, tax, HR, accounting, security, or regulated professional advice authority.
- Guaranteed revenue, savings, or ROI claims.

The SMB lane has lower regulatory risk than personalized finance advice, but it has its own risks: credentials, client records, payment systems, employee data, regulated business data, and false ROI promises.

## Product Shape

### Platform Name

Working internal name:

```text
Veritas Intelligence Operations Engine
```

Plain-English description:

```text
A private operator-led AI system that turns messy business, finance, or workflow questions into structured intake, evidence-backed analysis, QA-safe recommendations, and polished deliverables.
```

### First SMB Wedge

Working offer:

```text
Workflow Clarity Sprint
```

Customer-facing promise:

```text
We map one painful workflow, identify practical automation opportunities, show what not to automate yet, and deliver a plain-English action plan. No passwords, no system access, no production changes, and no guaranteed revenue claims.
```

Best first segments:

- local professional services
- owner-operated service businesses
- bookkeeping/tax support firms, with sensitivity caution
- local retail or repair businesses
- small restaurants/catering/event workflows
- consultants/coaches/agencies with intake and follow-up friction

Best first workflow types:

- missed lead follow-up
- inquiry triage
- appointment scheduling
- document collection
- quote/proposal follow-up
- customer status updates
- review/referral workflows
- internal task handoffs

Avoid first:

- payment/POS access
- payroll/HR workflows
- medical, legal, tax, or compliance-sensitive decisioning
- direct accounting-system automation
- customer-record ingestion
- API-key or password handling
- autonomous outbound messages without review

## 6-10 Week Timeline Fit

### Verdict

This pivot can fit the existing PM timeline **only if the goal remains 55-65% internal/service-led SaaS infrastructure readiness**.

It cannot honestly become a public, generic, customer-ready SaaS in 6-10 weeks without cutting corners on privacy, security, delivery, onboarding, support, and legal boundaries.

### Why It Fits

The system already has the hard middle layer:

- service-state and run lifecycle
- operator queue
- local control cockpit
- renderer/export pipeline
- QA regression
- scenario library
- PM handoff
- authority matrix
- no-leak/no-overclaim posture

The SMB pivot mainly needs schema specialization and scenario/deliverable expansion, not a total rebuild.

### Proposed 6-10 Week Adapted Plan

| Phase | Weeks | Goal | Output |
|---|---:|---|---|
| 0 | 0-1 | Pivot contract | Decide whether SMB Workflow Clarity becomes active side-lane, alternate P0, or future wedge. Freeze naming, claims, and stop lines. |
| 1 | 1-2 | Generic service-run schema | Generalize service-state fields from finance-only scenario fields into domain/request/workflow/evidence fields. |
| 2 | 2-4 | SMB workflow fixtures | Add 3-5 anonymous SMB workflow scenarios: missed lead, document collection, quote follow-up, scheduling, status updates. |
| 3 | 3-5 | SMB deliverable renderer | Generate customer-safe workflow maps, automation opportunity tables, risk notes, and implementation roadmaps. |
| 4 | 4-6 | SMB validator | Block credentials, internal leaks, guaranteed ROI, legal/tax/compliance/security certainty, and external-send inference. |
| 5 | 5-7 | Operator cockpit extension | Add domain filter: finance vs workflow automation. Show readiness, blockers, QA state, and next operator action. |
| 6 | 7-8 | PM handoff and demo packet | Produce internal PM packet comparing finance lane and SMB lane readiness. |
| 7 | 8-10 | Pilot decision packet | Prepare go/no-go for warm-network feedback or fictional-only continued build. No outreach unless separately approved. |

Expected outcome at week 10:

- 55-65% internal/service-led readiness for a generic intelligence engine with finance and SMB workflow lanes.
- Strong demo/proof posture.
- Operator-led delivery path.
- Not public SaaS.
- Not real customer-data ready unless separate gates are approved.

## Architecture Adjustment Needed

Current WF75 service-state is finance-shaped in active scenarios. The next evolution should introduce a domain-neutral service run contract.

Recommended generic fields:

- `service_run_id`
- `domain`: `finance_intelligence`, `workflow_automation`, `business_research`, `learning_plan`, etc.
- `request_type`
- `scenario_id`
- `audience_segment`
- `input_sensitivity_class`
- `allowed_evidence_classes`
- `forbidden_data_classes`
- `analysis_state`
- `renderer_state`
- `validator_state`
- `blocker_reason`
- `next_operator_action`
- `customer_visible_allowed`
- `external_delivery_allowed`
- `authority_boundary`

Finance-specific fields like ticker sets should become domain payload fields, not top-level assumptions.

SMB workflow payload fields:

- `business_type`
- `workflow_name`
- `workflow_steps`
- `current_tools`
- `pain_points`
- `time_lost_band`
- `sensitivity_flags`
- `automation_candidates`
- `not_recommended_automations`
- `implementation_risk`
- `non_guaranteed_roi_hypothesis`

## Recommended Implementation Order

1. Create a review-only pivot packet or script output:
   - `tmp/generic-intelligence-saas-pivot-audit.json`
   - optional later: `scripts/generic_intelligence_saas_pivot.py`

2. Add SMB workflow scenarios to a separate scenario library, not the active finance scenario library at first:
   - `tmp/wf75-smb-workflow-scenario-library.json`

3. Add a generic service-run schema proposal:
   - `tmp/generic-service-run-contract.json`

4. Build an SMB renderer regression harness:
   - `tmp/wf75-smb-renderer-export-regression.json`

5. Extend the operator console only after contracts validate:
   - show finance and SMB lanes side by side
   - keep both local-only
   - do not imply public/customer readiness

6. Prepare a PM decision packet:
   - keep Retail Finance as P0
   - promote SMB as P1 monetization side-lane
   - or pivot SMB to P0 if Randall explicitly chooses speed-to-cash over finance-product focus

## Strategic Recommendation

Do not abandon the retail finance infrastructure. It is valuable and differentiating.

But for monetization, the SMB Workflow Clarity lane is likely faster:

- lower compliance burden than retail investment advice
- easier to explain
- easier to sell as a fixed-scope service
- less dependent on source licensing
- can start as planning-only
- can use fictional demos and warm feedback before real client data

Recommended business posture:

```text
Build one generic internal service engine.
Keep two vertical wrappers:
1. Retail Finance Intelligence - long-term, high-value, compliance-heavy.
2. Workflow Clarity Sprint - faster cash-flow validation, service-led, lower regulatory burden if kept planning-only.
```

Do not market the platform as generic until at least two narrow vertical wrappers work.

## Decision Options

### Option A - Keep Retail Finance P0, Add SMB As P1 Side-Lane

Best if Randall wants to preserve the current workflow lock and avoid churn.

Pros:

- lowest disruption
- uses existing PM timeline
- keeps finance moat intact
- allows SMB monetization prep without confusing control surfaces

Cons:

- slower direct cash-flow test
- SMB may stay parked too long

Recommendation: best default.

### Option B - Pivot WF75 P0 To Generic Intelligence Engine

Best if Randall wants the product architecture to become explicitly multi-domain now.

Pros:

- aligns better with reusable SaaS infrastructure
- reduces overfitting to finance
- makes PM layer more platform-oriented

Cons:

- risks broadening too early
- can dilute the retail finance sprint
- needs careful naming and schema generalization

Recommendation: viable, but only if we freeze the generic service-run contract first.

### Option C - Pivot P0 To SMB Workflow Clarity Sprint

Best if near-term revenue validation is the top priority.

Pros:

- fastest monetization path
- existing artifacts are already strong
- easier first pilot story

Cons:

- pauses retail finance product focus
- requires outreach/training/pricing decisions
- still needs data/delivery gates before real pilots

Recommendation: strongest cash-flow test, but should be an explicit owner decision.

## Stop Lines

This audit does not authorize:

- changing Active Workflows P0 by implication
- outreach, emails, posts, calls, or lead contact
- real customer data intake
- customer-data storage
- credential handling
- client system access
- external delivery
- public launch
- paid subscriptions or account signups
- legal/compliance/security/tax/accounting certainty
- guaranteed savings, revenue, or ROI claims
- finance portfolio/canon mutation
- brokerage/account/paper/live action
- owner approval inference

## Review Questions For Randall

1. Should SMB Workflow Clarity become a P1 monetization side-lane while Retail Finance stays P0?
2. Should the PM timeline be reframed around a generic service engine with finance and SMB as vertical wrappers?
3. Is near-term revenue validation more important than staying locked on the retail finance product?
4. Do we want the next implementation slice to be contract-only, scenario-library, renderer, or operator-console extension?

## Recommended Next Action

Create the generic service-run contract and SMB scenario library as review-only artifacts:

```text
tmp/generic-service-run-contract.json
tmp/wf75-smb-workflow-scenario-library.json
tmp/wf75-smb-pivot-pm-decision-packet.json
```

Then decide whether SMB remains a side-lane or becomes the active WF75 product target.

