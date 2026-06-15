# Skills Governance Index

## Purpose

Provide one operator-facing index for the active workspace skills so scope, posture, validation state, and deprecation triggers are visible without a full skill-by-skill audit.

## Governance fields
- **Owner**
- **Scope**
- **Model posture**
- **Validation tier**
- **Last tested**
- **Deprecation trigger**

Validation posture for this index on 2026-05-03:
- baseline validation method: `openclaw skills check`
- this is a governance/accounting surface, not proof that every skill just completed a live end-to-end workflow pass
- unless explicitly upgraded, the honest default validation posture for active skills is **Tier 1 structural**

## Active workspace skills (37 canonical)

2026-06-14 count correction: `openclaw skills check` reported 95 total skills, 53 visible/eligible, and 0 missing requirements after applying `veritas-workspace-audit-orchestrator`. Governance count for workspace skill directories is now 38 total: 37 canonical active workspace skills plus 1 deprecated legacy fallback (`technical-chart-pass`). The 2026-06-06 metadata pass covered the then-live 35 workspace skill directories; `veritas-intelligence-effort-router`, `veritas-wf78-tier-promotion-spine`, and `veritas-workspace-audit-orchestrator` are tracked as canonical active skills added after that pass.

The original 19-skill table remains the baseline spine; the supplementary table below accounts for newer active skills added since the last full governance rewrite.

| Skill | Owner | Scope | Model posture | Validation tier | Last tested | Deprecation trigger |
|---|---|---|---|---|---|---|
| automation-hardening-manager | Veritas workspace | automation architecture, trust gates, ownership boundaries | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-06-04 | replace or merge if automation-governance contract moves fully into a newer canonical playbook/skill |
| cron-automation-manager | Veritas workspace | cron design, scheduling boundaries, overlap risk, WF75/SQL coverage patterns, approved scoped entry-band maintenance exception, WF74 collection, and no-training cron boundaries | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-06-08 | review if cron layer changes enough that scheduling guidance becomes stale or duplicates another skill |
| ic-swarm-orchestrator | Veritas workspace | bounded multi-lane orchestration, challenge lanes, completion handshake | operator-maintained external-lane references; validate routing via protocol before use | Tier 2 functional local proof | 2026-05-04 | review if external lane posture or helper-lane governance drifts materially |
| memory-continuity-manager | Veritas workspace | daily/durable memory routing, pre-compaction flush discipline, duplicate-heading hygiene, and dedupe posture | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-14 | review if continuity system or daily-note contract changes materially |
| openclaw-operator | Veritas workspace | workspace/runtime/config/skill hygiene | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if runtime/operator procedures move into a new canonical operator layer |
| openclaw-troubleshooter | Veritas workspace | OpenClaw runtime/config troubleshooting | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if troubleshooting doctrine drifts from live runtime or docs |
| project-continuity-manager | Veritas workspace | thin project pickup points and continuity notes | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if project continuity standard is replaced by a stronger canonical workflow contract |
| veritas-fundamental-pass | Veritas workspace | Veritas equity fundamentals workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if finance evidence standards or vault structure change materially |
| veritas-investment-deck | Veritas workspace | finance-first investment presentation workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if deck workflow is superseded by a canonical packaging layer |
| veritas-macro-pass | Veritas workspace | macro regime and market context workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if macro source/trust rules change materially |
| veritas-pdf-brief | Veritas workspace | finance-first PDF deliverable workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if fixed-layout output flow changes materially |
| veritas-portfolio-update | Veritas workspace | portfolio board synchronization, band maintenance, and trust-boundary handling | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-07 | review if portfolio owner surfaces or sync contracts change materially |
| veritas-positioning-pass | Veritas workspace | portfolio-positioning decisions from macro/fundamental/technical inputs | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if positioning doctrine or risk rules change materially |
| veritas-post-earnings-sync | Veritas workspace | post-earnings closure workflow and note-layer sync | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | promote toward Tier 3 live-workflow proof as a priority core workflow |
| veritas-self-improvement | Veritas workspace | doctrine-aligned reflection, correction capture, WF74 reflection/proposal routing, gated auto-patch proposal routing, and RSI-to-candidate-to-skill proposal loop | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-06-13 | review if self-improvement outputs begin overlapping continuity or operator layers excessively |
| veritas-technical-pass | Veritas workspace | canonical Veritas technical timing workflow | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-05-04 | review if ownership drifts back toward deprecated legacy technical-state vocab or chart standards change materially |
| veritas-weekly-brief | Veritas workspace | weekly intelligence rebuild and synthesis workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | promote toward Tier 3 live-workflow proof as a priority core workflow |
| workspace-governor | Veritas workspace | workspace structure, note placement, startup-surface compression, audit residue intake, generated-proof placement, and organization governance; `tmp/` prototype-proof lifecycle paired with disciplined-implementation exemption | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-14 | review if workspace architecture, root-folder policy, or boot-surface ownership changes materially |
| workspace-qa-pass | Veritas workspace | bounded high-signal QA audits after meaningful changes, including layered audit-claim QA, live-state/artifact reconciliation, PM proof-budget fit, WF75 evaluation lens, and approved-implementation closeout honesty | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-06-14 | review if QA standards drift from live control-plane or workflow contract standards |

### Supplementary active workspace skills added after the original governance baseline

| Skill | Owner | Scope | Model posture | Validation tier | Last tested | Deprecation trigger |
|---|---|---|---|---|---|---|
| bash-compatibility | Veritas workspace | Bash/WSL compatibility checks in a native Windows workspace | explicit-use only; PowerShell remains default | Tier 1 structural | 2026-06-06 | review/deprecate if Bash compatibility is no longer needed or runtime moves away from native Windows |
| code-review-auditor | Veritas workspace | independent code/patch review, scope-drift review, adjacent contract QA, stale-doc checks, and claims-vs-proof verification | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-14 | merge/deprecate if workspace-qa-pass fully absorbs code-specific review |
| disciplined-implementation | Veritas workspace | system-aware implementation governance, implementation size classes, reuse/proof/flattening, PM proof-budget routing, adjacent-consumer scans, stop lines, and training/eval candidate-script guardrails | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-06-08 | review if implementation procedure moves fully into a canonical playbook or if post-control-plane growth is not revalidated |
| obsidian | Veritas workspace | Obsidian/vault note operations | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-17 | review if note-layer tooling changes materially |
| operating-procedure-repository-manager | Veritas workspace | operator procedure repository governance | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-17 | merge if procedure repo becomes part of workspace-governor |
| safe-refactor-planner | Veritas workspace | low-risk refactors preserving behavior/proof | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-17 | merge if disciplined-implementation fully absorbs refactor planning |
| sec | ClawHub / Veritas-inspected | official SEC EDGAR filings, company facts, XBRL, and filing-index evidence for WF65/WF66 support | local `.venv`; official-source evidence only, no portfolio/canon/trade authority | Tier 2 bounded smoke proof | 2026-05-17 | remove/disable if dependency behavior widens beyond GET-style SEC evidence retrieval, User-Agent compliance breaks, or outputs are treated as authority instead of evidence |
| smb-workflow-automation-operator | Veritas workspace | SMB Workflow Clarity / Lead Rescue scenarios, manual service packets, automation blueprints, tool-fit recommendations, and customer-safety stop lines | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-31 | merge/deprecate if SMB service operations are abandoned or fully absorbed by a future training/service app with stronger governance |
| sqlite | Veritas workspace | SQLite concurrency/type/pragma handling | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-04 | review if SQLite usage disappears or moves to a bundled skill |
| veritas-bounded-portfolio-agent | Veritas workspace | WF64/WF56 bounded portfolio/canon proposal and gated apply loop, including scoped routine entry-band maintenance | model-agnostic; OpenClaw defaults | Tier 2 workflow proof | 2026-06-07 | review if portfolio mutation authority changes materially |
| veritas-financial-planning-pass | Veritas workspace | bounded planner/advisor synthesis across goals, constraints, portfolio posture, and recommendations | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-17 | merge/deprecate if positioning-pass absorbs holistic planner/advisor synthesis |
| veritas-pm-department | Veritas workspace | roadmap, readiness, and queue framing across product lanes | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-06 | merge/deprecate if PM framing moves fully into the PM cockpit or Active Workflows contract |
| veritas-response-contract | Veritas workspace | user-facing response proof/risk/next-action contract, finance response boundaries, opportunity radar, WF78 tier-funnel replies, canon-change context, and model-improvement/training claim discipline | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-08 | review if response style or authority boundaries change materially |
| veritas-wf78-tier-promotion-spine | Veritas workspace | WF78 tier routing, promotion, repair, freshness, and non-capital funnel-spine governance | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-14 | review if WF78 tier semantics, promotion authority, or repair-funnel ownership moves into a newer canonical workflow skill |
| veritas-workspace-audit-orchestrator | Veritas workspace | full workspace audits, targeted finding reviews, control-plane health reviews, skill/procedure hardening review, and finance authority review with proof boundaries | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-06-14 | review if full-audit routing moves into a newer control-plane skill or overlaps workspace-governor/workspace-qa-pass enough to create confusion |
| wf67-paper-trading-operator | Veritas workspace | WF67 paper-only trading preparation, guard proof, and owner approval boundaries | model-agnostic; paper-only guardrails; no live execution authority | Tier 1 structural | 2026-06-06 | review/deprecate if WF67 paper workflow is retired or paper/live authority boundaries materially change |
| windows-powershell-workspace | Veritas workspace | native Windows/PowerShell workspace execution guidance | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-17 | review if runtime moves away from native Windows |

## Deprecated legacy fallback

| Skill | Status | Current posture | Replacement |
|---|---|---|---|
| technical-chart-pass | Deprecated legacy fallback | Keep only as a narrow generic chart-read fallback; do not use for board sync, technical-sheet updates, or Veritas deployment-state work | `veritas-technical-pass` |

## Stale-model-reference rule

If a skill references:
- a specific OpenClaw model ID
- Gemini / Claude lane posture
- or any external routing assumption

that reference should be treated as **operator-maintained** unless it is validated live frequently.

Current skill with explicit operator-maintained external lane posture:
- `ic-swarm-orchestrator`

## Known governance follow-up

- 2026-06-06: skill directory audit corrected governance accounting to 35 workspace skill directories (34 canonical active + 1 deprecated fallback), added `agents/openai.yaml` metadata across all workspace skills, added explicit boundary sections to `code-review-auditor` and `obsidian`, and deferred `skills/sec/.venv` relocation as a separate approval/rollback cleanup packet.
- `technical-chart-pass` overlap has now been resolved by deprecating it into a narrow legacy generic-fallback posture and routing canonical board work to `veritas-technical-pass`.
- 2026-05-17: new `veritas-financial-planning-pass` intentionally adds one planner/advisor synthesis owner instead of scattering planner constraints across every finance skill. Existing positioning/fundamental/response/bounded-portfolio skills were tightened to reference this boundary and WF55 probability gates.
- 2026-05-31: new `smb-workflow-automation-operator` is approved because SMB Workflow Clarity / Lead Rescue needs a separate department owner from finance. This reduces cross-lane confusion and keeps customer/workflow stop lines out of portfolio skills.
- 2026-06-03: cron/skill/SQL-consumer architecture hardening now has a JSON-first gate: `python scripts\automation_stack_hardening_pass.py --write --validate`. Use it after cron load reductions, skill-routing edits, or WF72 A2 proof changes before claiming the automation stack is hardened.
- 2026-06-03: retail-grade truth routing is now the top automation hardening priority. Use `python scripts\retail_truth_routing_contract.py --write --validate` for Phase 1 before claiming SQL/customer/retail answer-path readiness; PM may coordinate status, but Veritas main keeps final truth authority.
- 2026-06-05: product-scale pass created WF80-WF83 without increasing skill count. Decision: product expansion should first reuse existing PM/SMB/response/continuity/implementation/QA/hardening skills; propose a new skill only after live repeated friction shows an ownership gap.
- 2026-06-07: Randall approved the band-maintenance doctrine: the system owns fresh reference bands and routine posture-preserving technical entry-band/stop maintenance; Randall handles exceptions, policy changes, invalidation/reclaim judgment, and capital/execution decisions. Updated `veritas-portfolio-update`, `veritas-bounded-portfolio-agent`, and `cron-automation-manager`; code proof is `test_auto_apply_entry_band_maintenance.py`.
- 2026-06-07: Randall approved implementation-efficiency skill hardening after the PM proof-budget work. Applied and corrected `disciplined-implementation` and `workspace-qa-pass` through Skill Workshop so live skills retain judgment/QA depth while routing repeated validator mechanics through `validation_budget` / `closeout_mode`. WF74 now treats clean, bounded, approved proposals left pending as a regression fixture.
- 2026-06-07: Randall approved applying Skill Workshop proposal `workspace-governor-20260608-a4535613aa`. `workspace-governor` now owns startup-surface compression rules: boot files route, detailed procedures live in skills/operating procedures, workflow state/history lives in workflow notes/capsules, script catalogs live in `scripts/README.md`, and chronological detail lives in `memory/YYYY-MM-DD.md`.
- 2026-06-08: Randall approved applying WF74 model-quality collection updates to `veritas-self-improvement` and `cron-automation-manager`. The live skill bodies now preserve their prior doctrine and add WF74 collection/cron sections: scheduled runner `scripts\wf74_model_quality_collection_cron_runner.py`, review-only ledgers, downgrade rules, and explicit blocks on model-ranking claims, WF55 outcome grading, portfolio/canon mutation, capital deployment, and paper/live/account action.
- 2026-06-08: Randall approved implementing the local training/eval candidate builder and applying the recommended skill enhancements. Applied Skill Workshop proposals `veritas-response-contract-20260608-916b10152e`, `disciplined-implementation-20260608-388716bc31`, `cron-automation-manager-20260608-c28330a694`, `memory-continuity-manager-20260608-36b288136b`, and `veritas-self-improvement-20260608-23cf18a63d`. The live skill bodies now preserve their prior doctrine and add guardrails for model-improvement claims, metadata-only candidate builders, no-training cron boundaries, memory redaction, and RSI-to-skill proposal routing.
- 2026-06-09: Randall approved strengthening `veritas-response-contract` after implementation closeouts. Applied Skill Workshop proposal `veritas-response-contract-20260610-83b8c3666b`, then immediately repaired the live skill with `veritas-response-contract-20260610-2e7a975881` after inspection showed the first proposal had replaced rather than merged the body. The restored live skill preserves prior finance/macro/WF78/canon/model-improvement response doctrine and adds implementation closeout proof clarity: richer top-level result descriptions, one-sentence validation-count meanings, and explicit unblock next steps for blockers or approvals.
- 2026-06-08 skills-backup recovery audit after old-baseline concern: compared live workspace skills against Randall's local `C:\Users\Veritas\Desktop\workspace\skills-backup` and merged missing durable sections without overwriting today's guardrails. Restored material backup sections in `veritas-response-contract` (market-state hardening, opportunity radar, WF78 tier-funnel pattern, leadership/research carry-forward), `cron-automation-manager` (WF75 PM continuation, Node/SQL cockpit, SQL coverage guard, consolidation posture, portfolio-agent and WF67 paper cron boundaries), `disciplined-implementation` (implementation size classes, system-aware standard, reuse/proof/flattening, artifact-format default, Windows/Node/skill-boundary/governance sections), `veritas-self-improvement` (WF74 reflection-to-proposal pipeline), and `workspace-qa-pass` (WF75 lens, default edit posture, good-pass standard). Preserved the newer June 7/June 8 proof-budget, entry-band, WF74, RSI, memory-to-dataset, and no-training candidate-builder guardrails.
- 2026-06-08: pending Skill Workshop proposal `ic-swarm-orchestrator-20260609-8ef558230e` adds verified Opus challenger routing for serious finance workflow gates. It requires actual subagent model path `claude-cli/claude-opus-4-8` before a lane counts as Opus proof; labels alone are not proof.
- 2026-06-09: Randall approved implementing skill-level intelligence-effort routing. Applied new skill proposal `veritas-intelligence-effort-router-20260610-54e9762382`, then hardened adjacent skills through Skill Workshop: `veritas-response-contract-20260610-b0a6eaac09`, `veritas-macro-pass-20260610-1274b4fcfe`, `veritas-positioning-pass-20260610-f8130719c8`, `veritas-fundamental-pass-20260610-b942cf98cc`, `veritas-technical-pass-20260610-4e828e08a9`, `veritas-pm-department-20260610-6249644657`, `cron-automation-manager-20260610-298ad9f6aa`, and `disciplined-implementation-20260610-50d6d707df`. The live posture is front-door artifact first, narrow refresh second, full integrated pass only when consequence/freshness/authority requires it, and Skill Workshop-only mutation for durable skills.
- 2026-06-09 all-skill governance pass found the prior hardening proposals had been applied with full `SKILL.md` content instead of body-only proposal content, creating duplicated frontmatter/tool-output wrapper lines in eight skills. Repaired through Skill Workshop with body-only proposals: `veritas-response-contract-20260610-4bd817ccd3`, `veritas-macro-pass-20260610-52910302cc`, `veritas-positioning-pass-20260610-759fdb2245`, `veritas-fundamental-pass-20260610-fe94081963`, `veritas-technical-pass-20260610-315d801936`, `veritas-pm-department-20260610-bf929dd133`, `cron-automation-manager-20260610-9a3123d0c4`, and `disciplined-implementation-20260610-a47595ad8d`. Follow-up recommendation: add an explicit body-only Skill Workshop update rule to implementation/QA guidance before future bulk skill updates.
- 2026-06-13: Randall approved applying Skill Workshop proposal `veritas-self-improvement-20260613-1c1ae70cbc`. `veritas-self-improvement` now adds the WF74 gated auto-patch proposal contract: refresh the WF74 evidence surfaces, classify findings into patch-plan or owner-gated routes, require lane lease plus scoped diff plus validator proof before any code patch, keep skill updates pending by default until explicit approval, and hard-block autonomous changes to doctrine, finance canon/portfolio state, account/action surfaces, credentials, runtime config, and Skill Workshop apply/install actions.
- 2026-06-13: Parallel implementation posture was tightened in core routing surfaces: new parallel lanes should default to PM/WF implementation slices, not QA/audit-only lanes; completed helper candidates should not be re-leased from stale recommender output; WF86/WF87 autonomous-paper work is now explicitly governed by shadow-decision/session accrual, GET-only reconciliation maturity, daylight/stale-gate clearance, fresh WF67 guard/kill-switch proof, and Randall exact approval. A matching `disciplined-implementation` Skill Workshop update should be applied only after explicit approval.
- 2026-06-14: Randall approved the audit/targeted-review skill set after ClawHub and web pattern review. Applied new `veritas-workspace-audit-orchestrator` plus updates to `workspace-governor`, `workspace-qa-pass`, `code-review-auditor`, and `memory-continuity-manager`; live skill validation reported 95 total skills, 53 visible/eligible, and 0 missing requirements. External skills were used as pattern sources only, not installed.
- Next governance focus should be validation-tier promotion for the core workflow skills rather than further overlap expansion.

## Department split

- Finance department: `veritas-fundamental-pass`, `veritas-technical-pass`, `veritas-macro-pass`, `veritas-positioning-pass`, `veritas-financial-planning-pass`, `veritas-portfolio-update`, `veritas-post-earnings-sync`, `veritas-weekly-brief`, `veritas-investment-deck`, `veritas-bounded-portfolio-agent`, and `wf67-paper-trading-operator`.
- Intelligence routing bridge: `veritas-intelligence-effort-router` is the cross-skill dispatcher for finance, PM, workflow, macro, cron, and implementation effort bands. It decides whether to answer directly, read a front-door artifact, refresh a narrow chain, run an integrated decision pass, or invoke proof-heavy implementation/Skill Workshop governance.
- SMB department: `smb-workflow-automation-operator` owns Workflow Clarity / Lead Rescue scenarios, fake-data practice, manual service packets, and automation blueprints.
- Product scaleout department: WF80-WF83 reuse existing skills rather than adding a new one. `veritas-pm-department` owns portfolio/priority framing; `smb-workflow-automation-operator` owns SMB service patterns; `veritas-response-contract` owns user-facing synthesis; `project-continuity-manager` owns pickup notes; `disciplined-implementation` owns scripts/validators; `workspace-qa-pass` and `automation-hardening-manager` own gates/QA. New product-scale skill creation requires a repeated workflow gap, not just a new product idea.
- PM bridge: `veritas-pm-department` owns prioritization, readiness posture, and queue framing across SMB and finance product lanes.
- Node / SQL cockpit bridge: `disciplined-implementation`, `SQLite`, `cron-automation-manager`, and `apps/pm-control-cockpit` own implementation, read-only SQL visibility, and reminder efficiency.
- Audit/governance bridge: `veritas-workspace-audit-orchestrator` owns full workspace audits and targeted finding reviews; `workspace-governor` owns structural residue; `workspace-qa-pass` owns independent QA and live-artifact reconciliation; `code-review-auditor` owns code/diff review; `memory-continuity-manager` owns daily/durable continuity hygiene.
- QA bridge: `workspace-qa-pass`, `code-review-auditor`, and `automation-hardening-manager` own review, stop-line checks, and automation boundary hardening.

## Planned Tier 2 pilot set

Workflow 29 should start with a narrow proof set instead of pretending the whole skill layer upgrades at once:
- `ic-swarm-orchestrator` -> completion-handshake proof **landed** via `scripts/swarm_completion_handshake.py` with local fail/pass verification on 2026-05-04
- `veritas-technical-pass` -> first sidecar validator pilot for a file-contract-heavy workflow skill **landed** via `scripts/veritas_technical_pass_validate.py` with local proof on 2026-05-04
- `automation-hardening-manager` + `cron-automation-manager` -> machine-readable trust-block producer/consumer pilot **landed** via `scripts/automation_trust_block.py` and `scripts/cron_trust_block_consumer.py` with local pass/fail samples on 2026-05-04

## No-skill-sprawl rule

Current canonical active workspace skill count: **35**.
Deprecated legacy fallback count: **1** (`technical-chart-pass`).

The count now exceeds 20, so additional new skills should require explicit governance justification. Prefer tightening existing skills or adding references before adding more skill directories.

Trigger a governance review when:
- the count exceeds 20
- a new skill overlaps an existing skill materially
- 3 or more skills cluster around one lane without a clear canonical owner
- a skill repeatedly needs operator explanation before use

When triggered:
1. update this index
2. classify affected skills as keep / merge / review / deprecate
3. avoid opening additional new skills until overlap is understood

Any time a workspace skill is added, removed, renamed, or materially repurposed:
1. update this index in the same workstream
2. run `openclaw skills check`
3. for skill-file edits, run `git diff --check -- skills`
4. update `TOOLS.md` or the owning route only when routing posture changed
5. record the change in the daily memory note when it materially affects operations

## Related standards
- `06. Playbooks/Skill Quality Standard.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
