# Obsidian CLI Runtime Note

## Purpose

Use Obsidian CLI for local note discovery, inspection, and link navigation. It is not generated-proof validation, an apply engine, or an authority surface.

## Active finance routes

| Need | Owner |
|---|---|
| Alert preferences and review posture | `03. Alerts and Recommendations/Investor Profile.md` |
| Generic alert conditions and states | `03. Alerts and Recommendations/Alert Trigger Policy.md` |
| Ticker thesis and alert interpretation | `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md` |
| Live numeric bands and invalidation | guarded SQL `reference_levels` / `tmp/alert-level-freshness-controller.json` |
| Read-only operations and proof routes | `03. Alerts and Recommendations/Alert Operations Board.md` |
| Recommendation risk doctrine | `07. Risk/Risk Rules.md` |

Example discovery commands:

```powershell
obsidian-cli search-content "freshness_decay" --no-interactive --format json --page-size 10
obsidian-cli print "Alert Trigger Policy"
obsidian-cli print "Alert Bands and Invalidation Register"
```

## Boundary

Search results and backlinks are routing evidence only. They do not outrank owner notes, generated validators, exact source truth, or Randall's decision. Do not infer canon mutation, capital, account, order, money-movement, external-delivery, or paper/live execution authority from Obsidian output.
