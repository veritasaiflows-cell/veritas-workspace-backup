# Workspace Audit - 2026-04-22

## 1. Executive summary

The workspace is real, usable, and materially more mature than a notes dump. The finance operating model is coherent, the core navigation stack is strong, and the script layer is no longer imaginary.

But it is not clean enough to trust casually.

The biggest problem is not missing capability. It is **drift between the written truth, the machine truth, and the actual current operating model**. Several parts of the system are saying different things at the same time:
- workspace standards still describe an old top-level structure
- `FINANCE_SOUL.MD` still describes a different identity and operating doctrine than `SOUL.md`
- `tmp/portfolio-config.json` materially conflicts with current portfolio notes and risk posture
- `tmp/market-state.json` is partial while newer downstream artifacts still present a stronger-looking operating surface
- legacy branch residue still sits in active root paths (`templates/`, `Evening Review/`, `state/`, old helper scripts)

Bottom line: the workspace is strong enough to operate, but weak enough to mislead if you stop checking the seams.

## 2. Overall health score

**6.8 / 10**

Good operating core, too much truth-source drift and leftover structure noise for anything higher.

## 3. Biggest strengths

- **Strong finance-first navigation spine.** `Home.md`, dashboards, markets, portfolio, intelligence, and risk files form a coherent review order.
- **Core note quality is good.** The active finance notes are readable, decision-oriented, and increasingly aligned.
- **Automation layer is meaningful.** The scripts, `tmp/` artifacts, and selective post-earnings workflow are real and useful.
- **Continuity discipline exists.** `MEMORY.md`, daily notes, and protocol files are doing real work.
- **Audit culture is already present.** There is an actual audit trail under `08. Audits/`, which is rare and valuable.

## 4. Major drift risks

1. **Duplicate doctrine problem**
   - `SOUL.md` says Veritas.
   - `FINANCE_SOUL.MD` says APEX, portfolio manager, autonomous advisor, different session init, different posture.
   - That is not harmless flavor. It is conflicting operating doctrine.

2. **Config truth vs note truth mismatch**
   - `tmp/portfolio-config.json` still shows old weights like 15% core slots, 10% cash, and 5% speculative slots.
   - The live notes now say 20% cash, reduced ETN sizing, and tighter discipline.
   - That means the dashboard/config layer is behind the actual note layer.

3. **Workspace-governor standards are stale**
   - The skill reference still defines the old consulting-era top-level folder policy.
   - The real workspace is finance-first with `01. Dashboards` through `09. Archive`.
   - Written policy and live structure are still out of sync.

4. **Active root drift**
   - Empty `state/` still exists.
   - `Evening Review/` sits as a stray top-level folder outside the numbered system.
   - `templates/` still holds old branch templates.
   - Root is not chaotic, but it is no longer strict.

## 5. Workflow inefficiencies

1. **Too many layers say similar things**
   - Executive Brief
n- This Week
- Next Actions
- Weekly Positioning Review
- Daily Executive Summary
- Dashboard
- Trigger Sheet

   The stack is conceptually valid, but it is close to redundancy drift. If maintenance slips, contradictions will multiply fast.

2. **Manual truth is still embedded inside supposedly systematized flows**
   - Fed target is hardcoded.
   - FedWatch is unwired.
   - ETN earnings timing is still unresolved.
   - Critical date confirmation still depends on ad hoc checking.

3. **Old helper clutter slows judgment**
   - `scripts/diagnose.py`
   - `scripts/diagnose_calendar.py`
   - `scripts/market_state_refresh_plan.md`
   - `tmp/calc_ma.py`
   - `tmp/refresh_technicals.py`
   - `tmp/inspect_fedwatch.py`

   These are small, but they pollute the active tool surface.

4. **Archive policy is incomplete**
   - Old business branch material was archived well under `09. Archive/`.
   - But old templates and root leftovers were not finished off.

## 6. Structural and information-architecture problems

1. **One empty root folder and one stray root folder should not still exist**
   - `state/` is empty dead weight.
   - `Evening Review/` may be legitimate, but as a top-level active folder it breaks the review order.

2. **Template layer is from the wrong operating era**
   - `templates/opportunity-note.md`
   - `templates/weekly-opportunity-review.md`
   These are clearly prior-branch artifacts and no longer fit the finance model.

3. **Naming consistency is not tight enough**
   - `FINANCE_SOUL.MD` has odd casing and conflicting doctrine.
   - Mixed conventions remain between human notes, system notes, and generated artifacts.

4. **There are too many “source of truth” candidates**
   - live notes
   - `tmp/*.json`
   - dashboard payloads
   - README process statements
   - MEMORY

   The system has not fully settled which layer wins when conflicts appear.

## 7. Automation and scheduler issues

1. **Downstream artifacts can look healthier than upstream inputs deserve**
   - `tmp/trigger-sheet.json` is fresh.
   - `tmp/market-state.json` is still `partial`.
   - That creates confidence leakage.

2. **`tmp/portfolio-config.json` is stale relative to the current note layer**
   - This is the single biggest automation-governance issue.
   - If the dashboard reads this as canonical, the dashboard is behind the portfolio notes.

3. **`tmp/` is not cleanly machine-artifacts-only**
   - It still contains helper `.py` files and scratch outputs.
   - That violates its own intended role.

4. **The automation spine is documented better than it is governed**
   - The scripts exist.
   - The workflow notes exist.
   - But validation between script output and note truth is still weak.

## 8. Documentation and continuity gaps

1. **Doctrine conflict is unresolved**
   - `SOUL.md` and `FINANCE_SOUL.MD` should not both remain active without a clear hierarchy note.

2. **Skill guidance is behind reality**
   - `skills/workspace-governor/references/workspace-standards.md` is stale.

3. **Some prior audit findings were not fully closed**
   - Earlier notes mentioned removing `state/`.
   - It still exists.
   - That is a closure-discipline problem.

4. **Rebalance log is structurally fine but still mostly ceremonial**
   - No real decision entries yet.
   - That is acceptable for draft stage, but it means the audit trail is not yet complete once actual portfolio calls begin.

## 9. Highest-value fixes

1. **Pick one doctrine and retire the other**
   - Resolve `SOUL.md` vs `FINANCE_SOUL.MD` explicitly.
   - Best answer: keep Veritas as the only identity and convert `FINANCE_SOUL.MD` into a finance doctrine note or archive it.

2. **Make `tmp/portfolio-config.json` match the actual portfolio/risk notes immediately**
   - Right now it is a drift engine.

3. **Update workspace-governor standards to the actual finance-first structure**
   - The standards file is still lying about the root policy.

4. **Clean the root**
   - remove `state/`
   - either move or formalize `Evening Review/`
   - decide whether `veritas-command-center.html` belongs in root permanently

5. **Finish old-branch residue cleanup**
   - archive or rewrite old templates
   - remove superseded diagnostics and scratch helpers from active paths

6. **Define source-of-truth precedence explicitly**
   - For portfolio and risk: note layer or config layer?
   - For macro readiness: `tmp/market-state.json` should stay authoritative unless overridden explicitly in-note.
   - For dashboard rendering: no silent contradiction with note layer.

## 10. Prioritized action plan

### Priority 1, fix now
1. Resolve `SOUL.md` vs `FINANCE_SOUL.MD` conflict.
2. Bring `tmp/portfolio-config.json` into line with current portfolio weights, cash level, and risk posture.
3. Update `skills/workspace-governor/references/workspace-standards.md` to match the live finance-first vault.

### Priority 2, this week
4. Remove or relocate root drift: `state/`, `Evening Review/`, and any other non-canonical top-level leftovers.
5. Clean `tmp/` so it contains generated artifacts, not helper Python files.
6. Remove or archive superseded diagnostic and planning files from `scripts/`.

### Priority 3, next hardening pass
7. Add a written source-of-truth hierarchy for notes vs config vs dashboard payloads.
8. Add validation checks so stale or conflicting `tmp/` data cannot quietly masquerade as current truth.
9. Decide whether the dashboard is a primary operating surface or just a convenience view, then document that sharply.

## Final blunt read

This workspace is no longer a toy. That is the good news.

The bad news is that it is now complicated enough to create **plausible-looking lies** if drift is not actively controlled. The next quality jump does not come from adding more notes or more scripts. It comes from tightening doctrine, root policy, and source-of-truth discipline.