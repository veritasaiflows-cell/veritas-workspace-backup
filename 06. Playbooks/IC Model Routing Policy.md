# IC Model Routing Policy

## Purpose

Define how model family and thinking level should be chosen for independent-contractor work inside the Veritas OS.

This note exists because:
- different models are better at different kinds of work
- some models hit usage limits sooner
- cost and latency matter
- not every pass needs the highest-reasoning or highest-cost option

## Current model posture

### Gemini lane
Primary:
- policy name: `gemini-3.1-pro`
- current verified Gemini CLI ID: `gemini-3.1-pro-preview`
- alternate verified CLI ID: `gemini-3-pro-preview`

Fallback:
- policy name: `gemini-3-flash`
- current verified Gemini CLI ID: `gemini-3-flash-preview`

Not approved for normal use:
- `gemini-3.1-flash-lite-preview`
- unverified / non-working attempted aliases `gemini-3-flash` and `gemini-3.1-flash`

Notes:
- official Google model docs position Gemini 3.1 Pro as the advanced reasoning model for complex problems, large context, and agentic software work
- official Google docs also show thinking controls on Gemini 3.1 family models in API / Vertex documentation
- however, do **not** assume our current CLI harness exposes those thinking controls directly; if the CLI path does not expose them, route by model choice and task shape instead
- current Veritas OS posture is to keep Gemini model selection constrained to Pro and Flash for cleaner routing and less quality drift

### Claude lane
Primary:
- `Sonnet 4.6`

Available live menu on this machine:
- `Sonnet 4.6`
- `Sonnet 4.6 (1M context)`
- `Opus 4.7`
- `Opus 4.7 (1M context)`
- `Haiku 4.5`

Current operating posture on this machine:
- Claude CLI is now verified as callable locally
- Randall still handles Claude prompting/reporting directly by default
- Veritas may also invoke Claude CLI when useful, but Claude remains the judgment-first lane

Thinking / effort levels:
- low
- medium
- high

Rare escalation:
- `Opus 4.7`
- use sparingly because cost is materially higher
- official Anthropic docs position Opus 4.7 as the most capable generally available Claude model, with a step-change improvement in agentic coding over Opus 4.6

## Model-role fit

### Gemini
Best fit:
- multi-file implementation
- bounded script work
- validator wiring
- plumbing passes
- dashboard/workbook propagation
- structured phase execution
- long-context repository or artifact digestion
- cost/speed-tunable implementation passes when the contract is already clear

### Claude
Best fit:
- judgment-heavy reviews
- false-positive detection
- contract definition
- post-earnings interpretation
- canonical-state recommendations
- morning decision-surface logic
- difficult cross-artifact synthesis
- high-consequence command-center / presentation-layer cleanup where coherence matters more than raw speed

## Thinking-level guidance

### Gemini 3.1 Pro
Use when:
- the pass touches several files
- the architecture is already decided
- implementation quality matters more than novel interpretation
- the task needs sustained context over multiple sub-passes
- the task benefits from very large context or mixed inputs
- agentic coding quality matters, but the problem is still more implementation-heavy than judgment-heavy

Why:
- Google’s Vertex documentation describes Gemini 3.1 Pro as the advanced reasoning model for complex problems
- it explicitly highlights improved SWE and agentic capabilities, finance/spreadsheet usefulness, and a 1M-token context window

### Gemini 3 Flash
Use when:
- Pro is rate-limited or unavailable
- the pass is narrow and well-specified
- the work is mostly mechanical
- the contract is already defined and only a smaller implementation or audit pass is needed
- lower latency matters more than frontier reasoning depth

Do not use Flash for:
- first-pass architecture definition
- subtle trust or contract disputes
- ambiguous cross-layer judgment calls
- canonical note adjudication where a wrong judgment would cost more than the speed gain

Note:
- Google’s public docs clearly show thinking support across Gemini 3.1 family documentation, but unless the exact CLI runtime exposes that control, treat Flash as a model-tier fallback rather than a reliably tunable reasoning lane

### Claude Sonnet 4.6 — low thinking
Use when:
- the task is a narrow review
- you need a fast read on one note or one artifact
- the logic is already well-bounded

### Claude Sonnet 4.6 — medium thinking
Resource-optimized default Claude posture.
Use when:
- contract definition matters, but the consequence of a miss is moderate rather than severe
- deployment-readiness interpretation is still early or provisional
- post-earnings reasoning matters, but the source set is modest and the conclusion is not yet a canonical call
- the task benefits from careful synthesis but does not justify high effort or Opus
- you want the best speed/intelligence tradeoff in the Claude lane
- the goal is to screen, narrow, or pre-shape a later higher-effort pass

Why:
- Anthropic positions Sonnet 4.6 as the best combination of speed and intelligence
- medium effort is the right savings mode when the task is real judgment work, but not yet high-consequence final adjudication

### Claude Sonnet 4.6 — high thinking
Use when:
- the pass is judgment-heavy and expensive mistakes matter
- multiple conflicting artifacts need reconciliation
- the decision affects capital deployment posture or canonical-state changes
- the work needs stronger synthesis, but not enough to justify Opus cost
- you are close to a real operator decision, not just an exploratory screen

### Claude Opus 4.7
Use rarely, but more deliberately than before.
Reserve for:
- unusually consequential judgment passes
- difficult synthesis across many artifacts
- command-center / HTML / presentation-layer cleanup where coherence and agentic coding both matter
- situations where Sonnet repeatedly misses nuance or coherence
- hard mixed tasks that combine implementation depth with high-stakes reasoning

Why:
- Anthropic’s official model overview positions Opus 4.7 as the most capable generally available Claude model
- Anthropic explicitly claims a step-change improvement in agentic coding over Opus 4.6

Do not use Opus as the default just because it is stronger.
Use it when the incremental judgment or coding quality is actually worth the cost.

## Routing rules

### Rule 1 — routing ownership
Veritas owns Gemini routing and model selection inside the workspace.
Veritas also owns Claude CLI routing and model selection inside the workspace.
Randall may still prompt Claude directly, but the OS-level local routing layer is now Veritas-owned.

### Rule 2 — document before automating
Start by documenting routing policy.
Do not build a dedicated routing skill until the pattern proves stable across repeated projects.

### Rule 3 — route by task shape, not brand preference
Pick the model based on:
- implementation vs judgment
- ambiguity level
- cost sensitivity
- urgency
- context length required

### Rule 4 — downgrade only when the task allows it
If using a smaller/faster model:
- the contract should already be clear
- the pass should be bounded
- the review burden should remain manageable

### Rule 5 — expensive models should buy real risk reduction
Higher-cost models should be used when they materially improve:
- judgment quality
- cross-artifact reconciliation
- capital-deployment safety
- note-layer correctness

## Current practical routing recommendation

- **Gemini Pro** -> core OS integrity, multi-file implementation, large-context repo work, and structured plumbing passes; Veritas-routed by default
- **Gemini Flash** -> bounded cleanup or follow-on passes when Pro is exhausted and the contract is already settled; Veritas-routed by default
- **Claude Sonnet medium** -> default judgment lane; Veritas-routed locally by default, while Randall may still prompt Claude directly
- **Claude Sonnet high** -> higher-stakes deployment-readiness or post-earnings interpretation; Veritas-routed locally by default, while Randall may still prompt Claude directly
- **Claude Opus** -> deliberate escalation for especially consequential synthesis or command-center / HTML work where coding quality and coherence both matter; Veritas-routed locally by default, while Randall may still prompt Claude directly

## Fast routing table

| Task shape | Default model | Escalation | Fallback | Thinking posture | Cost posture |
|---|---|---|---|---|---|
| Multi-file script implementation | Gemini 3.1 Pro | Claude Opus 4.7 if coding+coherence both matter a lot | Gemini Flash | default / whatever the harness exposes | medium |
| Validator / gate / plumbing pass | Gemini 3.1 Pro | none unless the pass becomes ambiguous | Gemini Flash | default / harness-limited | medium-low |
| Broad workspace synthesis | Claude Sonnet 4.6 medium | Claude Opus 4.7 or Sonnet 1M | none | medium by default | medium |
| Post-earnings interpretation | Claude Sonnet 4.6 high | Claude Opus 4.7 | Claude Sonnet medium | high when capital-deployment judgment matters | medium-high |
| Deployment-readiness contract work | Claude Sonnet 4.6 high | Claude Opus 4.7 | Claude Sonnet medium | high | medium-high |
| Command Center HTML / presentation coherence | Claude Opus 4.7 | Opus 1M if context is huge | Claude Sonnet high | adaptive / higher effort when available | high |
| Narrow mechanical cleanup with a settled contract | Gemini Flash | Gemini 3.1 Pro if drift appears | none | default / harness-limited | low |
| Cross-project contradiction check | Claude Sonnet 4.6 high | Claude Opus 4.7 | none | high | medium-high |
| Massive-context note/audit synthesis | Sonnet 4.6 (1M) | Opus 4.7 (1M) | Sonnet 4.6 high | medium or high depending on stakes | high |
| Quick low-stakes Claude helper task | Haiku 4.5 | Sonnet 4.6 medium | none | low or medium | low |

## YOLO note for Gemini Pro

`gemini-3.1-pro-preview` may use YOLO posture selectively for bounded implementation work when Veritas explicitly chooses it.
That is an exception, not a general default.
Do not use Gemini Flash in YOLO posture.

## Flash-specific warning

Gemini Flash should not be used as the first pass for broad strategic synthesis in a fast-moving workspace unless the context packet is tightly curated.

Why:
- it is more likely to re-derive stale problems that have already been fixed
- it can produce a confident but lagging high-level brief when project continuity is spread across notes, chain logs, artifacts, and recent repairs
- it is better used after the contract, phase, and current state are already pinned down

Practical rule:
- use **Gemini Flash** for bounded implementation or audit tasks
- do **not** use it as the default model for "tell me the whole OS state" prompts in a rapidly evolving workspace

## Claude CLI posture note

On 2026-05-01, Claude posture changed from Desktop-only to verified local CLI readiness:
- `claude --help` works
- `claude --version` works
- `claude -p` headless invocation works
- live menu includes Sonnet 4.6, Sonnet 4.6 (1M), Opus 4.7, Opus 4.7 (1M), and Haiku 4.5

Claude is now a valid local CLI lane, but it should still remain permission-respecting and judgment-first rather than a default autonomous automation lane.

## Evidence notes

Public sources checked on 2026-05-01:
- Anthropic model overview: Opus 4.7 = most capable generally available model; Sonnet 4.6 = best speed/intelligence mix; Opus 4.7 called out for step-change agentic coding improvement over Opus 4.6
- Anthropic extended-thinking docs: Sonnet 4.6 supports adaptive/extended thinking controls; Opus 4.7 uses adaptive thinking with effort rather than the older manual token-budget mode
- Google Vertex model docs: Gemini 3.1 Pro is positioned as the advanced reasoning model with improved SWE/agentic capability, 1M-token context, and finance/spreadsheet usefulness
- Google Vertex model docs for Gemini 3.1 family show thinking support and multiple thinking levels in public docs, but this does **not** prove our current CLI harness exposes those controls

## When to build a routing skill

Build a reusable routing skill only after:
- at least a few parallel projects have used this policy
- model selection patterns are clearly recurring
- the routing logic is stable enough to outlive current chat context
- a routing artifact or checklist would save repeated manual decisions

Until then, this playbook is the right abstraction.
