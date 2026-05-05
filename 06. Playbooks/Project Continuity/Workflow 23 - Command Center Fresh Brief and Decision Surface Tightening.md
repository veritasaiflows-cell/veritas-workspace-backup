# Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening

## Objective
- Tighten the Command Center / dashboard layer so fresh briefs, open decision points, and easy report-intelligence access are visible without turning the Command Center into a second conflicting truth layer.
- Use the outputs of WF21 and WF22 to improve orientation, review access, and freshness visibility.
- Keep Command Center as an access and decision-surface layer, not a truth-owner.

## Current State
- `01. Dashboards/Executive Brief.md` and `01. Dashboards/This Week.md` already define the orientation layer.
- Workflow 21 will generate review packets for daily / weekly evidence intake.
- Workflow 22 will generate bounded freshness-patch proposals for stale/alignment issues.
- The Command Center / dashboard layer still needs tighter linkage to fresh briefs, explicit decision points, and report-intelligence access surfaces.

## Scope
- define which fresh brief outputs should surface in Command Center
- define which decision points should appear there and with what trust language
- define how report-intelligence artifacts are linked for easy retrieval
- keep the dashboard layer aligned with review outputs without pretending they are canon

## Out of Scope
- turning Command Center into a canonical note owner
- auto-publishing decision-grade reports from review packets alone
- replacing Portfolio Snapshot, Risk Rules, or Weekly Positioning Review as truth owners

## Sequential phase approach

### Phase 1 - Surface map
- identify the specific Command Center / dashboard surfaces to tighten
- map their truth owners and allowable derived inputs

### Phase 2 - Fresh brief and decision-point contract
- define how daily post-close review packets and Sunday weekly packets become visible orientation items
- define how unresolved truths and freshness warnings stay visible without fake certainty

### Phase 3 - Report-intelligence access layer
- define how weekly briefs, scorecards, patch proposals, and other report artifacts are linked for fast operator retrieval

### Phase 4 - Validation and trust check
- confirm the Command Center remains derived, honest, and easy to use

## Dependency order
- wait for WF21 manual packet flow to be real
- then wait for WF22 freshness-patch candidate flow to be real
- then tighten the Command Center around those proven outputs

## Immediate planning note
The two bounded scripts help this workflow by creating better upstream objects:
- `research_intake_packet.py` produces structured daily / weekly review packets that can feed fresh-brief inputs and explicit open questions
- `canonical_freshness_patch.py` produces narrow stale-surface proposals that can feed dashboard freshness warnings and decision-point cleanup queues
