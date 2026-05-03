# Regime Change Protocol

## Purpose

Define what constitutes a regime shift, the mandatory file update sequence when one is triggered, the default portfolio response, and who or what triggers the reassessment.

The current system defines regime continuity well. This protocol handles what happens when the regime actually changes.

---

## Three regime states

### State 1: Current regime (baseline)
**Definition:** Late-cycle, restrictive-policy, resilient-growth, selective risk-on.

**Characteristics:**
- Fed funds rate above 3.0%, policy on hold
- Unemployment below 5.0%
- GDP growth above 1.0% annualized
- 2s10s spread between -20 and +100 bps
- VIX between 12 and 28
- No active credit event (HYG spreads within 150 bps of normal)
- Inflation above 2.0% but below 5.0%

**Posture:** Selective risk-on. Favor quality, earnings, and durability. Avoid narrative speculation and leveraged names.

---

### State 2: Transition regime (conditions deteriorating or improving)

**Definition:** One or more current-regime thresholds have been breached but the overall regime has not yet decisively shifted. Evidence is mixed or conflicting.

**Triggers (any one of the following):**
- Unemployment rises above 4.8% month-over-month
- Q1 or Q2 GDP annualized prints below 1.0%
- 2s10s spread re-inverts below -30 bps
- VIX sustains above 28 for 5+ consecutive trading days
- HYG credit spreads widen more than 150 bps in a 30-day window
- Fed explicitly signals rate cuts ahead (language shift, not futures pricing)
- Oil spikes >30% in 30 days OR crashes >25% in 30 days (energy shock)
- DXY moves >8% in 30 days in either direction

**Posture:** Raise cash. Pause new entries. Hold existing positions with stops active. Do not add to positions in affected sectors. Flag for full regime review within 5 trading days.

---

### State 3: Broken regime (decisive shift confirmed)

**Definition:** Multiple threshold breaches confirmed, or a single acute shock event that categorically changes the operating environment.

**Triggers (any two simultaneous, or one acute event):**
- Unemployment above 5.0% with accelerating trend
- GDP contraction (negative print)
- VIX above 35 sustained for 10+ trading days
- Credit event: major bank failure, sovereign default, or HYG spreads >250 bps above normal
- Fed in emergency cut mode (inter-meeting cut or 50+ bps cut at a single meeting)
- Geopolitical shock: active great-power military conflict, nuclear escalation signal, or major supply chain disruption affecting >20% of a critical commodity

**Posture:** Defensive. Reduce equity exposure toward minimum. Increase cash. Review every position for thesis impairment. No new equity entries until regime stabilizes or new regime is defined. Consider TLT, GLD, and SHY as hedge vehicles.

---

## Mandatory file update sequence on regime shift

When a regime change is triggered, update files in this exact order:

### Step 1: Flag the trigger (immediate — same session)
- Write a dated note in `memory/[YYYY-MM-DD].md` identifying: what triggered the review, which threshold was breached, and the current state assessment (transition vs. broken)
- Add a `⚠️ REGIME REVIEW TRIGGERED` banner to `01. Dashboards/Executive Brief.md`

### Step 2: Update the macro layer (within 24 hours)
- Update `02. Markets/Macro Regime Dashboard.md` — revise regime statement, update working data points, rewrite base interpretation
- Update `02. Markets/Regime Scoring Matrix.md` — re-score all tracked names against the new or transitioning regime. Regime Fit scores will change across the board.

### Step 3: Update the portfolio layer (within 24 hours)
- Update `03. Portfolio/Portfolio Snapshot.md` — revise overall posture, cash level, and risk flags
- Update `03. Portfolio/Deployment Trigger Sheet.md` — review all action states. Names that were "Almost deployable" in the prior regime may become "Do not touch" in a broken regime.
- Update `03. Portfolio/Technical Entry and Invalidation Sheet.md` — entry bands set under the prior regime may no longer be valid if the macro environment changes the support/resistance structure

### Step 4: Update the intelligence layer (within 48 hours)
- Update `05. Intelligence/Weekly Positioning Review.md` — revise weekly posture, deployment map, and risk section
- Update `05. Intelligence/Weekly Intelligence Brief.md` — add a regime change section with the evidence and implications
- Update `02. Markets/Watchlist.md` — confirm that the active tracking universe still makes sense under the new or transitioning regime

### Step 5: Review risk rules (within 48 hours)
- Review `07. Risk/Risk Rules.md` — confirm that sizing tiers and escalation triggers are still calibrated for the new environment
- If a broken regime is declared, escalate per the escalation triggers in Risk Rules (drawdown, leverage, options, portfolio shifts >20%)

### Step 6: Log and close (within 72 hours)
- Write a dated regime-change summary in `08. Audits/[YYYY-MM-DD]-regime-change-[description].md`
- Update `MEMORY.md` with the regime shift as a durable decision record
- Remove the `⚠️ REGIME REVIEW TRIGGERED` banner from Executive Brief once the update sequence is complete

---

## Default portfolio actions by state

| Regime State | Cash Target | New Entries | Existing Positions | Speculative Sleeve |
|---|---|---|---|---|
| Current (baseline) | 15%–25% | Per normal deployment gates | Hold with stops active | Max 10% total, Tier 3 sizing rules |
| Transition | 25%–40% | Pause — no new entries | Maintain stops, review thesis | Cap at 5%, no new speculative adds |
| Broken | 40%–60% | No new equity entries | Reduce toward minimum, stops active | Exit or cut to near-zero |

---

## Who triggers a regime reassessment

**Automatic triggers (script-surfaced):**
- `market_state_refresh.py` output flags a threshold breach in VIX, yields, or macro data
- `validate_dashboard_state.py` produces a critical-level warning rather than a warning-level flag

**Manual triggers:**
- Veritas identifies a threshold breach during a session and flags it in the daily note
- Claude (operating as audit/review layer) calls a regime review after reading vault state at session open
- Randall explicitly directs a regime review

**Trigger authority:** Either Veritas or Claude can call a transition-regime flag. A broken-regime declaration requires either explicit Randall direction or two independent threshold breaches confirmed in the same session.

---

## Re-entry after a broken regime

A broken regime does not mean permanent defensive posture. Return to the current/baseline regime requires:
1. Primary threshold breaches resolving (e.g., unemployment stabilizes, VIX returns below 28, GDP prints positive)
2. At least 4 weeks of stabilizing data — not a single data point
3. A deliberate regime re-declaration in `02. Markets/Macro Regime Dashboard.md`
4. Re-scoring of all names in `02. Markets/Regime Scoring Matrix.md` against the new baseline

Do not drift back into risk-on posture without a deliberate re-declaration. The regime change protocol runs in both directions.

---

## Last updated

- 2026-04-26 — created by Claude per vault efficiency and precision audit (2026-04-26)
- Thresholds calibrated to the current late-cycle, restrictive-policy baseline
- Review thresholds annually or after any broken-regime event to recalibrate to the prevailing environment
