# Deployment Readiness Morning Operating Cadence

## Purpose

Define the exact operator use pattern for the deployment-readiness machine surface without letting it outrank the canonical Trigger Sheet.

## Owner boundary

- Canonical deployment judgment lives in `03. Portfolio/Deployment Trigger Sheet.md`
- Machine support artifact lives in `tmp/deployment-readiness-surface.json`
- Run-summary trust state lives in `tmp/run-summary-<window>.json`
- If the machine artifact and the Trigger Sheet disagree, the Trigger Sheet wins and the mismatch becomes QA work rather than silent override

## Window routing

Use the window that matches the operating moment:

- `morning` -> trading-day premarket deployment review
- `post-close` -> post-close cleanup / next-day staging
- `sunday` -> weekly staging only, not live deploy-today judgment

Do not treat the Sunday surface as a substitute for a trading-day morning decision pass.

## Morning operator checklist

1. **Trust preflight**
   - confirm the chosen `tmp/run-summary-<window>.json` exists
   - require `status = ok`
   - require `execution.chain_status = ok`
   - if `stop_line = true`, stop deployment review and treat the session as `SYSTEM HOLD`

2. **Freshness preflight**
   - read `generated_at_utc` from the run summary and `trigger_generated_at_utc` from `tmp/deployment-readiness-surface.json`
   - if the timestamp gap is material or the surface is clearly stale for the intended window, treat the artifact as advisory-only and do not upgrade any name on its authority

3. **Validation preflight**
   - require dashboard validation to stay clean or honestly degraded
   - if critical warnings appear, stop at contradiction / blocker review rather than candidate promotion

4. **System posture check**
   - read `canonical_note_mutation_allowed`
   - scheduled windows remain fail-closed in v1; this artifact supports review only
   - read `macro_gate`; if degraded, preserve caution and do not force borderline names

5. **State review order**
   - review in this order:
     1. `SYSTEM HOLD`
     2. `DO NOT TOUCH`
     3. `BLOCKED`
     4. `ALMOST / NEAR-EARNINGS CAUTION`
     5. `POST-EARNINGS REVIEW`
     6. `ALMOST DEPLOYABLE`
     7. `DEPLOYABLE NOW`
   - this prevents positive ranking from hiding trust or event-risk residue

6. **Trigger Sheet cross-check**
   - for any name that appears decision-relevant, cross-check `03. Portfolio/Deployment Trigger Sheet.md`
   - if the note is stricter than the machine surface, keep the stricter note-layer judgment
   - if the note is looser than the machine surface, do not loosen automatically; review the contradiction explicitly

7. **Human decision points**
   - confirm thesis gate
   - confirm macro/regime gate
   - confirm technical trigger / no-chase discipline
   - confirm catalyst risk is acceptable
   - confirm size and invalidation under `07. Risk/Risk Rules.md`

8. **Output rule**
   - if nothing materially changed, do not churn the Trigger Sheet
   - if a real state changed, update the Trigger Sheet explicitly and briefly explain the reason
   - if evidence is incomplete, log the contradiction or review need rather than forcing a state change

## Escalation rules

Escalate to contradiction review instead of action when:
- a date-sensitive catalyst is unconfirmed inside the active window
- the machine surface says `DEPLOYABLE NOW` but the Trigger Sheet still says `Almost`, `Blocked`, or `Do not touch`
- validation turns warning/critical in a way that can contaminate deployment state
- a name is in band but macro/policy trust is degraded enough to undermine confidence

## Proof rule

The machine surface may support deployment review only when:
- the relevant run summary is terminal and usable
- the stop line is not active
- validation is not in contradiction with the candidate state
- the Trigger Sheet either already agrees or is being explicitly reviewed for a justified change

The machine surface may **not**:
- mutate canonical notes on its own
- outrank the Trigger Sheet
- substitute for explicit event-risk or sizing judgment
- convert a timing-uncertain name into a full green light by ranking alone

## Handoff rule

Helper lanes may prepare evidence or contradiction packets, but only the main session may reconcile those packets into a proposed Trigger Sheet update against the workspace-file truth layer. The durable Trigger Sheet remains a file-owned decision surface; chat is only a reconciliation interface.
