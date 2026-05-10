# Workflow 37 - Daily Summary Commercial Brief Hardening

## Objective
- Harden the daily summary stack so pre-market and post-close summaries become more commercial and decision-grade without creating a second truth layer.
- Keep deterministic snapshot writers as the evidence pack.
- Add bounded agent-ready packet inputs and review-only commercial brief generation on top of those packets.

## Current State
- paused with follow-up as of 2026-05-06 after Randall explicitly moved the active queue to WF38
- current stack already has stable deterministic writers:
  - `scripts/premarket_snapshot.py`
  - `scripts/postmarket_snapshot.py`
  - `scripts/daily_executive_brief.py`
- the first real hardening slice is now in place:
  - malformed source-status delta rendering is fixed across the deterministic summary stack
  - post-close daily summary wording no longer mislabels overnight futures context as an open read
  - bounded AI handoff packets now exist for both morning and post-close windows
  - those review-only packets are now wired into the scheduled `morning` and `post-close` chains
- Option 2 is now the approved path: deterministic fact packs plus bounded AI-written review briefs

## Last Meaningful Progress
- WF23 closed with follow-up after live dashboard overlap was reduced to owner-first orientation language and an independent closeout audit confirmed the second-truth-layer risk was materially resolved
- WF37 Phase 1 packet slice landed and was proved live:
  - `scripts/dashboard_delta_render.py` now centralizes human-safe delta rendering across the summary stack
  - `scripts/premarket_snapshot.py`, `scripts/postmarket_snapshot.py`, and `scripts/daily_executive_brief.py` were hardened to render prior-run deltas more honestly
  - `scripts/daily_executive_brief.py` now uses `Overnight futures context` wording instead of a misleading `Directional open read` label in the post-close brief
  - `scripts/summary_brief_packet.py` now emits review-only AI handoff packets for `morning` and `post-close`
  - live proof ran cleanly: `py_compile` passed, `tmp/premarket-brief-input.json` and `tmp/postclose-brief-input.json` were generated, and the refreshed summary notes now render source-status deltas without malformed blank lines
- WF37 Phase 2 contract is now explicit in `06. Playbooks/WF37 Phase 2 Bounded Agent Writer Contract - 2026-05-06.md`
- WF37 Phase 3 validator proof is now explicit in `06. Playbooks/WF37 Phase 3 Brief Lint and Guard Proof - 2026-05-06.md`; `scripts/summary_brief_lint.py` passed a safe draft and correctly failed an unsafe draft with the expected authority-drift findings
- WF37 Phase 4 first writer-trial proof is now explicit in `06. Playbooks/WF37 Phase 4 First Writer Trial Proof - 2026-05-06.md`; both the first pre-market and first post-close review-only drafts passed lint after a real false-positive fix in the validator
- WF37 Phase 5 manual-review posture is now explicit in `06. Playbooks/WF37 Phase 5 Manual Review Posture and Output Path - 2026-05-06.md`; scheduled chains now auto-generate `tmp/premarket-brief-input.json` and `tmp/postclose-brief-input.json`, while `tmp/run-summary-morning.json` and `tmp/run-summary-post-close.json` now carry a `review_only_brief` block that tells the operator the packet is ready and that draft generation/delivery still remains manual/review-only
- a dedicated non-canonical draft location now exists at `01. Dashboards/Review-Only Briefs/Pre-Market/` and `01. Dashboards/Review-Only Briefs/Post-Close/`; this is the intended home for future human-readable review drafts instead of leaving them in `tmp/`

## Scope
- define the owner-safe commercial brief architecture for daily windows
- produce machine-readable writer packets for pre-market and post-close windows
- keep summaries commercial-grade while preserving owner-note authority
- add the smallest validation and routing rules needed to stop shadow-canon drift

## Out of Scope
- direct owner-note mutation from AI-written briefs
- autonomous deployable-state publication
- direct trade instruction or portfolio-authority language
- cron promotion before repeated clean review-only proof exists

## Preflight / Entry Checklist
- [x] WF23 dashboard-layer overlap risk is honestly closed enough to expand
- [x] deterministic summary stack exists and is producing live artifacts
- [x] Option 2 (fact pack + bounded AI brief) is explicitly approved
- [x] current trust boundary is explicit: snapshots stay evidence-first; owners stay canonical
- [ ] repeated review-only packet + brief proof exists for both windows
- [ ] validator / lint rules fully cover commercial-brief authority drift

## Execution Posture
- main session owns workflow contract, authority boundaries, and final integration
- bounded helper lanes are appropriate for packet/brief contract challenge, writer QA, and closeout audit
- new automation remains review-only until proof is repeated and clean

## Acceptance Gates
- one bounded Phase 1 artifact names the summary surfaces, owner layers, allowed claims, forbidden claims, and stop lines
- machine packets exist for `morning` and `post-close` windows with explicit `review_only` posture
- deterministic summary outputs no longer emit malformed delta lines on source-status changes
- post-close daily summary no longer uses misleading morning/open wording
- first proof run shows packet artifacts generated cleanly from current live inputs
- control surfaces stay honest about residue: no cron/native agent promotion yet

## Sequential phase approach

### Phase 1 - Packet and owner-boundary contract
- define target outputs, owner layers, trust block, and allowed / forbidden claim shapes
- produce review-only machine packets for morning and post-close

### Phase 2 - Bounded agent-writer contract
- define the exact writer prompt contract, sentence-shape limits, and provenance/citation rules
- decide canonical path for a pre-market brief and how post-close commercial prose coexists with the existing machine daily summary

### Phase 3 - Validator and proof pass
- add the smallest honest lint / validator checks for forbidden authority claims and missing owner routing
- run bounded proof over both windows

### Phase 4 - Schedule posture decision
- decide whether the agent-written brief remains manual/review-triggered or is ready for scheduled review-only generation

## Dependency order
- deterministic writers first
- packet contract second
- bounded agent writer third
- validator / proof fourth
- schedule decision last

## Exit / Closeout Checklist
- [x] Phase 1 packet/owner-boundary artifact exists
- [x] first packet producer implementation landed
- [x] adjacent deterministic consumers were scanned and hardened for obvious delta/render drift
- [x] packet outputs proved clean on live artifacts
- [x] writer contract artifact exists
- [x] validator / lint proof exists
- [x] first review-only writer trials passed for both windows
- [x] queue / registry / memory aligned with real WF37 state

## Checkpoint Decision
- paused with follow-up - Phase 6 repeated-run proof and delivery-posture decision remains open, but WF38 is now the active workflow

## Next Action
- resume only when daily-summary brief hardening becomes the priority again: prove repeated clean review-only runs for both windows under the scheduled packet generation posture, then decide whether the `Review-Only Briefs` folders are stable enough to become the standing manual-draft path.

## Next Pass
- Keep scheduled promotion fail-closed until repeated clean runs exist and a delivery posture is intentionally approved.

## Next 1-2 Adjacent Candidate Workflows
- Workflow 38 - Sector Expansion and Promotion Review Hardening is now the active bounded lane
- any later summary-scheduler widening must still wait for clean packet and writer proof

## Key Files
- `06. Playbooks/Project Continuity/Workflow 37 - Daily Summary Commercial Brief Hardening.md`
- `06. Playbooks/WF37 Phase 1 Brief Packet and Owner-Boundary Contract - 2026-05-06.md`
- `06. Playbooks/WF37 Phase 2 Bounded Agent Writer Contract - 2026-05-06.md`
- `06. Playbooks/WF37 Phase 3 Brief Lint and Guard Proof - 2026-05-06.md`
- `06. Playbooks/WF37 Phase 4 First Writer Trial Proof - 2026-05-06.md`
- `06. Playbooks/WF37 Phase 5 Manual Review Posture and Output Path - 2026-05-06.md`
- `scripts/dashboard_delta_render.py`
- `scripts/summary_brief_packet.py`
- `scripts/summary_brief_lint.py`
- `scripts/premarket_snapshot.py`
- `scripts/postmarket_snapshot.py`
- `scripts/daily_executive_brief.py`
- `scripts/README.md`
- `01. Dashboards/Pre-Market Snapshot/`
- `01. Dashboards/Post-Market Snapshot/`
- `01. Dashboards/Daily Executive Summary/`
