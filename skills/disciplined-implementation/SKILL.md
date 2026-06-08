---
name: disciplined-implementation
description: System-aware disciplined implementation for OpenClaw workspace code, automation, scripts, validators, manifests, chain steps, workflow code, and boot/control surfaces. Use when changing implementation surfaces that must preserve department ownership, reuse existing capabilities before creating new ones, scan upstream/downstream consumers, prove behavior before closure, and update continuity/control surfaces without increasing OS overhead.
---

# Disciplined Implementation

Build the smallest **system-correct** fix that closes the real contract gap without increasing long-term operating overhead.

This skill is not just a patching checklist. Treat Veritas as a self-contained operating system with departments, owner truth surfaces, validators, queues, boot files, and hard finance/security boundaries. A good implementation improves the system's ability to operate cleanly tomorrow, not just the local file today.

## Read First

Read only what the pass needs, but default to:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- the owning workflow or continuity note
- the changed file
- the nearest upstream producer and nearest downstream consumer when shared vocab, JSON shape, freshness metadata, or manifests are involved
- the smallest useful validator or acceptance harness
- `windows-powershell-workspace` guidance when the pass uses shell commands, Windows paths, encodings, wrappers, approvals, or scheduled chains

## Contract

Before editing, make these explicit:
1. the real defect or requested behavior
2. what file owns the change
3. what must not change
4. the proof gate and adjacent consumer that could silently drift
5. which department/owner surface owns the behavior after the change
6. whether an existing script/helper/validator/skill/control surface should be reused or extended
7. whether the change reduces or increases boot/load/queue/script overhead
8. which startup/routing/control surfaces and indexes need to know so future sessions do not rediscover it by broad search

If any of those are unclear, inspect before patching. Do not guess.

## Implementation Size Classes

Classify the pass before deciding whether to spawn, load major workflow contracts, or update broad control surfaces.

### Micro

Use for one-file or one-artifact fixes where the contract is already clear.

- Scope: one implementation file, one proof artifact, or one small routing/doc correction.
- Context: read the changed file plus the smallest validator/consumer needed.
- Execution: main session may do it directly when reversible.
- Proof: one targeted command or direct inspection is enough when no shared contract changes.
- Continuity: daily memory only if the result affects pickup state.

### Narrow

Use for bounded implementation that touches one owner plus one adjacent consumer or validator.

- Scope: one script/validator plus one adjacent consumer, README, or proof route.
- Context: owning workflow note, changed file, nearest consumer/validator, and the smallest proof harness.
- Execution: main session or one narrow helper packet; use `06. Playbooks/Subagent Spawn Handoff Template.md` if spawning.
- Proof: compile or syntax check, targeted behavior run, and the adjacent validator that consumes the changed contract.
- Continuity: update owning continuity/control surface only after proof.

### Major

Use when the pass changes shared semantics, authority boundaries, workflow state, multi-file control-plane behavior, or cross-surface contracts.

- Scope: multi-file workflow/control-plane change, schema/state-vocabulary change, automation authority change, or canonical-surface boundary.
- Context: owning workflow note, `06. Playbooks/Major Workflow Contract Standard.md`, spawn matrix/template if helper lanes are used, and independent QA when risk warrants.
- Execution: default to a bounded worker plus main-session integration unless the main-session exception is explicit.
- Proof: regenerated downstream artifacts plus the smallest consuming acceptance gate.
- Continuity: update live queue/continuity/daily memory and name checkpoint posture.

Do not make Micro/Narrow work satisfy the full Major Workflow Contract Standard. Do not downgrade Major work into a Micro label to avoid QA or authority checks.


## Blast Radius

Classify before choosing proof:
- `micro`: tiny local text/routing/proof-surface fix with no shared consumer
- `narrow`: one owner file or script plus a targeted validator
- `shared`: producer/consumer contract, generated artifact shape, routing, queue, helper, skill, or control surface
- `major`: integration behavior, finance authority boundaries, runtime/config/channel/auth, canon/portfolio, customer/public, SQL promotion, archive/delete, or broad workflow automation

PM jobs may already carry `validation_budget` and `closeout_mode` from `scripts/pm_implementation_job_queue.py`. Use that budget when it exists, but challenge it if the live blast radius is wider than the job claims.

## System-Aware Standard

Prefer changes that make the Financial OS flatter, more reusable, and easier to route:
- one owner per truth type
- generated artifacts are proof/review surfaces, not canon or approval
- scripts that remain should become better shared capabilities, not isolated clutter
- boot files should route work to the right owner surfaces with minimum load
- helper lanes should receive small department-owned packets, not broad workspace dumps
- validators should protect authority boundaries and downstream semantics

Do not optimize locally in a way that creates global ambiguity. A smaller diff is not good if it leaves duplicate truth, an orphan script, a hidden consumer break, or another control surface to remember.

## Reuse, Proof, And Flattening

Before adding a new script, validator, manifest field, workflow artifact family, dashboard, or boot/control surface:
1. search/read the nearest existing scripts, helpers, validators, skills, manifests, and owner notes
2. choose reuse, extension, or thin wrapper when safe
3. create a new surface only when reuse would create unsafe coupling, two-writer risk, authority ambiguity, or high regression risk
4. label any new surface as prototype, wrapper, validator, production entrypoint, or temporary proof
5. record the consolidation/migration/archive path after proof

Proof-first isolated scripts are allowed for safety, especially in finance/paper/canon workflows, but they must not become permanent by default.

For scaling workflows, prefer making the repeated pass easy to rerun before adding the next batch. If the current workflow depends on a remembered sequence of commands, create or extend a phase runner/manifest/validator unless doing so would create unsafe coupling. Report-only is the default; apply/import/promotion modes require exact approval references and stop-line proof.

Use the smallest proof ladder that proves the claim:
1. compile/syntax check for changed code
2. targeted behavior run
3. adjacent consumer or domain validator when a shared contract, truth surface, or authority boundary changed

Do not stop at compile-only when runtime proof is practical.

## Artifact Format Default

For generated proof, validation, queue, runner, state, and control-plane outputs, prefer JSON or SQLite as the default durable artifact. Do not create paired Markdown sidecars just because a JSON artifact exists.

Create Markdown only when one of these is true:
- Randall explicitly asks for a human-readable brief, packet, deck outline, or durable note.
- The file is an actual owner-facing review surface, not a duplicate of machine proof.
- A cron/PM handoff needs a compact human summary that Randall or main-session Veritas will read.
- The artifact belongs in a durable note/playbook/procedure rather than `tmp/`.

If Markdown is optional, expose it behind an explicit flag such as `--write-md`; leave JSON as the normal `--write` output. For `tmp/` proof surfaces, JSON-only is the default unless a consuming route proves the Markdown is read.

## Implementation Procedure

1. Reconstruct the live system contract from code, owner notes, validators, workflow continuity, and boot/control surfaces.
2. Identify the owning department/surface and adjacent departments that consume the result.
3. Apply the reuse/proof/flattening gate before creating new files or entrypoints.
4. Prefer the smallest meaningful **system** diff: local enough to be safe, broad enough to prevent duplicate truth or orphan overhead.
5. Patch the owner first, then scan adjacent consumers, validators, ranking maps, fallback paths, manifests, summaries, and boot/queue references.
6. If a shared state label, manifest field, trust/freshness field, authority flag, proof path, or boot/queue routing rule changes, update at least one adjacent acceptance path in the same pass.
7. Re-run the smallest honest verification set before claiming closure.
8. Update continuity or control surfaces only after proof is real.
9. If the change affects a durable contract, authority boundary, workflow state, data family, source-of-truth route, or recurring answer path, inspect the relevant startup/routing surfaces (`TOOLS.md`, Startup Truth Index, Active Workflows, owning continuity note, relevant skill) and patch stale routing text in the same pass when safe.
10. Refresh or validate the relevant SQL/workspace index/live DB surface (`artifact_index.py`, `workspace_index.py`, `tmp/veritas-canon-cache.sqlite`, coverage registry, or ticker cards as applicable) so the new state is discoverable through the intended fast route, not only by broad search.

## Native Windows / PowerShell rule

Use `windows-powershell-workspace` for native Windows syntax, encoding, wrappers, and scheduled-chain behavior. Keep the common footgun here: do not use Bash-style `&&` or `||`; use PowerShell-safe dependent commands or Python wrappers.

## Node Cockpit Implementation Pattern

Use this pattern when changing `apps/pm-control-cockpit`, Node APIs, cockpit tabs, or local SQL-backed dashboard behavior.

- Inspect first: `state/pm-cockpit-source-registry.json`, `apps/pm-control-cockpit/src/server.ts`, changed public files, relevant source artifacts, and any SQLite schema involved.
- Keep the cockpit local-only on `127.0.0.1` unless Randall explicitly approves a trusted exposure change.
- Prefer existing local tools and fixed query helpers before adding npm dependencies.
- For simple local SQLite visibility, prefer the existing read-only allowlisted `sqlite3` CLI adapter pattern. Do not accept arbitrary SQL from user/browser input.
- Treat SQL cockpit data as derived control-plane visibility, not canon, approval, customer-data import, portfolio mutation, account authority, or execution authority.
- After changes, run the smallest proof set that proves the route: `npm run validate`, `node --check apps\pm-control-cockpit\public\app.js` when UI code changed, and probe `/api/state` plus the changed API route on the local server.

## Skill Boundaries

Use `safe-refactor-planner` when the primary job is behavior-preserving structure change: extracting helpers, reducing duplication, moving hard-coded chains into manifests, or paying down technical debt. Use this skill when implementation changes touch workflow contracts, authority boundaries, generated artifacts, adjacent consumers, validators, or boot/control routing. If both apply, plan the seam with `safe-refactor-planner` and close the system contract with this skill.

Example:
- Micro: change one JSON field label in a producer and run its parser/consumer check.
- Narrow: add a WF78 runner flag, run compile + runner phase + routing grep.
- Major: change a shared authority flag, regenerate downstream artifacts, run consumer validation, and update Active Workflows after proof.


## Proof Budget Rule

Do not force every implementation slice through the full closeout ladder.

Use this default mapping unless the owning queue says otherwise:
- `micro`: local proof plus queue/artifact refresh only when needed
- `narrow`: targeted proof plus PM state refresh
- `shared`: producer/consumer proof plus handoff refresh
- `major`: full integration closeout, usually including `control_closeout_bundle.py --write --validate`

The budget reduces repeated validator mechanics; it does not reduce judgment. Any authority or safety surface remains shared/major until proven otherwise.

## Stop Lines

Stop and reassess when:
- the patch widens scope beyond the stated contract
- the fix depends on stale artifacts you did not refresh
- a shared contract changed but no downstream proof exists
- the runner says success but the output artifact still contradicts the claim
- the change creates a new durable surface without an owner, load budget, and consolidation path
- the change duplicates truth that belongs to canon notes, Active Workflows, Startup Truth Index, a workflow note, or a skill
- local cleanup would weaken authority boundaries, review-only language, or finance/paper/live-account stop lines

## Control-Surface Rule

If the work closes or materially changes a workflow state:
- update the owning continuity note
- update the queue or registry only after proof
- keep wording honest about residue and next pass
- keep boot files lean: point to owner surfaces and proof indexes rather than copying long workflow history
- route department ownership through WF71/WF73-style indexes when available instead of adding another durable control plane

## Automatic Improvement Capture

After any coding, script, validator, manifest, or workflow-code pass, check whether the session exposed a reusable failure pattern or proof gap.

If yes, harden one of these before closure when safe:
- the nearest acceptance harness or validator
- this skill's procedure
- `windows-powershell-workspace` when the lesson concerns PowerShell, Windows paths, wrappers, encoding, approvals, or native-runtime behavior
- the owning script contract / README
- the live queue item with owner, next pass, and acceptance criteria
- the startup/routing/index surfaces that should have made the answer discoverable first (`TOOLS.md`, Startup Truth Index, Active Workflows, relevant skill, SQL/workspace index, live canon-cache/registry)

If the next step is ambiguous, ask a concrete question instead of guessing the coding direction.

## Output Format

Return in this order:
- implementation goal
- files changed
- reuse / flattening decision
- department or owner surface affected
- proof run
- remaining residue
- next workflow action


## Training/eval candidate scripts

When implementing scripts that prepare examples for evaluation, routing benchmarks, fine-tuning review, or model-quality analysis:

1. Keep the first implementation local and review-only.
2. Emit metadata-only rows by default: source path, schema, generated timestamp, validation status, task family, candidate id, quality signals, risk flags, redaction status, and recommended use.
3. Do not include raw prompt, chat, private memory text, secrets, account data, or unredacted finance execution context in generated candidate artifacts.
4. Include explicit authority flags blocking external upload, training/fine-tuning calls, model-weight mutation, WF55 outcome grading, portfolio/canon mutation, capital deployment, and paper/live/account action.
5. Validate that no candidate marked `training_candidate` or `fine_tune_candidate` is finance-boundary content, unredacted memory, unsafe authority context, or missing proof.
6. Route changed candidate-builder scripts through shared validation because they affect future evaluation/training quality.

Closeout proof should include `py_compile`, the candidate builder `--write --write-md --validate`, changed-file validator routing, and WF74 RSI validation when the work touches RSI/model-quality surfaces.

## Governance Footer

- Posture: Tier 1 structural skill for implementation governance; not an authority source by itself.
- Last structural validation: 2026-06-02 via `openclaw skills check` and boot-size guard after JSON-first/Markdown-restraint hardening.
- Deprecation trigger: review if implementation procedure moves fully into a canonical playbook, if `safe-refactor-planner` absorbs the behavior-preserving refactor portion, or if this skill again grows after a major control-plane change without validation.
