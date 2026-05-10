# Operator Responsibilities

## Purpose
Summarize Randall's practical responsibilities in plain English when using the Veritas OS.

## Your role
You are the operator, final decision-maker, and approval gate.
The system helps you:
- gather evidence
- maintain the research stack
- stage summaries and review packets
- surface warnings and unresolved truths

The system does **not** replace your judgment on:
- portfolio posture changes
- deployment decisions
- blocker clearance
- trust widening
- automation promotion

## Your main responsibilities

### 1. Keep authority straight
- Canonical owner notes win over dashboards, packets, and polished summaries.
- If a pretty output conflicts with an owner note, treat the pretty output as subordinate until fixed.

### 2. Approve automation widening deliberately
- Read-only artifact generation is easier to approve.
- Anything that writes canon, delivers autonomously, or expands authority needs a higher bar.

### 3. Treat warnings as real
- If validation says warning, partial, stale, or unresolved, do not silently convert that into confidence.
- Credit, event timing, and macro warnings should visibly downgrade trust.

### 4. Use review-only layers correctly
- Review-only packets and briefs are for orientation.
- They are not permission slips to act.

### 5. Keep the queue honest
- Open the next workflow only after the current one is really closed.
- Do not advance from memory, vibes, or implied completion.

## When to ask Veritas directly
Ask directly instead of running scripts yourself when you want:
- today's review-only pre-market brief
- today's review-only post-close brief
- a workflow status check
- a cron/scheduler trust decision
- help interpreting residue or warnings

## When script-level operation makes sense
Run scripts yourself only when:
- debugging
- validating a narrow chain step
- deliberately operating at the CLI layer

## Escalation rule
Pause and ask for a higher-trust review when:
- a summary appears to grant authority it should not own
- the system wants to widen automation after only one or two clean runs
- a workflow appears closed in one surface and open in another
- a note mutation would be irreversible or decision-sensitive
