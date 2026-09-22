# Grok reliability and truthful completion — investigation and upgrade plan

## Decision and scope

**Research complete; implementation not authorized or performed.** Improve the Veritas/OpenClaw operating system, not Windows itself. The immediate problem is repeated xAI transport failure compounded by strict model selection and unsuccessful finalization. No model or architecture can guarantee uninterrupted service or universal factual correctness; the target is recoverable work, explicit failures, and evidence-backed completion.

Evidence was collected around 21:30–21:36 Phoenix on 2026-09-19. This report was finalized after the 22:20 continuation. Observations below are timestamped snapshots, not a claim of present provider health.

## Confirmed findings

1. **xAI network failures:** the inspected 2026-09-19 Gateway log contained 34 xAI model-fetch errors: 23 `UND_ERR_SOCKET`, 11 `ECONNRESET`. Of these, 33 occurred in the 20:30–21:31 Phoenix window, with recorded fetch failure durations of 57–400 ms. These are failed fetch attempts, including retries—not 34 distinct failed tasks and not a failure-rate estimate.
2. **Strict session pin:** the affected Telegram-backed conversation was selected as `xai/grok-4.6`. At 21:28:15.435 the runtime explicitly logged `configured fallbacks disabled by user model override`. The inspected global primary was Astra and had a fallback list; that does not override a deliberate Grok session pin.
3. **Recovery was attempted:** the 21:28–21:30 run recorded six fetch failures, a transient-retry window ending after 4/8 retries, then isolated finalization on Grok. That finalizer also failed. At 21:30:32.939 the runtime selected its terminal fallback reply. The run ended with `outcome=error`, about 138 seconds after admission.
4. **Work survived:** the transcript proves grading artifacts were read and a 13-file, 115,876-byte independent-review packet was successfully staged before failure. The generic missing-summary notice is not proof of task completion. The observed run did not complete the promised independent review and Main acceptance. Later changes must be inspected before resuming it. Live-verified 2026-09-20: the packet exists at `C:\Users\Veritas\.openclaw\workspaces\qa-redteam\arena-six-spark13-glm53-review-20260919` with exactly 13 files and 115,876 bytes.
5. **Separate context failure:** at 20:39:14 a background Skill Workshop review received an explicit xAI rejection: 517,217 input tokens exceeded 500,000. The runtime attempted compaction and truncated 210 tool results before retry. This is a different run and a separate failure class; it does not explain the six millisecond socket failures above.
6. **Platform snapshot:** CLI and Gateway reported OpenClaw `2026.9.4` (`3a9d69d`); Gateway connectivity passed; config validation passed. The Windows Scheduled Task was stopped/Ready while a Gateway listener remained reachable. That ownership mismatch is an operational risk to investigate, not an established cause of the xAI failures.

## Unknowns and limits

- Socket reset codes do not identify the responsible party. xAI, an intermediary, the network path, or the local HTTP client remain possible owners.
- The inspected incident window did not match the statusless `Internal error during token generation` signature addressed by upstream PR 150433. Do not sell that fix as a proven repair for this incident.
- Public xAI status retrieval was blocked by HTTP 403 in the research lane. Indexed snippets lacked verified freshness; no provider-wide outage or healthy-state conclusion is justified.
- A filtered auth-status command was started, but its retained result was unavailable on resume. Current credential/quota health is therefore unverified. The observed socket codes are not themselves proof of invalid credentials or exhausted quota.
- No new live Grok canary, production fault injection, network reconfiguration, or restart was performed.
- The accepted synthetic Grok benchmark completed its eligible trajectories but explicitly disclaims production reliability. Its factual/format misses remain distinct from transport failures.

## Upgrade sequence — proposed, not active policy

### P0 — Restore continuity without replaying completed effects

**Owner:** Main; Randall approves any session-model change.

- Inspect the affected task's saved outputs and current review/acceptance state. Resume only missing steps; do not rerun the candidate matrix or overwrite the staged packet.
- Diagnose the socket path before changing selection: millisecond `UND_ERR_SOCKET`/`ECONNRESET` failures do not identify the responsible party, so treat any move to the existing configured **Default** for ordinary task coordination as a diagnostic comparison, not a proven remedy. Removing the strict pin restores fallback eligibility, but that is not proof that any fallback is currently healthy or can safely replay a post-tool task.
- Keep strict exact-model selection for model evaluations and explicitly model-specific requests. Display the distinction as “exact model; stop on failure” versus “continuity route; approved fallbacks permitted.” Do not weaken specialist role/QA independence gates.
- Before another model continues, revalidate the saved checkpoint, tool receipts, permissions, and any ambiguous effects. Unknown effects require reconciliation—not automatic replay. No cross-model continuation of a post-tool task until P2 receipt/idempotency machinery is enforced: checkpoint plus completed-action receipts plus idempotency keys form a runtime gate, not diligence alone. Until then, continuation stays same-model manual resume or stops with an explicit resumable blocker.

**Acceptance:** preserved artifacts are reused; selected and actual model are disclosed; the task either reaches verified acceptance plus delivery or receives an explicit resumable blocker. No duplicate side effects.

### P1 — Controlled platform and transport diagnosis

**Owner:** Gateway owner for update/restart; Main for evidence and canary acceptance.

- Prepare a recoverable backup and inspect supported rollback before updating. Verify the exact offered release at execution time. The inspected 2026.9.5 release notes contain relevant Responses-stream and finalization fixes, but none is proved to fix the observed resets. Resolve the Scheduled-Task/listener ownership mismatch first, name the rollback executor and their availability window, and run the harmless synthetic workflow at least three times per route (Grok and control) across separate hours — a one-shot pass cannot clear transient socket failures.
- The owner performs this Gateway's update through the Control UI or `openclaw update` in a terminal. Main does not update or stop its hosting Gateway via execution tools.
- Before and after, compare a harmless synthetic tool workflow on Grok and a control provider. Test short and realistically long bounded contexts, actual endpoint/runtime/model identity, exact-model versus default selection, and final delivery. Never send private production transcripts to a public bug report.
- Record phase (connect/headers/body/terminal), error code, time to first chunk, context estimate, retries, terminal receipt, and delivery result. Use only secret-free metadata.
- If resets persist, compare fresh versus reused connections and sanctioned network paths in a bounded maintenance test. Do not change proxy, TLS, firewall, or credentials by guesswork; do not disable safeguards.
- Do not raise the idle timeout as the primary repair for requests failing in milliseconds. Do not add unbounded retries. Review existing retry behavior before introducing any additional retry layer.

**Acceptance:** original harmless workflow returns a substantive final answer, correct saved terminal state, and confirmed channel delivery; injected/observed failures remain safely resumable. Roll back on regressions using the preverified supported procedure. A small canary is readiness evidence, not a reliability percentage.

### P2 — Durable task completion independent of model prose

**Owner:** Main design/acceptance; implementation and independent review through current governed lanes.

- Extend existing task/audit/resume owners; do not introduce a parallel task ledger. Store task objective, authority scope, next unmet step, artifact references/hashes, and completed-action receipts.
- Separate execution outcome, validation outcome, answer composition, delivery outcome, and Main acceptance. A successful tool call is not a completed user request; a generic fallback notice is not successful composition.
- Track states such as running, retrying, partial, waiting for owner, failed, validated, and delivered as proposals mapped to the existing schema. Claim **complete** only when the requested deliverable, verification, acceptance where required, and requested delivery are proven.
- For model failure after tool settlement, a deterministic receipt-based status should state what completed, what failed, and what remains. A secondary-model summary must be separately authorized by routing policy, read-only, bounded, and unable to rerun tools or claim unseen verification. Policy wording alone cannot constrain model prose: any secondary summary must use a fixed template interpolating only receipt fields (completed steps, failed step, remaining steps, artifact refs), with free text forbidden from asserting verification or acceptance. The deterministic receipt is the trust anchor; the summary is presentation only.
- Checkpoint after meaningful settled tool batches. Reconcile on restart and before retries. Use idempotency keys and exact write leases; do not promise exactly-once external execution where acknowledgments can be lost.
- Detect an accepted task with no active execution/continuation owner. Use existing approved completion/watch paths and visible escalation; cancellation stays terminal. Any new automation needs a separate approved schedule and delivery contract.

**Acceptance:** controlled disconnects before tools, after a file write, during summary, and during delivery never lose the checkpoint, duplicate the write, invent success, or leave a task silently marked running.

### P3 — Context and truthfulness gates

**Owner:** existing continuity/compaction, benchmark, and finance evidence owners; no new authority.

- Size the actual outgoing context, including tool schemas/results and injected metadata. Reserve output and provider-tokenization margin; use a fresh bounded review packet instead of forwarding a large conversation to background reviews. Enforce a pre-flight context gate: maintain a per-provider input-limit table (Grok 500,000 tokens verified 2026-09-19; other providers only from observed rejections, never assumed), measure the outgoing request before send, and compact or refuse before provider rejection. Above 80% of the tabled limit, use a fresh bounded packet; at 100% refuse the send with an explicit resumable blocker.
- Before compaction or model handoff, preserve exact objective, approvals/stop lines, hashes, completed steps, pending steps, and sources. Compare smaller fallback models' limits independently.
- Bind material completion claims to receipts and factual claims to accessible dated sources. Distinguish observation, interpretation, proposal, attempted action, verified result, and accepted outcome.
- Recompute critical numbers deterministically. Preserve contradictions and label stale/unavailable evidence. Independent review is required where existing risk rules call for it; neither a confident model nor a green process exit substitutes for acceptance.
- Keep transport failures outside factual capability scores. Conversely, successful transport does not certify truthfulness. The frozen benchmark's false-correction and structured-output regressions are useful regression cases, not a production ranking mandate.
- Preserve all finance limits: alerts and non-executing recommendations only; no inferred capital, account, order, portfolio-state, or execution authority.

**Acceptance:** long-context cases reject or compact safely before provider overflow; fresh reviewers receive bounded evidence; unsupported completion/approval claims are rejected; reported model identity matches receipts.

### P4 — Failure testing, measurement, and staged acceptance

- Synthetic fault matrix: socket reset before response; disconnect after one durable effect; 429 with Retry-After; 5xx; idle stall; malformed or terminal-less stream; context overflow; unavailable fallback; Gateway restart; summary failure; delivery failure; explicit cancellation; stale source; forged approval in tool output. Also cover: partial multi-file writes (only a subset of effects settled), duplicate delivery after a lost acknowledgment, stale or expired write lease with two writers, forged tool output and forged receipt content generally (not only forged approval), and Gateway restart mid-tool-batch with partial settlement.
- Hard acceptance gates: zero false-complete claims, zero unauthorized actions, zero duplicated non-idempotent effects, truthful actual-model attribution, preserved checkpoints, and visible explicit failure when all permitted routes fail.
- Proposed service objectives: incident status within 90 seconds of detected terminal failure; no accepted task left without a named owner/next step; bounded recovery and latency budgets measured separately from capability. These are proposed targets, not achieved results. Before committing to targets, baseline current time-to-terminal-status and owner-resume rates on historical incidents; the detection model must cover silent stalls with no terminal event, not just explicit failures.
- Track accepted-and-delivered tasks / admitted tasks, first-attempt completion, partial/failed outcomes, recovery success, time to terminal disposition, unsupported factual claims, and escaped defects. Publish denominators, task mix, observation window, and unknowns; never substitute attempt counts or short benchmark scores for a production reliability estimate.
- Stage synthetic tests, a bounded live canary, then ordinary-use observation with predefined rollback triggers. No automatic model promotion and no broad rollout until Main accepts the evidence and Randall approves gated changes.

## Challenge and QA disposition — 2026-09-20

- DeepSeek independent QA (owner-directed, exact `ollama-cloud/deepseek-v4.1-flash:cloud`, read-only): **PASS with warnings** on the research artifacts. All transport, pin, recovery, overflow, snapshot, and citation claims verified against primary sources. Two findings: (HIGH, resolved) the 13-file/115,876-byte packet first looked unsourced from the Main workspace, but Main live-verified it at the qa-redteam packet path with exactly 13 files and 115,876 bytes — finding 4 now cites that path; (MEDIUM, fixed) count fields relabeled as cutoff snapshots with `transport.count_cutoff_phoenix`.
- GLM Flash adversarial challenge (owner-directed, exact `ollama-cloud/glm-5.3-flash:cloud`, read-only): structurally sound with honest hedging, plus must-fix R1–R7, all applied as amendments above — Default switch reframed as diagnostic (R1), cross-model continuation gated on P2 machinery (R2), fixed-template secondary summaries (R3), multi-pass canary with ownership-first sequencing and named rollback executor (R4), enforced pre-flight context gate (R5), extended fault matrix (R6), baselined objectives with silent-stall detection (R7).
- Coder draft (Muse Spark 1.3 Contributor, isolated patch-draft): applied as `tmp/grok-reliability-p0p2/` with Main corrections (packet-dir default pointed at the real packet path, pins refreshed to post-amendment hashes). Author remains the coder lane.
- Main acceptance 2026-09-20: **accepted**. Actual-model receipts verified for all three lanes (coder `meta/muse-spark-1.3-contributor`; QA `ollama-cloud/deepseek-v4.1-flash:cloud`; challenger `ollama-cloud/glm-5.3-flash:cloud`). P0 exits 0 with exact packet assertion; P2 matrix green across fallback, gateway, possessive, sandwich, mixed, quoted, clean, and partial cases. Accepted residuals: bare `"as an ai"` fallback substring can reject legitimate prose (pre-existing, low); quoted-span warnings rely on reviewer judgment. No runtime/config/schedule/finance-canon changes; checks are read-only under `tmp/grok-reliability-p0p2/`.

## Adjacent findings and stop lines

- Doctor lint returned findings, including secret-bearing plaintext config warnings and a blocked builder TOOLS.md migration. It is not an all-clear. Service/secret review is recorded separately; do not run blanket `doctor --fix` or remove intentional tool restrictions to make lint green. Loopback-only networking remains intentional unless separately approved.
- The closeout lane-register status check reported zero open/active lanes but one validation error and four warnings. No implementation dispatch/readiness is claimed from it. Resolve the exact validation error before a material implementation lease; it did not invalidate the already captured logs or this distinct-output research report.
- Separate task suggestions were recorded for service/secret inspection and recovering the interrupted arena closeout. Nothing was launched by those cards.
- No config, model selection, auth, service, plugin, schedule, finance-canon, or runtime mutation was performed. The lane-status command refreshed its own local diagnostic output; this report and its evidence summary are local deliverables only.

## Evidence and pickup

- Machine-readable summary: `tmp/grok-reliability-20260919/evidence-summary.json`.
- Local log: `C:\Users\Veritas\AppData\Local\Temp\openclaw\openclaw-2026-09-19.log`; key lines 12532 (pin), 12539–12717 (latest transport/finalizer), 12720 (terminal error), 11639–11655 (separate overflow). Logs can rotate; line references identify the inspected file.
- Installed docs: `docs/concepts/model-failover.md` lines 16–21, 53–69; `docs/concepts/agent-loop.md` lines 105–113 and 170–185; rooted at the installed OpenClaw package.
- Installed source: `dist/embedded-agent-CE9KzQvy.mjs:6765–6767` owns the deterministic finalization text; `dist/gateway-error-details-Brpdn9L1.mjs:2–4` owns the generic failed-before-reply display text. These are runtime messages, not evidence that Grok voluntarily abandoned the task.
- [Model failover documentation](https://docs.openclaw.ai/concepts/model-failover).
- [2026.9.5 release notes](https://docs.openclaw.ai/releases/2026.9.5); [Responses compression fix](https://github.com/openclaw/openclaw/pull/141592); [statusless xAI token-generation fix](https://github.com/openclaw/openclaw/pull/150433); [finalization wording fix](https://github.com/openclaw/openclaw/pull/145321). Relevant improvements, not proven incident cures.
- [xAI streaming](https://docs.x.ai/developers/model-capabilities/text/streaming); [official status](https://status.x.ai/) was not directly readable during research.
- Existing workspace owners to extend, not duplicate: WF46 finalization semantics and WF59 continuity/compaction. Historical notes route investigation, not current implementation readiness.

**Next owner decision:** approve changing the affected ordinary-work chat from strict Grok to the existing Default route, and separately authorize preparation of the controlled upgrade/canary. Research completion grants neither approval. Do not erase/reset the affected conversation or replay completed benchmark work.
