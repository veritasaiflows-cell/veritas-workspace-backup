# OS Optimization Advisor Unlock Prework

Generated: 2026-05-24 14:45 MST  
Lane: WF68 / WF55 / WF70 advisor unlock prework  
Status: prework complete, proposal-only

## Verdict

The advisor unlock path is real, but the next step is **not** external delivery-channel apply yet. First repair the latest WF68 internal validation blocker, then prepare a narrow delivery-only approval packet for Randall. WF55 and WF70 are stronger than the audits implied: the 12 stale Call Log rows were already reconciled down to 3 open rows, and WF70 official-source capture is already scheduled in the finance chains with clean post-close proof.

## Authority boundary

This prework is review/proposal only.

- No config/auth/channel mutation.
- No external message sending.
- No live trade/account/money movement.
- No paper execution from this artifact.
- No owner approval inference.
- No probability, win-rate, expected-return, or model-readiness claims.

## Evidence inspected

| Area | Evidence |
|---|---|
| Live queue | `06. Playbooks/Active Workflows.md` |
| OS phase plan | `tmp/wf72-post-audit-os-optimization-phase-plan.md` |
| WF68 | `06. Playbooks/Project Continuity/Workflow 68 - Intraday Alert Engine and Advisor Surface.md`; `tmp/intraday-alerts/runtime-handoff-status.json`; `tmp/intraday-alerts/delivery-router-status.json`; `tmp/intraday-alerts/advisor-alert-packet-validation.json` |
| WF55 | `06. Playbooks/Project Continuity/Workflow 55 - Probability Readiness and Outcome Retention Gate.md`; `04. Research/Call Log.md`; `tmp/probability-readiness-report.json`; `tmp/probability-readiness-validation.json` |
| WF70/WF66 | `06. Playbooks/Project Continuity/Workflow 70 - Official Company Source Capture and Reconciliation.md`; `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`; `tmp/wf70-official-capture-period-registry.json`; `tmp/wf70-phase6-parallel-capture-runbook.json`; `tmp/wf70-phase7-q2-rollforward-readiness.json`; `tmp/wf70-wf66-official-evidence-spine-validation.json` |
| Scheduled proof | `tmp/run-chain-post-close.json`; `tmp/run-summary-post-close.json` |

## WF68 delivery-channel approval packet requirements

### Current state

WF68 has internal OpenClaw/main-session handoff and advisor packet machinery. External delivery channels remain approval-gated because Telegram/Discord/email/etc. are config/auth/channel mutations.

Important blocker: latest `tmp/intraday-alerts/runtime-handoff-status.json` is `status=error` because `advisor-alert-packet-validation.json` has one critical error: `in_band_alert_labeled_wait_for_band:4`. An older `delivery-router-status.json` showed `EXECUTION_PACKET_READY` for ETN and XOM paper recommendation packets, but that artifact predates the later advisor validation error and does not authorize delivery or execution.

### Packet must include

1. **Chosen channel** — one named delivery path only: local Control UI, email, Telegram, Discord, or another explicit channel.
2. **Recipient/allowlist** — exactly who can receive alerts and who can respond.
3. **Delivery scope** — delivery only; no execution authority, no account authority, no owner-approval inference.
4. **Allowed message types**
   - `EXECUTION_PACKET_READY` only when trade-ready/in-band/sufficient official evidence gates pass.
   - Validation/blocker/failure messages.
   - Optional grouped digest for non-immediate alerts.
5. **Rate and quiet policy** — immediate only for trade-ready packets; grouped cadence for monitor/no-chase/stop-review states.
6. **Redaction contract** — no tokens, credentials, raw HTTP headers/bodies, raw account identifiers, or sensitive values.
7. **Approval language** — if `APPROVE` is used, it can only authorize the exact paper-only WF67 request under WF67 guardrails; live trading remains blocked.
8. **Rollback/disable plan** — exact disable path and proof that alerts stop.
9. **Test plan** — non-financial fixture message first, then a dry financial fixture, before any live alert delivery.
10. **Audit log** — path, timestamp, channel, redacted payload hash, outcome.

### Apply gates

- Explicit Randall approval of exact channel/config patch.
- Security/runtime posture review.
- Backup/export of touched config.
- Test message delivered only to allowlisted target.
- Post-change validation proves no live/account/trade/money authority flags are true.

## WF55 stale Call Log / outcome bridge work

### Audit correction

The original audit claim of 12 stale Call Log rows is now stale. WF55 already reconciled the 12 rows on 2026-05-19:

- 3 Correct: `LMT`, `XOM`, `RTX`
- 5 Superseded / non-scoreable: `ETN`, `JPM`, `GOOG`, `MSFT`, `AMZN`
- 1 Voided / non-scoreable: duplicate `NVDA` row #9
- 3 still Incomplete/Open: `NVDA` row #3, `BRK.B` row #8, `VRT` row #10

Current readiness remains `NOT_READY`: 18 state-history rows, 13.08-day history span, 5 realized outcome sidecar rows, 0 retained owner-decision rows. `tmp/probability-readiness-validation.json` has 0 critical and 3 warnings: history span below 30 days, max timestamp gap above 48 hours, and degraded sector-expansion board.

### Exact remaining work

1. Build proposal-only review packets for:
   - `NVDA` row #3
   - `BRK.B` row #8
   - `VRT` row #10
2. For each, compare original call against current Execution Board, portfolio config, price/band/stop posture, catalyst state, and WF70/WF66 official evidence.
3. Recommend one status only: `Correct`, `Incorrect`, `Incomplete`, `Voided`, or `Superseded`.
4. If main approves, mechanically patch only Call Log fields: `Status`, `Outcome`, `Date Closed`, `Notes`; preserve original call text.
5. Append only score-eligible closed outcomes to `data/state-history/outcome-updates-v1.jsonl` through the existing outcome-update validator.
6. Convert future WF68 advisor alerts into outcome-link proposals; append only after owner action/no-action or observed follow-up evidence exists.
7. Rerun probability readiness report and validator. Keep probability/win-rate language blocked unless gates truly pass.

## WF70 scheduled official-source capture assessment

WF70 is not just a manual-demand design anymore.

Current state:

- 31/31 tracked operating-company equities have official company release or official SEC filing evidence.
- 30/31 have SEC exhibit evidence; BRK.B is covered by official SEC 10-Q with the SEC-exhibit distinction explicit.
- WF70/WF66 evidence-spine validation is clean: 31 records, 165 checks, 0 critical, 0 warnings.
- Investor presentations and transcripts are not captured yet; they are explicitly represented as manual-required, not falsely green.

Scheduled design:

- Existing finance chains already run official capture scripts after fundamental metrics validation and before reconciliation/bridge.
- `tmp/run-chain-post-close.json` on 2026-05-23 shows official capture steps 9-16 all `ok`, then reconciliation/bridge steps all `ok`.
- `tmp/run-summary-post-close.json` is `warning`, not blocked; acceptance passed, chain exit code 0, artifact-index validation 27/0.
- WF70 Phase 6 runbook is ready for parallel capture: 7 disjoint workers, then sequential `validate_all -> registry_refresh -> reconciliation_refresh -> bridge_refresh`.
- WF70 Phase 7 Q2 rollforward readiness is complete but waiting for Q2 releases in mid-July 2026. Capture scripts need per-ticker source URL + `period_slug='q2-2026'`; consumers are registry-routed and need no code changes.

Recommendation: keep the current scheduled chain design. If implementing Phase 2 advisor-quality unlock, harden a Q2/event-triggered official-source refresh plan around the Phase 6 runbook rather than inventing a new cron path.

## Recommended implementation batches

| Batch | Goal | Stop line |
|---|---|---|
| B1 WF68 internal blocker repair | Fix `in_band_alert_labeled_wait_for_band:4`; rerun producer/router/advisor/outcome validation. | No delivery-channel apply; no execution. |
| B2 WF68 delivery-only packet | Draft Randall decision packet for one channel with allowlist/rate/redaction/rollback/no-execution terms. | Do not mutate config/auth/channels without explicit approval. |
| B3 WF55 remaining Call Log bridge | Review NVDA #3, BRK.B #8, VRT #10; propose statuses; append only validated score-eligible outcomes after approved patch. | No probability/win-rate/model-readiness claims. |
| B4 WF70 scheduled capture hardening | Convert Phase 6 runbook into Q2/event-triggered refresh design if needed; preserve validators and source-freshness downgrades. | Evidence only; no portfolio/canon/trade authority. |

## Validation gates

- **WF68:** advisor enricher validation `ok`; runtime handoff `ok`; router not older than advisor packet; all authority flags false.
- **WF55:** Call Log original text preserved; outcome sidecar validator `ok`; probability validator 0 critical; `NOT_READY` remains unless depth/span/owner-decision gates truly clear.
- **WF70:** official capture validator `ok`; registry refresh `ok`; reconciliation validator `ok`; bridge validator `ok`; evidence-spine validator `ok`.
- **Delivery channel:** exact approved config diff; non-financial test message; redacted audit log; rollback proof; no live/account/trade authority flags true.
