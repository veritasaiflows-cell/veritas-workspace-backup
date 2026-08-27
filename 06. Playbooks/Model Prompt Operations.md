# Model Prompt Operations

## Purpose

Make prompt usage predictable across GPT5.4 Research, Gemini Flash, Claude, and Gemini Pro.

This note answers three operator questions:
1. where do I find the current prompts?
2. how do I know which prompt is next?
3. how do prompts get updated without drifting?

## Prompt stack

### Layer 0 - governed prompt-book registry

This is the metadata/control layer for reusable prompt families and internal challenge-solving patterns.

Current files:
- `06. Playbooks/Veritas Prompt Book.md`
- `tmp/prompt-book-registry.json`
- `tmp/prompt-book-lint.json`
- `tmp/prompt-book-eval-gap-packet.json`
- `tmp/prompt-book-pm-job-packet.json`

Purpose:
- index reusable prompt families, source paths, hashes, contracts, eval coverage, and stop lines
- route repeated internal challenges into WF74/WF88, PM jobs, validators, or pending Skill Workshop proposals
- keep prompt operations metadata-only

Rule:
- do not store raw prompts, raw responses, tool payloads, system prompts, secrets, or approval authority in the prompt-book registry

### Layer 1 — reusable prompt packs
These are the stable libraries.

Current files:
- `06. Playbooks/GPT5 Research Prompt Pack.md`
- `06. Playbooks/Gemini Flash Prompt Pack.md`
- `06. Playbooks/IC Model Routing Policy.md`
- `06. Playbooks/OpenClaw Model Deployment Plan.md`

Purpose:
- store reusable prompt patterns by model
- keep prompts categorized by task shape
- evolve slowly

### Layer 2 — active prompt queue
This is the operator-facing "what should I run next?" layer.

Current file:
- `06. Playbooks/Active Model Prompt Queue.md`

Purpose:
- list the next recommended prompts
- tie prompts to the current project lanes
- keep the queue short and current

### Layer 3 — raw outputs
This is the evidence inbox.

Folder:
- `tmp/external-research/`

Purpose:
- save raw GPT5 / Gemini Flash outputs
- keep cheap-model work reviewable
- avoid losing useful research in chat history

## How to know which prompt is next

Always check:
- `06. Playbooks/Active Model Prompt Queue.md`

That file should contain:
- the current recommended prompt
- the target model
- the exact task lane
- whether the prompt is `ready`, `hold`, or `done`

Operator rule:
- if you want the next low-cost task, use the top `ready` item in the active queue
- if you want a new kind of task, pull the pattern from the prompt pack and then add it to the active queue

## Prompt statuses

Use only these statuses:
- `ready` -> good to run now
- `hold` -> valid prompt, but not the next priority
- `done` -> already used for the current cycle
- `stale` -> no longer matches current reality; revise before reuse

## When prompts should be updated

Update a prompt when one of these is true:
- it produced a stale or misleading answer because the scope was too broad
- it produced useful work only after manual corrections
- the project state changed enough that the old framing is now wrong
- a better bounded version becomes obvious after usage
- a new model capability or limitation materially changes routing

Do not revise prompts just for wording churn.
Revise them when performance or routing truth changed.

## Update mechanism

### Small change
If a prompt mostly worked but needed a tighter instruction:
- update the prompt pack entry
- update the active queue item if it is still in rotation

### New recurring prompt type
If a new prompt pattern proves useful more than once:
- add it to the relevant prompt pack
- add a short note about when to use it

### Broken prompt
If a prompt causes repeated drift:
- mark the active queue item `stale`
- rewrite before reuse
- if the failure is durable, log the lesson in daily memory

## Current operator workflow

1. refresh or read `tmp/prompt-book-registry.json` when the prompt pattern should become reusable
2. read `06. Playbooks/Active Model Prompt Queue.md`
3. run the top `ready` prompt for the chosen model
4. save the output to `tmp/external-research/` when the model is GPT5 or Gemini Flash
5. ask Veritas to review the saved output if it may affect judgment or machine state
6. after review, mark the queue item `done`, `hold`, or `stale`
7. route recurring prompt friction through `prompt_book_eval_gap_packet.py` and `prompt_book_pm_job_packet.py`

## Durable rule

Prompt packs are the library.
The prompt book is the metadata registry and eval-routing control surface.
The active queue is the live control surface.
Raw outputs are evidence, not truth.
The deployment plan is the routing governor for when multiple local and external model lanes are simultaneously available.
