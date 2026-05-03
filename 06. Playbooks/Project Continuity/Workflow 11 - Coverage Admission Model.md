# Workflow 11 - Coverage Admission Model

## Objective
- Turn new-ticker intake and promotion decisions into an explicit operator procedure without reopening Workflow 6's already-set operational tier framework.

## Current State
- This workflow is queued behind Workflow 10 in the reprioritized sequence.
- Workflow 6 already settled the operating tier model (`Daily Execution`, `Event-Driven Watch`, `Macro Context`, `Speculative Monitor`).
- What is still missing is the **procedure** layer: how a new name gets admitted, what minimum thesis/data/date/note obligations it must satisfy, and how promotion/demotion decisions are made consistently.
- The formal Workflow 11 procedure draft should not outrun a real case. `LLY` is the first bounded live pilot and should be used before the procedure is treated as final.

## Last Meaningful Progress
- Workflow 7 added `LLY` as a single-name Healthcare watch-lane pilot.
- Current written-thesis residue remains explicit in `04. Research/Coverage Universe.md`: `CAT`, `CVX`, `LLY`, and `SMCI` are tracked operationally but still do not have full thesis blocks there.

## Outstanding
- Complete the missing `LLY` thesis block in `04. Research/Coverage Universe.md` as the first real intake-case pilot.
- Define the exact minimum machine + note data requirements before a name can enter the tracked universe or Execution lane.
- Define the per-ticker intake checklist.
- Define minimum thesis-block requirements before a new tracked name is considered honestly covered.
- Define the date/catalyst policy for newly admitted names.
- Define which canonical notes must update on admission, promotion, demotion, and removal, and who owns each mutation.
- Keep this workflow from relitigating Workflow 6's already-closed tier framework.

## Blockers / Trust Gaps
- Main risk is scope drift back into Workflow 6 territory.
- This workflow should inherit Workflow 6's lane/tier contract and build the **operator procedure** on top of it, not reopen the framework itself.
- Formalizing the procedure before running `LLY` once as a real bounded intake case would risk writing to a hypothetical instead of the live workflow.

## Next Action
- Complete the `LLY` thesis block first as the bounded live intake test case, then open the formal Workflow 11 draft so the procedure is grounded in one real pass instead of a hypothetical and includes explicit execution-lane admission gates.

## Key Files
- `06. Playbooks/Project Continuity/Workflow 6 - Coverage Tier Framework.md` - settled tier framework this workflow must inherit rather than reopen.
- `04. Research/Coverage Universe.md` - thesis-block owner and current `LLY` gap.
- `02. Markets/Watchlist.md` - active tracking-universe mirror.
- `03. Portfolio/Deployment Trigger Sheet.md` - execution-board ownership boundary.
- `tmp/portfolio-config.json` - current live lane assignment.

## Automation / Refresh Path
- Keep this in the main session first.
- If the procedure stabilizes after a few real uses, then consider promoting it into a dedicated skill.
