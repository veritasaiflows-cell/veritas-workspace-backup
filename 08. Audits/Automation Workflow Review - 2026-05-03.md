# Automation Workflow Review - 2026-05-03

## Scope
- Reviewed automation governance, active workflow queue, cron protocol, finance cron jobs, generated run summaries, deployment readiness, and the Workflow 16 -> 16A -> 16B automation chain.
- Primary files reviewed:
  - `06. Playbooks/Automation Architecture Spec.md`
  - `06. Playbooks/Automation Orchestration Protocol.md`
  - `06. Playbooks/Cron Job Protocol.md`
  - `06. Playbooks/Cron Run Ledger.md`
  - `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
  - `06. Playbooks/IC Project Registry.md`
  - `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md`
  - `06. Playbooks/Project Continuity/Workflow 16A - Research Intake Desk and Parallel Review Packets.md`
  - `06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md`
  - `06. Playbooks/Project Continuity/Workflow 19 - Playbooks Retrieval and Governance Cleanup.md`
  - `tmp/run-summary-*.json`
  - `tmp/deployment-readiness-surface.json`

## Executive Truth
- Finance automation is operational at the scheduled artifact level. Current run summaries for morning, post-close, post-earnings, and Sunday windows are `status=ok`, `stop_line=false`, `chain_status=ok`, `critical=0`, `warning=0`, `acceptance_passed=true`, `presentation_allowed=false`, and `canonical_note_mutation_allowed=false`.
- The live architecture still authorizes Phase 1 and Phase 2 automation only by default: scheduled artifact generation and review/checklist surfaces are allowed now, while broader autonomous maintenance is not allowed by default (`06. Playbooks/Automation Architecture Spec.md:22`, `06. Playbooks/Automation Architecture Spec.md:25`, `06. Playbooks/Automation Architecture Spec.md:31`).
- Research automation is not implemented yet. Workflow 16 explicitly says implementation is still unstarted and that no recurring source bundle, intake packet, routing/promotion contract, or canonical freshness patch contract is approved (`06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md:12`).
- Workflow 16 is the active readiness gate. Workflow 16A is the next active implementation lane. Workflow 16B is queued behind 16A. Workflow 19 is queued behind the Workflow 16 family (`06. Playbooks/OpenClaw Parallel Pilot Queue.md:794`, `06. Playbooks/OpenClaw Parallel Pilot Queue.md:795`, `06. Playbooks/OpenClaw Parallel Pilot Queue.md:796`, `06. Playbooks/OpenClaw Parallel Pilot Queue.md:797`).
- Current cron delivery is internal-only / fail-closed rather than routed external delivery. That is acceptable for now, but it should not be mistaken for reliable user-facing delivery automation (`06. Playbooks/Cron Job Protocol.md:17`, `06. Playbooks/Cron Job Protocol.md:86`).
- Deployment readiness is clean enough for operator review but not autonomous presentation or note mutation. `tmp/deployment-readiness-surface.json` reports `macro_gate=DEGRADED`, `presentation_allowed=false`, and `canonical_note_mutation_allowed=false`.

## Findings

### F1 - High - Do not widen autonomy yet
The system has clean scheduled artifact runs, but it has not crossed the trust threshold for autonomous judgment, canonical note mutation, presentation output, or broader maintenance.

Evidence:
- Phase 1 scheduled artifact generation is allowed now (`06. Playbooks/Automation Architecture Spec.md:22`).
- Phase 2 review surfaces and sync checklists are allowed now (`06. Playbooks/Automation Architecture Spec.md:25`).
- Phase 4 broader autonomous maintenance is not allowed by default (`06. Playbooks/Automation Architecture Spec.md:31`).
- Trust-boundary fields must remain explicit in cron outputs (`06. Playbooks/Cron Job Protocol.md:86`).
- Current run summaries preserve `presentation_allowed=false` and `canonical_note_mutation_allowed=false`.

Truth:
- The automation layer is ready for artifact production and operator review.
- It is not ready for autonomous canonical changes or outward-facing presentation.

Recommendation:
- Keep `presentation_allowed=false` and `canonical_note_mutation_allowed=false` as hard gates until Workflow 16B proves the patch contract on a bounded pilot.

### F2 - High - Workflow 16 is still a readiness gate, not an implementation pass
Workflow 17 and Workflow 18 unblocked Workflow 16, but they did not implement research automation. Workflow 16 now needs to convert those governance outputs into the research automation skeleton.

Evidence:
- Workflow 16 says research automation remains unstarted implementation-wise (`06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md:12`).
- Workflow 16 says no research cron or note-helper execution should open yet (`06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md:14`).
- No new research cron should go live before source bundle, intake packet, and routing contracts are approved (`06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md:101`).

Truth:
- The next correct action is not scheduling a research cron.
- The next correct action is closing the Workflow 16 readiness gate and opening Workflow 16A under the inherited Workflow 17 / 18 governance.

Recommendation:
- Treat Workflow 16 as the handoff/gate pass. Do not let it become an implementation sprawl pass.

### F3 - High - Workflow 16A must define source and routing truth before any packet automation
Workflow 16A owns the contracts that prevent research automation from becoming a noisy second truth layer.

Evidence:
- Workflow 16A is queued behind Workflow 16 as the next active implementation lane (`06. Playbooks/Project Continuity/Workflow 16A - Research Intake Desk and Parallel Review Packets.md:9`).
- Workflow 16A owns source bundle, intake packet, and routing/promotion contracts (`06. Playbooks/IC Project Registry.md:34`).
- Workflow 16A safe automation boundary remains constrained and human-gated (`06. Playbooks/Project Continuity/Workflow 16A - Research Intake Desk and Parallel Review Packets.md:122`, `06. Playbooks/Project Continuity/Workflow 16A - Research Intake Desk and Parallel Review Packets.md:128`).

Truth:
- Without 16A, research automation has no reliable definition of what sources count, what materiality means, or where outputs should route.

Recommendation:
- Build 16A as a contract-first lane:
  - source bundle contract
  - intake packet schema
  - materiality and contradiction routing
  - promotion / no-promotion rules
  - stop lines for rumor, duplication, stale secondary reporting, and note-conflict risk

### F4 - High - Workflow 16B must remain patch-proposal only
Workflow 16B is the first place where canonical freshness patching becomes concrete, but the file correctly blocks auto-apply behavior.

Evidence:
- Workflow 16B is queued behind Workflow 16A contract completion (`06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:9`).
- Freshness patch is explicitly not a thesis rewrite (`06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:13`).
- Freshness patches may not automatically promote, bench, upgrade, downgrade, change deployment posture, or rewrite thesis (`06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:22`).
- No auto-apply behavior is allowed in v1 (`06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:124`).
- The pilot must stop if it behaves like a second truth layer (`06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:146`).

Truth:
- 16B can draft exact patch proposals.
- 16B cannot be allowed to mutate canonical notes without human approval and rollback proof.

Recommendation:
- Pilot 16B against a bounded set of high-signal cases only, such as NVDA timing confirmation, ETN near-earnings caution, GOOG/MSFT post-earnings freshness, JPM/GS deployability posture, and oil/Hormuz context for XOM.

### F5 - Medium - Cron evidence is operational, but the ledger is stale
The live artifacts are current as of 2026-05-03, but `Cron Run Ledger.md` still names 2026-05-02 proof timestamps for morning, post-close, and Sunday windows.

Evidence:
- Morning ledger evidence still points to 2026-05-02 artifacts (`06. Playbooks/Cron Run Ledger.md:49`).
- Post-close ledger evidence still points to 2026-05-02 artifacts (`06. Playbooks/Cron Run Ledger.md:59`).
- Sunday ledger evidence still points to 2026-05-02 artifacts (`06. Playbooks/Cron Run Ledger.md:69`).
- Current run summaries in `tmp/` are refreshed on 2026-05-03 and show `status=ok`.

Truth:
- This is not a runtime failure.
- It is a proof-surface freshness issue: the ledger lags the actual artifacts.

Recommendation:
- Refresh the ledger after this audit if the ledger is intended to be the operator proof surface. Otherwise, demote it to protocol history and make the run summaries / readiness surface the primary proof.

### F6 - Medium - Cron delivery remains fail-closed / internal-only
The current cron list shows jobs are scheduled and recent finance windows are `ok`, but delivery is not a dependable external notification surface.

Evidence:
- Cron protocol allows no-delivery or internal-only jobs for now (`06. Playbooks/Cron Job Protocol.md:17`).
- Trust boundary fields are required in outputs (`06. Playbooks/Cron Job Protocol.md:86`).
- Runtime/session state remains advisory beneath artifact-level proof, especially while memory index health is degraded (`06. Playbooks/Cron Job Protocol.md:104`).

Truth:
- Cron jobs can run.
- Artifact proof is stronger than delivery/session proof.

Recommendation:
- Keep cron acceptance based on file artifacts and run summaries, not chat delivery or session-memory behavior.

### F7 - Medium - Deployment readiness is review-grade, not action-grade
The deployment surface is clean from a validation standpoint, but it still carries operator-only constraints.

Evidence:
- `tmp/deployment-readiness-surface.json` reports `stop_line=false`, `warning_counts.critical=0`, `warning_counts.warning=0`, and `timestamp_gap_hours=0.1`.
- The same file reports `macro_gate=DEGRADED`, `presentation_allowed=false`, and `canonical_note_mutation_allowed=false`.
- NVDA is still held by timing-confirmation logic despite being in band.
- ETN is under near-earnings caution.

Truth:
- The surface is useful as an operator dashboard.
- It is not approved as an autonomous buy/sell/presentation trigger.

Recommendation:
- Keep action language out of automation outputs unless a human explicitly promotes the surface from review-grade to action-grade.

### F8 - Low - Workflow 19 should stay queued behind the Workflow 16 family
The playbooks cleanup lane is real, but activating it now would compete with the live research automation sequence.

Evidence:
- Workflow 19 is queued behind the Workflow 16 family (`06. Playbooks/OpenClaw Parallel Pilot Queue.md:797`).
- The registry says Workflow 19 should reopen after the Workflow 16 family unless retrieval friction becomes a real blocker (`06. Playbooks/IC Project Registry.md:35`).

Truth:
- Governance cleanup matters, but it is secondary to the current automation chain.

Recommendation:
- Do not activate Workflow 19 unless retrieval friction blocks Workflow 16 / 16A / 16B execution.

## Phased Plan

### Phase 0 - Freeze the current truth baseline
Objective:
- Establish the difference between "cron artifacts are clean" and "automation autonomy is approved."

Actions:
- Keep current finance cron windows running as artifact generators.
- Record that all current run summaries are `ok`, no stop-line, no critical/warning count, no presentation allowance, and no canonical mutation allowance.
- Decide whether to refresh `Cron Run Ledger.md` with 2026-05-03 evidence or leave it as protocol history.
- Avoid widening automation while the worktree/control surfaces are still moving.

Acceptance:
- One current proof surface names the latest run state.
- No file claims autonomous note mutation or presentation approval.

### Phase 1 - Keep existing finance automation stable
Objective:
- Preserve the working artifact chain without expanding blast radius.

Actions:
- Continue morning, post-close, post-earnings, and Sunday artifact refresh.
- Keep validation based on `tmp/run-summary-*.json`, `tmp/dashboard-validation.json`, `tmp/dashboard-acceptance-report.json`, `tmp/portfolio-config-validation.json`, and deployment readiness.
- Do not add per-ticker cron jobs yet.
- Do not schedule workbook/PDF packaging beyond the current export-manifest stage unless the packaging contract is separately upgraded.

Acceptance:
- Two consecutive relevant scheduled runs remain `status=ok`, `stop_line=false`, validation clean, and trust boundaries explicit.

### Phase 2 - Complete Workflow 16 readiness gate
Objective:
- Convert Workflow 17 / 18 governance outputs into the research automation skeleton without starting live research cron.

Actions:
- Confirm Workflow 17 and 18 outputs are inherited by Workflow 16.
- Define what Workflow 16 hands to 16A and what remains prohibited.
- Keep canonical mutation default-no.

Acceptance:
- Workflow 16 closeout explicitly opens 16A and does not open research cron or note-helper execution.

### Phase 3 - Execute Workflow 16A contracts
Objective:
- Define trustworthy research intake before automation produces packets.

Actions:
- Approve the source bundle contract.
- Approve the intake packet schema.
- Approve routing/promotion/no-promotion rules.
- Define stop lines for contradiction, weak sourcing, duplicate signal, low materiality, stale secondary source chains, and canonical note conflict.

Acceptance:
- A packet can say "route to note freshness review" without implying a thesis rewrite or action posture change.
- A packet can also say "no route" when materiality is too low.

### Phase 4 - Execute Workflow 16B patch contract and pilot
Objective:
- Prove exact, narrow freshness patch proposals without auto-applying anything.

Actions:
- Define the canonical freshness patch format.
- Define owner approval and rollback proof.
- Pilot on a bounded set of high-signal cases.
- Stop immediately if the output behaves like a competing canonical layer.

Acceptance:
- Patch candidates include source, old text, proposed replacement, affected canonical note, materiality reason, and rollback path.
- No auto-apply behavior exists.

### Phase 5 - Consider a scheduled research packet only after pilot proof
Objective:
- Add automation only where 16A / 16B prove a real signal-to-noise advantage.

Actions:
- If the pilot is clean, schedule a research packet generator after an existing refresh window rather than creating many event-specific cron jobs.
- Keep output as an artifact only.
- Continue routing through human review.

Acceptance:
- The packet reduces stale-note risk without increasing false urgency or duplicate work.

### Phase 6 - Consider gated mechanical note helpers
Objective:
- Allow only narrow, reversible canonical freshness changes after explicit approval.

Actions:
- Start with mechanical freshness classes only, such as confirmed dates, elapsed earnings state, source links, or "review needed" markers.
- Require human approval, exact patch preview, validation, and rollback.
- Keep thesis, deployment posture, promotion/bench state, and target sizing outside automation.

Acceptance:
- A helper can draft a patch, but cannot commit it without approval.

### Phase 7 - Revisit presentation, workbook/PDF packaging, and broader maintenance
Objective:
- Upgrade outward-facing surfaces only after upstream trust is proven.

Actions:
- Reassess `presentation_allowed` only after the note-freshness and deployment-readiness contracts are stable.
- Reassess scheduled workbook/PDF packaging only after the export/build contract is clean and non-stale.
- Reassess broader autonomous maintenance only after repeated clean cycles and explicit trust-gate promotion.

Acceptance:
- Presentation and packaging outputs are not generated as decision-grade artifacts until the source and canonical truth layers are already stable.

## Recommendations
- Treat the current automation state as "artifact automation is working; judgment automation is not approved."
- Keep the Workflow 16 family sequential: Workflow 16 readiness gate, then Workflow 16A contracts, then Workflow 16B patch/pilot.
- Refresh `Cron Run Ledger.md` or stop treating it as the live proof surface.
- Do not add per-ticker or event-specific cron jobs until the research packet contract proves signal quality.
- Use existing scheduled finance windows as the anchor for any future packet generation.
- Keep `presentation_allowed=false` and `canonical_note_mutation_allowed=false` until a future audit can cite approved 16B pilot evidence.
- Keep Workflow 19 queued unless playbook retrieval friction directly blocks the Workflow 16 family.

## Next Concrete Action
Run the Workflow 16 readiness gate closeout, then open Workflow 16A as the next active implementation lane. The first 16A deliverable should be the source bundle contract, because every later packet, route, and patch depends on source trust.

