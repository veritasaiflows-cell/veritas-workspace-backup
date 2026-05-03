# 2026-04-21 Evening Review

## Purpose

This is the compressed but detailed catch-up document for tonight.

You should be able to read this in 10 to 20 minutes and come away with the full working picture of what changed today, what now matters operationally, what remains incomplete, and what tomorrow should focus on.

---

## Executive bottom line

Today was a real infrastructure-and-operations day, not a cosmetic wording day.

The most important thing that happened is that we found and fixed the real cause of the macro automation problem. The daily executive summary had been understating macro confidence for a legitimate reason: `market_state_refresh.py` was returning partial data because the running process could not see the FRED API key, even though the key existed in the Windows user environment. That meant the summary caveat was not fake. The upstream data really was incomplete. The fix was not to soften the wording. The fix was to harden the script so it checks both the live process environment and the Windows user environment.

That is now done. `tmp/market-state.json` is back to `status: ok`, with live 2Y Treasury and true 2s10s restored. The only remaining macro limitations are the honest ones: the Fed target range is still maintained manually, and FedWatch is still unwired.

From there, the rest of the session was mostly about making the system more honest, more durable, and more action-oriented:
- the stale technical-sheet problem was identified as a cadence design gap, not a broken script
- the technical-sheet refresh cadence was changed from Friday-only to Tuesday plus Friday
- post-earnings automation was tightened so reported earnings cannot stay just a calendar mention
- the daily executive summary was upgraded to require an actual execution layer rather than just a strategy summary
- `market_state_refresh.py` was extended to provide futures, sector, and top-actionable-name context
- the dashboard was reviewed and judged useful but still more like a polished status board than a true execution cockpit

That is the real state.

---

## 1. `memory/2026-04-21.md` — what happened today in factual terms

This file is the raw session log, and it now captures the important changes from today.

The session began with the macro automation problem. The issue was traced to a real environment mismatch: Windows had the FRED key stored, but the running process did not inherit it. That made the 2Y Treasury field fail upstream, which cascaded into partial macro output. The script was hardened to check:
- `FRED_API_KEY`
- `fred_api_key`
- Windows registry fallback in `HKCU\Environment`

After the change, the script was re-run and verified live. 2Y and 2s10s returned, and `tmp/market-state.json` moved back to healthy status.

From there, the technical-sheet staleness issue was investigated. The result was important: the problem was not that the script data was stale. The problem was that the canonical markdown note only had a guaranteed Friday rewrite path. The script outputs were fresher than the note. That means the note could drift stale even while the machine layer was current. The durable fix was to change the cron cadence so the technical-sheet maintenance now runs Tuesday and Friday at 4:30 PM Phoenix.

The post-earnings workflow was also tightened. Previously, there was too much room for the system to mention a reported earnings event without translating it into a real decision line. That is now harder to do. The post-earnings cron and the executive-summary cron were both updated so material earnings results must be carried forward as:
- what happened
- what it means
- what we do now

The Event Calendar also got a small but meaningful integrity fix: the weekday labels for Apr 21 and Apr 22 were corrected so the dates and weekday names no longer conflict.

Finally, the daily executive summary was upgraded structurally. It now requires:
- pre-market execution context
- distance from entry band in dollars and percent
- explicit if-then trigger conditions
- a same-day macro calendar
- an open protocol

The important caveat is that the pre-market section can only be as good as the script layer. So `market_state_refresh.py` was extended to capture futures, sectors, and actionable-name snapshots, while explicitly warning when true pre-market prints are not actually available from the source.

The final note in `memory/2026-04-21.md` is also important: dashboard work was reviewed and scoped, but intentionally left for the next session rather than rushed tonight.

---

## 2. `MEMORY.md` — what changed that should still matter next week

`MEMORY.md` now reflects the durable changes from this session.

The first durable change is the technical maintenance cadence. The system no longer treats Friday as the only guaranteed technical-sheet rewrite. That was too sparse for earnings-heavy weeks. It now treats Tuesday plus Friday at 4:30 PM Phoenix as the correct cadence, specifically to prevent the canonical technical note from drifting stale through midweek.

The second durable change is the post-earnings decision standard. Post-earnings follow-up is no longer just an implied workflow. Material tracked earnings should now preserve a concise decision line in the note layer:
- what happened
- what it means
- what we do now

That matters because it prevents the system from degrading into calendar logging without investment judgment.

The third durable change is the daily executive-summary standard. That workflow now needs an execution layer, not just strategic context. The durable rule is that the brief should include:
- pre-market execution context when actually available
- distance from entry band in dollars and percent for top actionable names
- explicit if-then trigger conditions
- same-day macro calendar
- open protocol discipline

The fourth durable change is epistemic honesty around pre-market data. `MEMORY.md` now records the rule that futures and live snapshot proxies are useful, but they are not the same thing as true pre-market prints. If the source does not provide real pre-market prices, the system should say so explicitly.

The fifth durable change is the dashboard warning. `MEMORY.md` now records that presentation scripts can become a second conflicting source of portfolio truth if too much is hardcoded into them. That is not just a cosmetic concern. It is a drift risk.

Those are the changes from today that should still matter later.

---

## 3. `scripts/README.md` — how the workflows are now documented

A meaningful amount of operating logic now lives in `scripts/README.md`, and that is a good thing. Cron payloads are not a good sole source of truth.

The README now clearly frames `tmp/market-state.json` as the macro-readiness source of truth. That means downstream briefs should not invent a more complete macro picture than the file actually supports. If the file is partial, the brief should explicitly downgrade macro confidence.

The README also now contains a dedicated post-earnings operating rule. That section says post-earnings automation should not stop at date tracking or a bare "reported" marker. For any material tracked earnings result, the note layer should preserve a concise decision-grade interpretation with three parts:
- what happened
- what it means
- what we do now

That is a clean operating standard, and it matters because it moves the system toward actual decision support.

The README also now documents the upgraded `market_state_refresh.py` behavior. That script is no longer just a basic macro snapshot. It now includes:
- futures snapshots
- sector posture snapshots
- actionable-name snapshots

Just as important, the README also documents the limitation: yfinance does not reliably provide true pre-market prints in this workflow. That honesty matters. It keeps the system from pretending that a live-ish snapshot is a full pre-market tape.

At this point, the README is doing what it should do: telling future-you how the operating chain is supposed to behave.

---

## 4. `05. Intelligence/Event Calendar.md` — small file, important integrity fix

This was not the biggest file today, but it mattered more than its size suggests.

The Apr 21 and Apr 22 entries had weekday-label drift. The dates themselves were right, but the weekday names were wrong, and one line still said "report tomorrow" when the event was now same-day. That is exactly the kind of small error that makes a system feel sloppier than it is and can create timing mistakes in morning briefs.

The calendar was corrected so:
- Apr 21 is now labeled Tuesday
- Apr 22 is now labeled Wednesday
- the same-day wording around RTX and NOC was corrected

The file also still carries the current earnings cluster correctly enough to matter:
- RTX is marked reported
- NOC sits in the immediate defense read-through window
- LMT remains a critical near-term catalyst
- the April 29 cluster remains heavy and important

The main takeaway is simple: this layer is now cleaner, and that matters because executive summaries depend on it.

---

## 5. `01. Dashboards/Daily Executive Summary/2026-04-21.md` — what the old brief still reveals

Tonight, this file is best read as a baseline rather than as the final product.

It already had some real strengths:
- it was reasonably decision-oriented
- it carried the macro caveat honestly
- it translated deployment status into portfolio implications
- it already had useful sections for blocked names, deployable names, and recommended actions

But after today’s work, its weaknesses are now clearer.

It is still more of a strategic morning memo than a true execution brief. Specifically, it did not yet force:
- real pre-market execution context
- exact distance from band in dollars and percent
- explicit if-then trigger conditions
- a proper same-day macro calendar with prior and consensus when available
- a disciplined open protocol

That is why the cron prompt was tightened. Tomorrow’s brief should be judged against this file. The question should not be "did the format get longer?" The real question is: "did it become more useful for actual morning decision-making without becoming noisy or fake-precise?"

That is the right comparison.

---

## 6. `scripts/market_state_refresh.py` — what changed technically and why it matters

This file got the biggest direct code improvement today.

The first important change was the FRED key hardening. The script no longer relies only on a single live-process environment variable. It now also checks:
- `FRED_API_KEY`
- `fred_api_key`
- Windows user-environment registry fallback

That matters because scheduled or service-backed automation on Windows can miss environment changes even when the user profile itself has the key configured.

The second important change is the new execution-context layer. The script now captures additional snapshot blocks for:
- S&P 500 futures (`ES=F`)
- Nasdaq 100 futures (`NQ=F`)
- sector posture snapshots (`XLI`, `XLF`, `XLK`, `XLE`)
- actionable-name snapshots (`ETN`, `JPM`, `NVDA`)

These snapshots include fields like:
- last price
- previous close
- regular market previous close
- change and percent change
- open, high, low, volume
- pre-market fields when available
- market phase

The third important change is the honesty layer. The script now explicitly warns when true pre-market pricing is not available from the source. That is critical. Without that warning, the system could easily drift into fake certainty around pre-open conditions.

The result is that `market_state_refresh.py` is now a much better input to an execution-aware morning brief, even though it still does not fully solve the pre-market data problem.

In plain language: this script is better than it was this morning, and it is better in the right way.

---

## 7. `scripts/generate_dashboard.py` — where the command center is strong and where it is still weak

This script is structurally sound, but it still has real weaknesses.

The good part is the architecture. It reads JSON from `tmp/` and builds a self-contained HTML dashboard. That is the right separation. The dashboard step itself does not make network calls, and that is clean.

The weak part is truth ownership. Too much important operating truth is still hardcoded inside the script itself:
- portfolio model
- sizing rules
- escalation rules
- regime indicators

That creates drift risk. The notes can say one thing while the dashboard shows another, and both can look authoritative.

The second weakness is that the dashboard renderer is not yet fully consuming the newly improved market-state data. The underlying script now knows more about futures, sector posture, and actionable-name snapshots, but the current generator is still mostly rendering the older macro set.

The third weakness is product-level rather than code-level: the dashboard is still more of a status board than an execution cockpit. It has good tabs and decent structure, but it does not yet compress the day into a clear answer to:
- what matters today
- what is closest to action
- what is blocked
- what should be watched at the open

That is why the highest-value dashboard recommendation was not a giant redesign. It was:
- add an Execution Context block on Overview
- add a compact Today’s Action Card
- reduce hardcoded portfolio truth over time
- add more execution math to the technical view

That is the right direction.

---

## 8. `veritas-command-center.html` — what the current front end tells us

The generated HTML confirms that the dashboard already has a respectable shell.

The tab structure is good:
- Overview
- Deployment Board
- Technical Analysis
- Portfolio
- Earnings Calendar
- Macro Regime
- Risk & Rules

The styling is solid enough. It is clean, readable, and already feels like a real control surface rather than a raw dump of values.

But the same verdict still applies: it is stronger as a command board for orientation than as a cockpit for action.

The biggest functional gap is that it still does not surface a true "today first" execution layer. The information is present across tabs, but the user still has to assemble the answer mentally. That is not ideal if the goal is fast morning decision support.

The second gap is that some of the displayed logic is still only as good as what `generate_dashboard.py` feeds it, and that generator still contains too much hardcoded truth. So the HTML can only be as reliable as the backend assumptions behind it.

The main takeaway is that the HTML is not the problem. The bigger issue is what it is being fed and how much decision compression the generator is doing before rendering.

So for tomorrow, the dashboard review should not focus first on colors or layout. It should focus on whether the Overview page is actually answering the most important operational questions.

---

## What is now fixed

These are the things that are genuinely better than they were before today:

- The macro automation issue was traced to the real environment problem and fixed at the script level.
- `tmp/market-state.json` is back to healthy status with live 2Y and true 2s10s.
- The technical-sheet cadence now reflects midweek reality, not just Friday maintenance.
- Post-earnings automation is now much more explicit about preserving decision-grade interpretations.
- The daily executive summary has been structurally upgraded to become more action-oriented.
- `market_state_refresh.py` now produces better morning execution context.
- The event calendar no longer has the most obvious weekday drift in the current catalyst window.
- The workflow logic is better documented in durable files instead of only in live prompts.

---

## What is still incomplete or constrained

These are the honest remaining limitations:

- FedWatch is still not wired.
- Fed target range is still manually maintained.
- yfinance still does not reliably provide true pre-market prints in this workflow.
- The upgraded executive-summary structure still needs to be judged on an actual next-morning output, not just on prompt text.
- The dashboard generator still hardcodes too much truth and does not yet fully exploit the new execution-context data.
- The command center still needs a more compressed, explicitly action-oriented Overview experience.

Those are real gaps, not theoretical ones.

---

## What tomorrow should focus on

If tomorrow goes well, the first check should be the newly generated daily executive summary.

That review should answer:
- Did the new structure actually improve the brief?
- Did the pre-market section become more useful without faking precision?
- Did the distance-to-band logic make the actionable names easier to evaluate?
- Did the trigger-condition section become concrete enough to act on?
- Did the macro calendar and open protocol improve decision discipline?

After that, the next review should be the dashboard and command center updates.

That review should answer:
- Is the new execution context actually visible?
- Is the Overview page more useful for the first two minutes of the day?
- Has the generator reduced drift risk or is it still carrying too much hardcoded truth?

That is the correct next-session sequence.

---

## Final take

Today was a strong systems day.

Not flashy, but important.

The real theme was this: stop letting the system sound smarter than its data, and stop letting operational gaps hide behind pretty summaries.

That happened in a few concrete ways:
- fixing the real macro feed problem instead of rewriting the prose
- tightening note automation so earnings produce decisions, not just mentions
- tightening the daily brief so it moves closer to real morning execution support
- expanding the market-state script while still being honest about data limits
- identifying the dashboard as useful but still one step short of being a true action cockpit

That is the state you should go to sleep with.
