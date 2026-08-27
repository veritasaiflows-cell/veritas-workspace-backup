# Workflow 75 - AI Drop-Service OS Agent Training

Generated: 2026-07-03T07:28:46Z

## Bottom Line

Two persistent isolated OpenClaw agents now exist for the WF75 AI Drop-Service OS:

- `research-scout`: public-source market, competitor, trend, and vendor research.
- `qa-redteam`: independent critique, risk review, proof gaps, and acceptance checks.

Both agents have isolated workspaces and zero external routing bindings. Veritas main remains the orchestrator and final verifier.

## How To Communicate

### Safest daily path

Tell Veritas main exactly what to send:

```text
Veritas, send this to research-scout: Find 8 sourced examples of AI workflow audit or AI automation sprint offers for small service businesses. Return source links, pricing if available, promise, deliverables, and risk notes.
```

```text
Veritas, send this to qa-redteam: Challenge the AI Workflow Clarity Sprint offer. Find the top 10 claims, privacy, delivery, pricing, and proof risks. Return blockers first.
```

### Direct CLI path

Use a direct internal agent turn:

```powershell
openclaw agent --agent research-scout --message "Find 8 sourced examples of AI workflow audit offers. Return a source table and cite URLs." --json
```

```powershell
openclaw agent --agent qa-redteam --message "Review this offer for weak claims, privacy risk, delivery risk, and missing proof. Return severity-ranked findings." --json
```

Use a persistent session key when you want continuity:

```powershell
openclaw agent --agent research-scout --session-key agent:research-scout:wf75-research --message "Continue the AI workflow audit competitor scan. Add 5 more examples and dedupe against prior notes." --json
```

List stored sessions:

```powershell
openclaw sessions --agent research-scout --json
openclaw sessions --agent qa-redteam --json
```

### Current WebChat limitation

Do not expect `@research-scout` or `@qa-redteam` mentions in this WebChat to route directly yet. The OpenClaw agent-to-agent session tool currently blocks cross-agent sends until cross-agent visibility is enabled in config. I did not change that config in this slice. The direct CLI route above works now, and Veritas can still route tasks for you from the main session.

## Randall's Role

- Set the business objective and quality bar.
- Provide what is real, unknown, blocked, or owner-gated.
- Decide whether outputs are worth turning into a demo, offer, or build lane.
- Never treat helper output as final until Veritas integrates and verifies it.
- Approve any external channel binding, customer use, cron automation, payment/vendor setup, or runtime expansion separately.

## Agent Rules

- Research Scout gathers evidence. It does not decide strategy.
- QA Red-Team challenges claims. It does not approve final delivery.
- Veritas main integrates, verifies, and produces the final user-facing answer.
- External routing, cron dispatch, customer/public use, credentials, vendor/payment accounts, and finance/account actions remain blocked unless explicitly approved.

## Prompt Recipes

Research prompt:

```text
Find [number] sourced examples of [market/offer/tool]. Return: source URL, buyer, promise, price if public, deliverables, evidence quality, and what we can learn for WF75. Do not contact anyone.
```

QA prompt:

```text
Review [artifact/offer/workflow]. Return blockers first, then severity-ranked risks, missing proof, privacy concerns, weak claims, and acceptance criteria. No edits unless assigned.
```

Veritas routing prompt:

```text
Veritas, send Research Scout this exact research task, then send the result to QA Red-Team for critique, then integrate both into a recommendation.
```

## Trend Radar

- Vertical AI services are moving from generic chatbots to specific workflow outcomes.
- SMB lead intake, missed follow-up, support triage, SOP cleanup, and weekly research briefs are practical first offers.
- Buyers will care about trust, privacy, proof, and clear ROI more than the word AI.
- Multi-agent systems need memory, task ownership, stop lines, and QA gates to avoid producing polished confusion.
- Human review remains a selling point, not a weakness.
