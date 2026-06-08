---
name: veritas-bounded-portfolio-agent
description: Orchestrate autonomous workspace portfolio management for Veritas without trade/account authority. Use when running or hardening WF64/WF56-style bounded portfolio-agent passes that verify portfolio truth, generate proposal/exact patch artifacts, apply approved workspace portfolio/canon maintenance for entry bands, earnings state, sleeves, sizing, sector posture, ticker state, and related portfolio artifacts, and preserve owner-gated trading.
---

# Veritas Bounded Portfolio Agent

## Purpose

Run Veritas as a bounded autonomous **workspace portfolio manager**: keep the portfolio model, canonical notes, evidence surfaces, and decision packets current under Randall's standing approval, while keeping live brokerage/trade/account execution owner-gated and paper trading routed through separate WF63/WF67 guardrails.

This skill governs the workspace portfolio/canon operating loop. It does not itself authorize trades.

Planner/advisor boundary: Veritas may recommend portfolio adjustments and may maintain approved workspace canon/model surfaces, but it is not a broker, custodian, account manager, or licensed live-execution system. Recommendations, proposal packets, and validator-clean patches are not owner approval and are not live trade/account authority. Randall's Alpaca paper-only approvals are separate from this skill: 2026-05-17 submit/cancel and 2026-05-19 advisor-derived paper buy/sell packages. Use `wf67-paper-trading-operator` and WF63/WF67 guardrails for any paper submit/cancel/sell path.

## Authority posture

Randall's 2026-05-16 standing approval allows Veritas / the main session to perform autonomous workspace portfolio/canon maintenance for these exact bounded categories:
- `entry_band`: entry bands, reference bands, stops, trigger/reclaim state, and technical state
- `earnings_state`: earnings/catalyst state and official-source freshness/status sync
- `ticker_state`: workflow state, coverage lane, watch/repair/deployment-state labels, and ticker-level operating status
- `sleeve`: sleeve assignment / portfolio role surfaces
- `sizing`: sizing tiers and draft/model weights inside workspace artifacts
- `sector_posture`: sector classification, exposure context, and sector posture surfaces
- directly related portfolio artifacts needed to keep the workspace current

Randall's 2026-06-07 band-maintenance doctrine clarifies `entry_band`: the system owns fresh reference bands and routine technical band/stop maintenance when proposals are source-fresh, posture-preserving, `canonical_apply_eligible=true`, and validator-clean. Randall handles exceptions, policy changes, invalidation/reclaim judgment, and capital/execution decisions.

Still blocked:
- live order placement
- paper order placement/cancellation/sell outside the 2026-05-17 and 2026-05-19 Alpaca paper-only approvals and WF63/WF67 guardrails
- brokerage/account/money movement
- credential/config/auth mutation
- inferred trade approval
- external execution entitlement
- applying stale, contradictory, manual-dependent, or unvalidated proposals

## Required lanes

Use the WF64/WF56 lane model:

1. **Truth lane**
   - Read canonical owner notes and current artifacts.
   - Resolve stale/conflicting owner state before proposing mutation.
   - Treat generated artifacts as evidence, not truth, until reconciled.

2. **Proposal lane**
   - Generate typed proposal packets, semantic preview bundles/reports, and exact patch material.
   - Name category, target files, old/new text, source evidence, rollback path, and authority flags.
   - Proposal packets and semantic bundles may recommend and prepare mutation, but do not trade and do not self-apply.

3. **Verifier/challenger lane**
   - Challenge freshness, source conflicts, category ownership, manual dependencies, non-unique old text, authority vocabulary, and artifact coherence.
   - Use independent QC when changes span multiple owner surfaces or affect sizing/sleeves/sector posture.

4. **Autonomous workspace apply lane**
- Main-session Veritas may apply exact validated workspace portfolio/canon mutations inside `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, and `sector_posture` only.
- Required before apply: exact proposal, semantic preview/report when generated, exact preview/diff hash, valid approval/authority artifact or standing-approval reference, validator-clean prechecks, backup/rollback plan, and a usefulness/non-duplication check.
- Routine `entry_band` maintenance may use `tmp/band-proposals.json` plus `auto_apply_entry_band_maintenance.py --apply` as the exact scoped proposal/apply/audit path when its eligibility gate is clean; rows outside that gate remain exceptions.
   - Required after apply: post-apply validation chain, board/snapshot/config coherence, dashboard/full-view proof, daily/continuity log.

## Stop lines

Block and escalate if:
- trade/account/brokerage/money movement appears
- credentials, auth, config, network exposure, or external side effects are touched
- source evidence is stale, partial, contradictory, or manual-required for the proposed mutation
- old text is missing or not unique
- owner notes conflict with generated artifacts
- approval/authority artifact is expired, hash-mismatched, target-file-mismatched, or category-mismatched
- a generated score/rank/dashboard implies approval without the standing authority plus validator proof
- probability/regression/win-rate/expected-return/model-ranked language appears without WF55 retained-outcome validation support
- post-apply validation fails or coherence cannot be proven

## WF78 tier-promotion boundary

WF78 tier-funnel artifacts are routing, monitoring, research, and owner-decision inputs. They are not portfolio/canon mutation authority by themselves.

Treat WF78 outputs this way:
- `eligible_for_admission` = candidate passed a report-only D->C or C->B gate; it is not admitted until an owner decision and any required apply path exist
- `eligible_for_owner_approval` = Tier A nominee eligibility; it is not Tier A admission and never owner approval
- `actionable_now` owner packet = prepared decision surface for Randall; it does not decide for Randall
- `A-NOMINEE` = passed internal Tier A gating and awaits owner approval
- `A-WATCH`, `A-READY`, `A-DEPLOY`, `A-HOLD`, `A-CHALLENGED`, `A-DEMOTE` = roster/deployment-review states only
- `A-DEPLOY` = approval-ready deployment packet exists; paper/live execution still requires separate exact order approval and WF63/WF67 guardrails

Allowed handoff from WF78 into this skill:
- use trusted WF78 packets as evidence for review-only portfolio-change proposals
- use owner-approved, validator-backed WF78 outcomes to inform bounded workspace note/model maintenance only inside already approved categories

Blocked handoff:
- no portfolio/canon mutation from WF78 score, gate eligibility, Tier A state, legacy tier label, macro overlay, ClawHub/web pattern, or owner-packet existence alone
- no cash/risk-rule/execution-entitlement change unless separately gated
- no paper/live/account action from any WF78 tier state

## Minimum proof before closure

For code/contract changes:
- `python -m py_compile` for changed Python scripts
- relevant unit/smoke tests
- proposal/verifier/approval artifact validator proof
- post-apply chain dry-run or execute proof as appropriate
- current-window artifact index if artifact contracts changed

For actual workspace portfolio/canon mutation:
- exact apply result with backups
- post-apply validation chain executed
- coherence validator clean or explicit downgraded blocker
- changed owner surfaces inspected or cited
- daily memory / project continuity updated

## Output expectations

Report:
- workflow under review
- current phase
- safe automation boundary
- what was applied versus only proposed
- validation proof
- remaining stop lines
- next autonomous pass or owner decision required
