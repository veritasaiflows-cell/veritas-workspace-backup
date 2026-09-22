# Post-Earnings Vault Update Workflow Prompt v1

## Purpose

Use this workflow after a material tracked earnings event.

This is an agent-facing prompt layer, not a script. The scripts prepare hard data and candidate update scope. The agent interprets the evidence and decides what actually changes in the vault.

## Hard boundary

- Scripts prepare.
- The agent interprets.
- Notes are the decision layer.
- Do not let scripts silently rewrite the vault.
- Do not touch files that are not materially affected.

## Required prep sequence

Run these from the workspace root before updating notes:

```text
python scripts/technical_refresh.py
python scripts/earnings_calendar_enrichment.py  # when the earnings-date map may have shifted
python scripts/deployment_check.py
python scripts/trigger_sheet_refresh.py
python scripts/post_earnings_prep.py
python scripts/post_earnings_note_targets.py
```

Use the following outputs as the machine-readable evidence stack:
- `tmp/technical-refresh.json`
- `tmp/market-state.json`
- `tmp/earnings-calendar.json`
- `tmp/deployment-check.json`
- `tmp/trigger-sheet.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`

## Freshness discipline

Before trusting the outputs:
- check stale flags
- check partial status
- check warnings
- downgrade confidence explicitly when inputs are incomplete

Do not present:
- hardcoded Fed target fields as live feeds
- missing FedWatch as if it exists
- best-effort pre-market snapshots as true tape
- unresolved earnings dates as confirmed facts

## Closure-state model

Use one explicit closure state for each material tracked earnings event. The state should be practical, visible, and easy to advance.

### States

1. **Prepared**
   - Pre-event packet exists and the name is in scope.
   - Required evidence stack is fresh enough to trust directionally.
   - Pre-earnings blocker or event posture is visible in the note layer.

2. **Reported, evidence pending**
   - The event happened, but the result is not yet interpreted cleanly.
   - The note layer may say reported, but it must also say interpretation is pending.
   - Do not imply closure yet.

3. **Interpreted**
   - The three-part line exists for the name:
     - what happened
     - what it means
     - what we do now
   - Thesis, blocker, and read-through implications are clear enough to act on.

4. **Synced**
   - The required note targets have been updated selectively.
   - At minimum, `05. Intelligence/Event Calendar.md` is updated for material tracked earnings.
   - Any other changed decision surfaces are updated only if the report materially changed them.

5. **Closed with follow-up**
   - Interpretation and note sync are done, but a real follow-up remains open.
   - Use this when the report is processed but the setup still needs a later step, such as:
     - post-earnings base repair
     - EIA follow-through for XOM
     - date confirmation for timing-sensitive names
     - waiting for the next session to judge the reaction structure

### Advancement rule

Advance only when the prior state is actually complete.
Do not skip from prepared to synced unless the interpretation was written and the note layer shows it.
If evidence is missing, stop at **reported, evidence pending**.
If interpretation is done but affected notes are still stale, stop at **interpreted**.

## Required handoffs

1. **Prep handoff**
   - `post_earnings_prep.py` defines the tracked packet and evidence window.
   - Failure if the name is still treated as pre-event after the event occurred.

2. **Scope handoff**
   - `post_earnings_note_targets.py` narrows candidate note targets.
   - Failure if the file map exists but nobody performs the selective note pass.

3. **Interpretation handoff**
   - The agent reads the evidence and writes the three-part decision line.
   - Failure if notes say reported without saying what changed.

4. **Note-sync handoff**
   - The agent updates only the note layer that truly changed.
   - Failure if `Event Calendar.md` still shows the event as upcoming or refresh-due after the event already happened.

5. **Closure handoff**
   - The agent labels the event as synced or closed with follow-up and makes any remaining dependency explicit.
   - Failure if the report is partially absorbed across notes with no visible closure state.

## Likely failure points

- `earnings-calendar.json` still carries the old date or missing date, so the prep packet stays in a pre-event stage after the report.
- The prep packet exists, but `interpretation_slots` remain empty and no agent pass closes them.
- `post-earnings-note-targets.json` names candidate files, but the event calendar or trigger sheet is not actually updated.
- A daily card mentions the result, but the canonical note layer never advances to synced state.
- A name clearly needs later follow-up, but that dependency stays implicit instead of being recorded as **closed with follow-up**.

## Interpretation standard

For each material reported name, preserve a concise three-part interpretation:

1. **What happened**
   - beat / inline / miss when knowable
   - guidance raised / maintained / cut when knowable
   - if not knowable, say evidence is incomplete

2. **What it means**
   - thesis impact
   - sector or peer read-through
   - whether confidence improved, weakened, or is still unresolved

3. **What we do now**
   - wait
   - keep blocked
   - promote
   - demote
   - reassess levels
   - follow-up pending

If evidence is mixed, say so plainly.
If evidence is incomplete, mark interpretation pending.
Do not fake closure.

## Selective update rule

Use `tmp/post-earnings-note-targets.json` to decide which notes are actually candidates.
That file narrows the scope. It does not force every candidate file to change.

Update only when the earnings result materially changed:
- action state
- blocker status
- thesis quality
- technical posture
- risk framing
- ranking or conviction
- durable act-when conditions

## File-specific rules

### `05. Intelligence/Event Calendar.md`
Update when:
- the event has now reported or resolved
- a concise decision line can be written

Write:
- reported marker
- short what happened line
- short decision implication

### `05. Intelligence/Weekly Intelligence Brief.md`
Update when:
- the report changes company thesis
- the report changes sector read-through
- the report changes near-term posture or recommended actions

Do not rewrite the whole brief for a minor report.

### `03. Portfolio/Execution Board.md`
Update only when:
- the earnings reaction materially changed structure
- the entry band is no longer valid
- the stop or invalidation logic changed
- the stance category changed

### `03. Portfolio/Execution Board.md`
Update when:
- action state changed
- blocker status changed
- trigger logic changed
- sizing logic changed
- a note-level recommendation must be upgraded or downgraded

### `03. Portfolio/Portfolio Snapshot.md`
Update only when:
- the report changed whether the draft slot remains justified
- status moved between active, suspended, under review, or damaged
- risk framing materially changed

### `04. Research/Coverage and Watchlist.md`
Update only when:
- conviction changed
- tier changed
- ranking changed
- trigger changed
- key risk changed

### `04. Research/Coverage and Watchlist.md`
Update only when:
- durable thesis language changed
- key risk changed
- act-when conditions changed

This is a permanent file. Do not write short-term noise into it.

## Output style for the agent

When you perform the update pass:
- be concise
- be factual
- be decision-grade
- avoid newsletter fluff
- avoid broad mechanical churn
- prefer one clear sentence over three vague ones

## Recommended execution order

1. read the relevant packet in `tmp/post-earnings-prep.json`
2. read the candidate file map in `tmp/post-earnings-note-targets.json`
3. inspect the reported name's current note presence
4. decide whether each candidate file truly needs a change
5. edit only the affected files
6. log durable workflow changes or lessons to daily memory if warranted

## Default no-op behavior

If no material tracked earnings reported, or the report does not justify note changes:
- leave files untouched
- return a brief no-op summary

If a material tracked event did report, do not use a no-op summary unless you also state the closure state and why it did not advance.

## First intended use cases

- LMT post-earnings morning follow-up
- MSFT / GOOG / AMZN cluster follow-up
- XOM post-earnings plus EIA follow-through
- ETN post-earnings timing-sensitive update
