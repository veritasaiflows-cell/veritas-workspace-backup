---
name: veritas-post-earnings-sync
description: Orchestrate the end-to-end closure workflow after a company reports earnings. Use this to run the refresh chain, scaffold the post-earnings scorecard, call the relevant analysis skills for judgment, and synchronize the results across the portfolio and watchlist board.
---

# Veritas Post-Earnings Sync

This skill owns the **transition from raw earnings data to a synchronized vault state.**

It is a workflow orchestrator. For the actual analysis of quality, valuation, or technicals, it should invoke the specific `veritas-*-pass` skills.

## 1. Preparation Phase

1. **Run the Artifact Chain:**
   Execute `python scripts/run_finance_refresh_chain.py post-earnings`.
2. **Inspect Evidence:**
   - Read `tmp/post-earnings-prep.json` to understand the delta in numbers, guidance, and calendar dates.
   - Read `tmp/post-earnings-note-targets.json` to identify which specific notes in the vault are flagged for updates.

## 2. Scorecard Phase

1. **Scaffold the Note:**
   Create or open the canonical scorecard: `05. Intelligence/Earnings/<Ticker> <Quarter> Post-Earnings Scorecard.md`.
2. **Populate Quantitative Core:**
   Use the data from `post-earnings-prep.json` to fill the "Results vs. Consensus" and "Guidance" sections.
3. **Execute Analysis Pass:**
   - Invoke `veritas-fundamental-pass` to interpret the impact on the long-term thesis and valuation.
   - Invoke `veritas-technical-pass` to determine if the post-earnings price action necessitates a new entry band or move to "Bench."
4. **Define Closure State:**
   Set the status at the top of the note: `Status: [Reported | Interpreted | Synced | Closed]`.

## 3. Sync Phase (The Board)

Update the following notes based on the targets in `tmp/post-earnings-note-targets.json`:

- **[[03. Portfolio/Deployment Trigger Sheet]]**: Update or remove the "Earnings Block." Update triggers if the setup has changed.
- **[[03. Portfolio/Technical Entry and Invalidation Sheet]]**: Update the band and the `band_last_set` date if the technical pass recommended a change.
- **[[02. Markets/Watchlist]]**: Update the "Context/Catalyst" column to reflect the post-print reality.
- **[[05. Intelligence/Event Calendar]]**: Roll the ticker's earnings date to the next confirmed or estimated quarter.
- **[[03. Portfolio/Portfolio Snapshot]]**: If the ticker is a held position, update the "Current Stance."

## 4. Closure Rules

- **No Silent Drift:** If the earnings report invalidates a prior thesis, do not "smooth" it. Flag it explicitly in the `Executive Brief`.
- **Honest Gaps:** If the conference call or IR release leaves questions unanswered (e.g., segment margin detail), mark the scorecard as `Synced` but NOT `Closed`.
- **Judgment Precedence:** If the machine artifact proposes a band update that contradicts the `veritas-technical-pass` judgment, the judgment wins. Document why.

## Execution Procedure

When Randall asks "Sync the [Ticker] earnings," follow this order:
1. `Research`: Run the script chain and read the `tmp/` JSONs.
2. `Strategy`: Briefly state the results and the intended update path across the 5 core notes.
3. `Action (Scorecard)`: Write the scorecard note with analysis.
4. `Action (Sync)`: Update the board notes in a single turn if possible, or sequentially.
5. `Verification`: Run `python scripts/validate_dashboard_state.py` to ensure no new contradictions were introduced.
