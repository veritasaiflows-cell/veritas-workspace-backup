# Research Department Downstream Handoff Contract

## Purpose
Define what the research department must receive from upstream automation and what it may hand off downstream after a WF25 review is decided.

This contract keeps WF21 and WF26 subordinate to the desk instead of letting packet automation or fresh-news flow invent its own destination.

## Core rule
Research packets and fresh-intelligence objects may prepare evidence.
They do not decide tracked-universe admission, promotion, demotion, portfolio posture, or command-center truth on their own.

## Required upstream inputs from WF21
Before a recurring research packet is allowed to feed the desk, it must provide:
- one explicit ticker or theme target
- source tier and confidence labels per `Research Automation Intake Packet Contract.md`
- materiality level
- thesis-impact summary
- contradictions / uncertainty section
- recommended routing
- stop-line status
- named owner surface if the packet argues for desk review

Minimum acceptable use by desk:
- **new-name intake** -> packet may nominate a candidate, but WF25 still decides admit / defer / reject
- **promotion/demotion review** -> packet may flag a role-change candidate, but WF25 still decides promote / hold / demote / remove
- **no-route item** -> archive without forcing a desk case

## Required upstream inputs from WF26
Before fresh external intelligence is allowed to pressure the desk, it must provide:
- approved source class
- verification posture
- unresolved-truth handling
- explicit statement of why the development matters to an active name, sleeve, or macro desk
- explicit statement when the event is still too noisy for a desk-level review

Desk rule:
- fast-moving geopolitical or news events may open a review object only when they survive the verification contract; otherwise they stay review-first and unresolved

## Allowed downstream outputs from the research department
After WF25 review is decided, the desk may hand off only these outputs:
- **admit to watch** -> update `Coverage and Watchlist` and machine-tracked universe if approved
- **promote / hold / demote / remove** -> update only the owner surfaces the decision actually changes
- **thesis-review needed** -> route to the appropriate research note owner without implying deployment approval
- **portfolio / deployment review required** -> hand off to `Execution Board` or `Portfolio Snapshot` owners for separate judgment
- **command-center visibility candidate** -> only after the owner surfaces are updated and the state is already true elsewhere

## Not allowed
- direct packet-to-command-center promotion
- direct packet-to-deployment-state promotion
- direct packet-to-portfolio-weight change
- direct packet-to-canonical-note mutation without owner-layer approval
- direct news-event routing that bypasses desk review

## Decision object outputs required from WF25
Every admission or promotion review should conclude with:
- candidate
- decision
- decision reason
- owner surfaces changed or intentionally unchanged
- next review condition
- whether downstream portfolio/deployment review is required
- whether command-center or weekly-brief visibility is warranted

## Current pilot interpretation
- **EOG** proved the desk can reject a new name when the role is weak and the catalyst is noisy.
- **GS** proved the desk can hold a name at tactical-secondary status even when execution signals look green.

## Use in workflow sequence
- WF25 owns the desk decision.
- WF21 and WF26 feed it.
- WF22 and WF23 may consume already-approved owner-surface changes later.
