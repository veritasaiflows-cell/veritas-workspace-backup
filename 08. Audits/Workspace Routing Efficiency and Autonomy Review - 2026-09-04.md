# Workspace Routing, Efficiency, and Autonomy Review

Owner: Main. Requested by Randall on 2026-09-04 (America/Phoenix).
Status: model configuration complete; review complete with limits; broader autonomy remediation remains open.

## Completed and verified

- Requested ordered fallback array saved using the documented OpenClaw config patch path, dry-run validated, applied without restart, and read back: Terra, Sol, Meta Muse Spark 1.3 Contributor, Opus 5, GLM 5.3, Kimi K3.
- Initial Astra primary was verified, then a concurrent writer changed the shared default to Luna and Muse Spark. Writer identity is unknown; test leakage is a hypothesis, not a confirmed cause. The explicit `agents.entries.main.model` patch subsequently passed dry-run/apply/readback, and the other active Main owner independently confirmed Astra plus all six fallbacks. Main no longer inherits the changing shared default. Existing session-specific overrides are not cleared.
- Three task-scoped, isolated OpenClaw child reviews were dispatched with requested Terra, Muse Spark, and GLM 5.3 models. These are not attested configured persistent-specialist writeback lanes. Reviews are advisory; no helper write authority or acceptance was granted. Actual Terra and Muse models were verified from returned history; both delivered useful read-only findings. GLM timed out at 10 minutes without a usable report and earns no completion/QA credit; its trustworthy usage is unavailable. The supplied Muse completion reports about 120k tokens, an excessive context load for this bounded research task; this is a failure to optimize, not a savings claim.
- Read-only route timing probe executed successfully. Status: 656.39 ms; WF84: 407.03 ms; WF85: 379.55 ms. These are single observations, not percentiles, savings estimates, or a before/after benchmark.
- Live WF84/WF85 router responses report `refresh_required`. A cached status card's green alerts row is not current finance readiness proof.
- Model-status inspection found OpenAI runtime auth usable and Opus 5 auth readiness indeterminate. Configuration order is verified; end-to-end failover through every provider is not.

## Verified operating map

| Need | Current owner / entry | Interpretation |
|---|---|---|
| Cached status | `scripts/status_card_packet.py --read-only --frontdoor --render --validate` | Fast, read-only; disclose cached timestamp and stale-input warnings. |
| Workflow identity | `scripts/workflow_router.py WF84 --answer summary` (or exact workflow ID) | Routing evidence, no execution authority; these probes reported no written files. |
| Operations queue | `tmp/pm-control-packet.json`, `state/pm-autonomy-policy.json` | Inspect generated timestamp and nested readiness; outer `ok` is schema/proof status, not all-green delivery. |
| Implementation | `scripts/project_implementation_router.py`, concurrent-lane register, implementation/routing skills | Currently inconsistent with requested Astra. Existing other-session lease covers 15 routing/bootstrap/skill files; preserve it. |
| Finance | `03. Alerts and Recommendations/`, finance SQL/effort owners -> guarded evidence and quotes -> alert controller -> WF84 -> WF85 | Evidence, alerts and non-executing recommendations only. Freshness and canon gates remain mandatory. |
| Recall and relationships | semantic memory for prior decisions; exact current owners for live truth; graph only as derivation | Graph file last modified 2026-08-24T03:05:54Z; stale for current architecture. No rebuild was run. |

This table is an audit map, not a replacement procedure or new authority source.

## Evidence and blockers

1. **Model and role drift (P0, local repair).** Startup/routing skills describe Sol; an older implementation skill describes Terra/Luna. A current router preflight selected Sol and observed Luna while the primary was being changed concurrently. Reproduce against a stable explicit Main config before attributing this to a parser bug. Canonical runtime roster uses `agents.entries`, not `agents.list`. Coordinate the existing owner's regression tests and actual-dispatch proof; do not weaken mismatch checks.
2. **Unattended runtime (P0, owner-gated mutation).** `openclaw status` reports gateway reachable but installed Scheduled Task stopped, and heartbeat waiting for a delivery route. This is a durability/delivery risk, not proof of total gateway failure. Inspect process ownership and task exit evidence, then propose exact startup/delivery correction with rollback. No service, channel, or heartbeat config changed here. Follow-up `openclaw gateway status --deep` exited 0 and confirmed CLI/Gateway 2026.9.1, service loaded but not running, connectivity probe OK, non-standard service environment handling, and active `diagnostics-otel` plugin 2026.7.1 versus expected 2026.9.1. Do not run broad doctor repair or plugin updates without a scoped approved diff/rollback.
3. **Current finance freshness (P0, existing owner).** WF84/WF85 explicitly require refresh. Phase 3G scope remains with its existing owner; do not restart another competing implementation or recurring cutover.
4. **Lane accounting (P1, evidence-dependent).** Three validator error groups: missing incident codes on two lanes; unavailable dispatch-index attribution on two retired WAVE2 lanes; missing finance-vector summary proof. Separate historical missing evidence from current execution failures. Do not invent incidents/usage, fabricate missing proof, or revive retired WAVE2.
5. **Standing autonomy scope (owner decision, not defect).** `state/pm-autonomy-policy.json` permits unattended proof refresh and planning but explicitly sets low-risk code changes, helper spawning without Main, and runtime/config changes false. Today's interactive implementation request does not silently enable permanent unattended code mutation.
6. **Telemetry limits (P1).** Runtime scorecard is an artifact-only bootstrap with zero timing checks, generated 2026-08-28. The efficiency review generated 2026-09-04T00:57:14Z reports 598 implementation-token gaps and incomplete fleet outcomes. Its historical aggregate is not this task's usage or an invoice. Do not infer efficiency improvement from it.

## Real model audio recommendation

Use the existing Windows Control UI's Browser Talk rather than build a second dashboard first. Installed `docs/nodes/talk.md` documents real-time bidirectional speech, interruptions, and `agent-consult`, distinct from TTS readback or transcription-to-text chat.

Documented quickest path: Settings -> Talk -> OpenAI -> `gpt-live-1-codex`, Browser WebRTC, agent-consult. Existing OpenClaw OpenAI OAuth is usable for text and is a documented eligible browser-audio auth route; actual voice entitlement and full OpenAI plugin readiness still need verification. The voice model is separate from Astra's text/reasoning model.

Current inspected Talk config has only realtime mode and agent-consult brain, with no explicit provider/model/transport. No Talk config, microphone, network exposure, provider session or audio generation was changed/tested. Acceptance: real speech roundtrip, interruption stops output, transcript joins intended Main session, consult returns actual task result, stop releases microphone, and failures are visible. No plaintext credentials in UI instructions or artifacts.

## Execution plan and acceptance

| Priority | Next action | Completion proof | Boundary |
|---|---|---|---|
| Done | Pin explicit Main Astra/order | Scoped config dry-run/apply, exact readback and independent owner readback passed | All other agent models and session-specific overrides preserved; provider failover not exercised. |
| P0 | Finish existing routing/bootstrap owner's QA with Astra and keyed-roster inheritance coverage | Focused tests + independent QA on actual diff; stable live config | Do not overlap the active lease or rewrite safety policy. |
| P0 | Diagnose unattended startup and heartbeat, then obtain exact repair approval | Task/process ownership, restart/reboot continuity test, intended delivery proof | Service/channel changes require approval. |
| P0 | Resume existing Phase 3G owner and refresh current finance evidence through approved paths | Mocked tests, independent QA, Main acceptance; fresh WF84/WF85 | No recurring cutover or finance-canon writes inferred here. |
| P1 | Resolve accounting debt without falsifying history | Typed evidence dispositions and validators | Retired WAVE2 stays retired. |
| P1 | Establish real efficiency baseline | Bounded contexts, per-attempt elapsed/usage/acceptance, small like-for-like samples | No invented savings; no automatic model promotion. |
| P1 | Configure/test Browser Talk if approved | Speech, interruption, transcript continuity, microphone cleanup | No new UI/server/plugin install needed by default. |
| Gate | Propose a standing low-risk repair envelope only after above proof | Allowed actions, exact write scope, retries, rollback, human escalation | Capital/accounts/execution remain outside this OS. |

## Proof and pickup

- `tmp/main-astra-fallback-patch-20260904.json`: initial defaults patch, no secrets.
- `tmp/main-astra-explicit-patch-20260904.json`: applied Main-specific patch, no secrets.
- `tmp/main-astra-model-verification-20260904.json`: exact primary/fallback assertions passed; provider failover not exercised.
- `tmp/astra-autonomy-route-timings-20260904.json`: measured route outputs and durations.
- `tmp/projects/astra-autonomy-review-20260904-20260905T055508Z.json`: failed exploratory preflight; includes both model drift and caller-omitted lease fields, not a clean product-only regression.
- `tmp/concurrent-lane-register.json`: current lease and error-group evidence; generated artifact, not permission.
- `tmp/phase3g-astra-scope-draft-20260904.md`: existing finance implementation pickup.

Main owns integration. The existing routing owner independently reports unchanged source hashes and no config edits from its focused validation work, narrowing but not identifying the concurrent config writer. It reports two Main/Sol checks failing live and adversarial model checks with warning-only/unknown-model acceptance; independent QA is not yet accepted. These are owner-reported follow-ups, not accepted fixes from this review.

This review does not claim full autonomy, all-blocker closure, persistent transport readiness, live voice success, or a completed performance optimization.
