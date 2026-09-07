# WF72 Financial Truth Map

Status: **review-only contract packet**. No canonical notes were edited. This artifact does **not** authorize portfolio mutation, trade/account action, paper orders, file moves/deletes/archive, or owner-approval inference.

## Evidence basis

Inspected owner surfaces and support artifacts:

- `03. Portfolio/Execution Board.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `04. Research/Coverage and Watchlist.md`
- `02. Markets/Macro Regime Dashboard.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `tmp/current-window-artifacts.json`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- `tmp/capital-deployment-recommendation-validation.json`

Current-window proof: `tmp/current-window-artifacts.json` generated `2026-05-22T05:13:12Z`, status `ok`, 104/104 artifacts present, no missing required roles, no critical/unreadable roles. Warning roles: `board_canon_guardrail`, `finance_discrepancy_resolver`, `run_summary`.

Capital recommendation proof: `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` generated `2026-05-22T04:56:17Z`; validator generated `2026-05-22T05:48:05Z`, status `ok`, 7 packets, 0 critical, 0 warning. Boundary still matters: packets have `apply_allowed=false`, `proposal_apply_allowed=false`, `trade_or_account_action_allowed=false`, and per-packet `source_freshness` is `stale` / `review_required`.

## Flattened truth ownership

| Truth type | Owner surface | Canon role | Promotion rule | Main drift risk | Recommended flattening action |
|---|---|---|---|---|---|
| Daily action router | `01. Dashboards/Today.md` proposed; currently missing | Generated review-only router, not canon | Never promotes by itself; links to owner surfaces and validator-clean packets only | Current daily answer is scattered | Create Today.md as top 3-7 item router: state, price vs band, owner action needed, proof links, warnings, authority flags |
| Execution state, bands, stops, repair/blockers | `03. Portfolio/Execution Board.md` | Canonical owner | WF64/WF56 gated apply only for scoped categories; no execution inference | Board is authoritative but heavy; current-window has `board_canon_guardrail` warning | Keep as single execution owner; later generate parser/detail sections from one structured source |
| Portfolio posture, model weights, sleeves, cash, concentration | `03. Portfolio/Portfolio Snapshot.md` | Canonical owner | Exact scoped artifact + validators + approval/standing approval + patch/rollback/post-apply proof | Internal freshness mismatch: top says 2026-05-21, freshness block still references 2026-05-19 | Keep as only model/posture owner; strip action-state detail to pointers and sync freshness block |
| Research universe, tiers, thesis, act-when | `04. Research/Coverage and Watchlist.md` | Canonical owner | Source-backed research packet and owner-surface patch path; no deployment/sizing implication | Long thesis sections and repeated opportunity radar can lag artifacts | Keep no deployment-state column; move recurring radar to generated Today/weekly support |
| Macro regime and macro guardrails | `02. Markets/Macro Regime Dashboard.md` | Canonical macro interpretation | Macro can influence posture only; cannot promote tickers/sizing/execution | Core macro data is 2026-05-15/17 while fresh 2026-05-21 radar is embedded; stale NVDA future-tense remains | Keep regime here; move repeated radar to Today/weekly; refresh stale event language |
| Weekly strategy | `05. Intelligence/Weekly Positioning Review.md` | Best current weekly strategy candidate | Weekly synthesis only; owner surfaces still own levels/weights/thesis | Main reset is week of 2026-05-11/15 but appended radar is 2026-05-21 | Make this the single weekly product or merge with rebuilt Intelligence Brief |
| Weekly intelligence | `05. Intelligence/Weekly Intelligence Brief.md` | Stale scaffold / archive-or-rebuild candidate | Do not use older body as current judgment | Fresh notice sits above stale May 4-10 body and machine skeleton | Rebuild as single weekly product or demote to archive/stub pointing to Weekly Positioning Review |
| Capital deployment recommendation packets | `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.*` | Generated support, not canon | Non-self-applying; separate exact apply artifacts required for any canon mutation | Validator-clean can be mistaken for deployment readiness despite stale/review-required packet freshness | Surface highlights in Today.md; keep full packet as proof |
| Current-window artifact index | `tmp/current-window-artifacts.*` | Generated proof/navigation index | Proves existence/readability/window only | Aggregate `ok` can hide warning roles | Use for Today/weekly proof links; do not copy the whole artifact list into notes |
| Official-source/fundamental evidence | `tmp/official-ir-captures/*`, `tmp/fundamental-ir-reconciliation-*`, `tmp/official-earnings-bridge.*` | Evidence support, not canon by itself | Promote only summarized thesis/catalyst implications through owner-surface diffs and validators | Manual-required fields can coexist with apparently complete packets | Keep raw capture detail in tmp/data; promote summaries only via scoped patches |
| Decision/outcome loop | `04. Research/Call Log.md` + `data/state-history/outcome-updates-v1.jsonl` | Decision/outcome owner pair | Serious recommendations should create/update decision records; probability claims blocked until WF55 clears | Recommendation packets can accumulate without outcome closure | Link Today/packets to decision IDs; keep paper/live labels explicit |

## Key findings

1. **The missing Today card is the biggest flattening gap.** Without it, Randall’s current-action answer is spread across Board, Snapshot, weekly notes, generated packets, and current-window indexes.
2. **Execution Board remains the strongest canonical owner, but it is doing too much human-facing work.** It should stay canonical; parser/detail sections should eventually be generated from one structured source.
3. **Portfolio Snapshot has a real freshness mismatch.** The top says date/data as of 2026-05-21, while its freshness section still references 2026-05-19.
4. **Weekly surfaces are split and stale/mixed-window.** Weekly Positioning Review is closer to current strategy; Weekly Intelligence Brief explicitly warns that its body is stale/scaffolded.
5. **Generated packets are useful but not truth owners.** The current capital recommendation validator is clean, but per-packet freshness remains `stale` / `review_required`, and all apply/trade flags remain false.

## Recommended sequence

1. Draft the Today-card contract next.
2. Consolidate weekly truth: one current weekly strategy/intelligence product, with the other demoted or rebuilt.
3. Later gated note-sync pass: Snapshot freshness block, Macro stale event language, and weekly stale-window cleanup.
4. Keep all generated-to-canon promotion inside WF64/WF56 exact patch/approval/validator/post-apply guardrails.
