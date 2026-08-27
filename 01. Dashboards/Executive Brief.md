# Executive Brief

## Bottom Line

The workspace now has two clean read layers: `Veritas Command Center` for Randall's human view and `Veritas PM` for operator/proof control. Human notes and deliverables should be easy to find; machine proofs remain in `tmp/`, `state/`, and validated workflow artifacts. Nothing in this surface is approval for capital deployment, paper/live execution, account action, portfolio mutation, or proof deletion.

## Fast Read Order

1. Veritas Command Center local UI: `http://127.0.0.1:8765`
2. `05. Intelligence/Thesis Ranking and Leadership Board.md`
3. `05. Intelligence/Weekly Positioning Review.md`
4. `03. Portfolio/Execution Board.md`
5. `03. Portfolio/Portfolio Snapshot.md`
6. `04. Research/Coverage and Watchlist.md`
7. `07. Risk/Risk Rules.md`
8. `10. Deliverables/INDEX.md`

## Human vs Machine Split

| Layer | Home | Role |
|---|---|---|
| Human command view | Veritas Command Center UI and `01. Dashboards/` | Randall-facing orientation, ranking, leadership, and next-read path. |
| Human canon notes | `03. Portfolio/`, `04. Research/`, `05. Intelligence/`, `07. Risk/` | Written portfolio posture, thesis, watchlist, risk, and weekly judgment. |
| Human deliverables | `10. Deliverables/` | PDFs, Excel workbooks, HTML views, and CSV exports for retrieval. |
| Machine proof | `tmp/`, `state/`, `data/state-history/` | Generated JSON, validation packets, indexes, histories, and proofs. |
| Veritas PM view | PM cockpit Veritas/PM tabs and PM packets | Operator control, queue state, workflow proof, source health, and authority boundaries. |

## Current Trust Read

- PM control: use `python scripts\pm_control_packet.py --write --write-db --validate`.
- Finance SQL canon guard: use `python scripts\finance_sql_canon_access.py --write --validate`.
- Workflow route lookup: use `python scripts\workflow_router.py WF## --answer summary`.
- Deliverables shelf: use `python scripts\deliverables_publisher.py --write --validate`.
- Command Center source health: use the local UI `/api/state` and `/api/sources` endpoints.

## Authority Boundary

Generated artifacts, dashboards, copied deliverables, and UI panels are review-only. They do not grant owner approval, canonical portfolio mutation, archive/delete apply, paper/live execution, brokerage/account action, sizing, sleeve, cash, risk-rule, customer delivery, or money-movement authority.

## Next Human Review

- Refresh thesis ranking after the next finance chain so leadership and entry posture are current.
- Keep PDFs/Excels/HTML/CSV reachable from `10. Deliverables/`, not buried in `tmp/`.
- Use Veritas PM for proof and source health; use Veritas Command Center for Randall's decision-facing view.
