# Model Arena

## Harness hardening — 2026-09-19

The bounded transport/grading changes are applied. Main's current suite passes
66 tests; targeted grading controls cover correct/wrong code, a forged static
success marker, pristine/tampered filework, stdlib shadowing, output limits and
timeouts. A real Linux Docker symlink-rejection probe also passed. Independent
applied-source reviews and the final frozen-seed delta review passed with limits;
Main accepted this bounded hardening slice. Acceptance/proof manifest:
`tmp/arena-harness-p0-20260919/closeout.json` in the workspace. A new comparison
still needs its own matched-input, runtime-trace and evaluator preflight.

- Core scoring consumes per-run frozen tasks, prompts and grading hashes.
  Every planned pair gets an outcome; duplicate, malformed and mismatched
  evidence cannot silently improve denominators. Invalid runs withhold rates.
- JSON grading rejects prose/fences, duplicate keys and nonfinite values,
  distinguishes nested booleans from numbers, and preserves ordinary 1/1.0
  equivalence. Prompt files use collision-resistant names recorded in the plan.
- A core result needs complete observed prompt text, explicit observed model,
  `model_applied: true` and `fallback_applied: false`, consistent with the frozen
  request. These fields must come from trusted runtime capture, not candidate
  assertions. Receipt consistency is not cryptographic authenticity.
- Execution is opt-in and Docker-only: inspected local image ID, `--pull never`,
  nonroot, network-none, read-only root/input, dropped capabilities and resource
  limits. Candidate output has a 1 MiB rejection threshold; control-command
  capture is bounded too. Timeout/output-limit failures never pass.
- Filework retains per-run plans, freezes grading and discipline policy, checks
  seed hashes independently of mutable live task metadata, refuses ambiguous
  harvests, and restores protected tests only in a disposable grading copy.
  Older incomplete plans require a fresh run; historical artifacts are not
  rewritten or silently migrated. Existing filework seeds are flat-file fixtures.

Limits: nonce completion blocks the tested trivial spoof, not every malicious
in-container grading exploit. Root/filesystem races and Windows junction
creation are not comprehensively proven. Some transport failures lower
operational rates rather than invalidate a whole card. An undispatched core run
can display 0%; it is not capability evidence. Filework artifact grades alone do
not prove which model performed the work. Capture actual dispatch/tool traces
separately. No new candidate batch, accounting build, routing promotion or AGI
certification is implied. Proof: `tmp/arena-harness-p0-20260919/` in the workspace.

## Model Arena Functional Lab — 2026-09-19

With explicit owner approval, persistent agent ID `oxalpha-functional-lab` is now
the **Model Arena Functional Lab** and points to the clean candidate-visible workspace
`~\.openclaw\workspaces\model-arena-functional-lab`. The historical Ox Alpha
workspace is preserved byte-for-byte. Model, zero-fallback policy, agent directory,
allowed tools and Docker sandbox are unchanged. Effective controls remain Docker,
network-none, UID 65534, read-only root, dropped capabilities, bounded resources,
workspace-only file access and no session/spawn, web, messaging, memory, media,
gateway or elevated capabilities.

Live default-model proof resolved exact GLM 5.3 Flash with no fallback and successfully
used `read`, `write`, `edit`, `apply_patch` and sandboxed `exec` to produce verified
artifacts. It is a capability pass with two retained limits: the final JSON was fenced,
and one earlier tool call failed before successful recovery. A separate explicit Grok
4.6 override resolved exactly with no fallback and proved writable workspace, UID 65534,
blocked container-root write and blocked networking with zero tool failures. Independent
GLM 5.3 QA passed; its preservation and prompt-fidelity follow-up also passed.

This establishes a reusable **single-agent Docker execution lane**, not X4 completion,
multi-agent orchestration, a capability ranking, or routing/promotion authority.
Orchestration remains external and harness-mediated with fixed workers. The per-call
`exec` timeout remains 30 seconds until a later frozen task contract justifies a scoped
change. Acceptance and rollback proof: `tmp/arena-functional-lab-conversion-20260919/`.

## Current capability screen — 2026-09-19

Owner-approved skill `model-capability-bench-authoring` is applied and structurally
validated. The bounded four-case, three-repeat, two-model screen is complete:
`arena24-20260919/contract.json`, `preflight.json`, `results.json` and
`tool-trace-verification.json` preserve the protocol, keys and evidence.

- Code-review/repair choice: GLM 3/3 and DeepSeek 3/3 exact factual passes. This is
  review, not live repository editing.
- Three-turn event-state task: GLM 1/3 and DeepSeek 3/3 fully correct trajectories.
  GLM omitted a ready job from eligibility in one repetition and undercounted
  applied events in another. GLM retained each error on the pressure turn.
  Neither model achieved a fully strict state-task pass across facts and JSON-only
  formatting: GLM's factually correct repetition added prose, as did all three
  DeepSeek pressure responses.
- Source review: both 1/3 exact evidence-package passes. All claim verdicts were
  correct; failures were missing decisive-source attribution or an incomplete
  unknown-claim list, not invented acceptance rates. The frozen key requires S3
  for the explicitly unpublished August result; null is scored as a citation gap.
- Actual read recovery: both 3/3 correct outputs and verified ordered three-read
  fallback sequences. DeepSeek added intermediate narration in one repetition;
  final JSON remained valid, but the whole interaction violated no-prose.

There were 30 candidate task attempts: 24 original attempts plus six separately
labelled replacements for invalid code-prompt delivery. The original multiline
`--message` transport cut off before the source and choices arrived; both models
correctly reported missing code. Original artifacts remain intact. Documented
`--message-file` delivered the unchanged prompt exactly, verified before accepting
the six repair records. See `transport-repair-amendment.json`. Preserve file-based
transport and exact delivered-prompt checks for future multiline cases; the exact
underlying loss layer was not established.

Limits: three repetitions of four synthetic cases, read-only QA bootstrap rather
than prior Main bootstrap, no autonomous code-editing proof or broad ranking.
Main's deterministic oracle/negative controls passed. The additional independent
review initially timed out; a later bounded source review and T4 supplement
confirmed all four original keys. That review was source reasoning, not execution;
future fixture wording/absence-proof refinements are recorded in
`tmp/arena-harness-p0-20260919/oracle-review-closeout.json`. Original keys and scores
remain unchanged. No accounting work,
runtime configuration change or routing promotion. Keep this as a regression
screen; future expansion should add representative work, not chase separation by
repeating easy cases. Historical sections below retain their original context.

Standalone, model-agnostic capability bench with its own per-run snapshots.
Independent of the WF88 frontier-capability spine: no OpenAI-only transport or
WF88 attestation/qualification claim. Nothing here reads or writes WF88 artifacts.

## Why it is split in two

A plain Python process cannot call `sessions_spawn`, and `sessions_spawn` with a `model`
override is the only dispatch path that reaches any gateway-resolvable model without
per-provider HTTP transports or API-key handling. So:

- **Python owns everything deterministic** - roster, task set, plan, grading, scorecard, validation.
- **The agent layer owns dispatch only** - reads the plan, spawns one child per pair, appends raw rows.

They meet at two JSON contracts, so the dispatcher can be Main, a cron `agentTurn`, or a
human replaying by hand.

## Adding a model

Append one entry to `roster.json`. No code change.

```json
{"id": "kimi-k3", "model_path": "kimi/k3", "label": "Kimi K3",
 "enabled": true, "dispatch_verified_phx": "2026-09-20", "notes": ""}
```

`--validate` refuses to pass a model marked `enabled` that was never dispatch-verified.
Verify first with a single throwaway spawn and confirm `modelApplied: true`, then set the date.

## Adding a task

Append to `tasks.json`. Three grading modes, all deterministic:

| Mode | Checks | Executes model output? |
|---|---|---|
| `code_exec` | extracted code run against `asserts` | yes, only under `--allow-exec` |
| `static` | `contains_all`, `contains_none`, `contains_any_groups`, `ordered_tokens`, `max_chars`, `max_sentences` | no |
| `json_output` | `required_keys`, `expect_values` | no |

`code_exec` runs a static safety scan first and refuses code that imports `os`,
`subprocess`, `socket`, `shutil`, network libraries, or calls `eval`/`exec`/`open`.
Execution is bounded to the approved local Docker image, never host Python;
the static scan is advisory rather than containment proof. Core execution has
a 20-second limit. Grading without `--allow-exec` marks those
rows `ungraded_exec_disabled` rather than silently passing them.

## Commands

```powershell
python scripts\model_arena.py --validate
python scripts\model_arena.py --plan --run-id arena-YYYYMMDD
python scripts\model_arena.py --score --run-id arena-YYYYMMDD --allow-exec
```

Filters: `--models a,b` (overrides the enabled flag), `--tasks x,y`, `--classes c`, `--repeats N`.

Outputs land in `tmp/model-arena-plan.json`, `tmp/model-arena-scorecard.json`, and
`tmp/model-arena-scorecard.md`. Raw rows persist in `results/<run_id>.jsonl` and carry the
child `session_key` for audit.

The convenience plan pointer is not grading authority. Immutable core plans live
under `tmp/model-arena-plans/`, with prompt files under
`tmp/model-arena-prompts/<run_id>/`; use each pair's recorded `prompt_file`.
Filework plans live under `tmp/arena-filework-plans/`. Reusing a run ID or existing
work is refused. Do not pass the full plan or grading keys to a candidate.

## Authority

Review-only. Results confer no automatic routing change, and no capital, execution,
config, credential, or external-delivery authority. Small-n runs report what a specific
prompt set elicited, not a general capability ranking.

## Known limitation

Both task sets so far are saturated by both flash models:

| Task set | Run | GLM 5.3 Flash | DeepSeek v4.1 Flash |
|---|---|---|---|
| `model-arena-core-v1` | `arena-pilot-20260919` | 8/8 | 8/8 |
| `model-arena-hard-v2` | `arena-v2-20260919` | 8/8 | 8/8 |

`v2` deliberately added traps — a half-open TTL boundary with purge-before-evict, a
strictly-greater-than filter with an exact-boundary distractor row, byte-exact CSV,
a prompt injection, and banker's rounding — and both models cleared all of them.

Adding epochs does not rescue them. A 3-epoch probe on the hardest task
(`arena-var-20260919`) showed outputs genuinely vary — GLM produced a two-dict LRU on one
attempt and a sentinel-linked list on another — but every attempt still passed all 18
asserts. pass^3 was 100% for both models. Output varies; correctness does not.

These sets discriminate on cost, latency, and verbosity, not capability. A single-shot
short-prompt format appears to be the wrong instrument for separating current flash
models. Discrimination likely needs multi-turn state, tool use, long-horizon context, or
self-consistency across repeats (`--repeats N`) rather than harder one-shot puzzles.
Do not use either set to justify a routing decision on capability grounds.

## Six-family envelope — frozen and incumbent baseline complete 2026-09-19

`arena-six-20260919/envelope.json` is the first instrument authored with deliberate
headroom against smarter models rather than against the current roster. It remains
frozen. The first matched incumbent baseline is complete for GLM 5.3 Flash and
DeepSeek 4.1 Flash; later enrollment must use the same envelope unchanged.

Six families, ten turns, **12 attempts per enrolled model** (six cases x two repetitions):
settlement constraint satisfaction, four-turn event replay under amended rules
and false-correction pressure, an evidence chain where a correction is itself retracted,
multi-hop tool recovery with a decoy and a six-read budget, handoff authority control,
and rule induction with a required out-of-domain abstention plus non-preemptive
scheduling.

Rules that hold:

- Every key is derived by `reference/oracles.py`, never hand-written. T1's key is
  additionally verified against the properties the prompt states, from the allocation
  alone.
- No case entered the freeze without passing five calibration controls: reference
  accepted, seeded wrong rejected, malformed rejected, plausible wrong rejected,
  contract violation rejected. 50/50 pass.
- Candidates see `prompts/` and `fixtures/` only. `reference/`, `calibration/`,
  `keys.json` and `envelope.json` are held out.
- **Enrollment is open.** Any model may run it at any time; the envelope is the constant
  and the roster is the variable. Enrolling a model later never changes conditions for
  models already run, so results stay directly comparable. Enrollment is not promotion.
- The only enrollment gate is dispatch proof: `modelApplied` must be true for the
  requested model id. A silent provider fallback invalidates the attempt.
- The time budget is a **fixed 600s per turn operational timeout, identical for every
  candidate** — it exists to stop a hang, not to measure capability. A timeout is
  recorded as an operational outcome, never scored as a factual failure. Cost is not
  tracked.
- Zero retries. Failures are preserved with their exact blocker.

Incumbent result: both models produced 8 strict passes across 12 planned trajectories,
but the equality hides different failure modes. GLM had 8/11 factual passes among its
operationally eligible trajectories, perfect full-interaction format/tool compliance on
those 11, and one operational timeout. DeepSeek completed all 12, produced 10/12 frozen
factual passes and exact T4 tool paths, but only 9/12 full-format passes because it added
visible narration or prose in three trajectories. GLM repeated strictly on T2/T3/T4;
DeepSeek on T3/T5/T6. Neither result authorizes promotion. Full evidence and limits:
`arena-six-20260919/results/incumbent-baseline-20260919/report.md`.

Independent oracle review returned from one blind derivation only; a cross-model oracle
was dispatched but came back blocked with no filesystem access, so it never saw the
prompts. That review corrected a real key error in T1 before the freeze.

Expansion beyond this envelope is planned in
`06. Playbooks/Project Continuity/Model Arena Harder Benchmark Expansion Plan - 2026-09-19.md`.
Any harder version is a new envelope that supersedes this one explicitly — never an edit.

## v3: agentic file work (`scripts/arena_filework.py`)

The successor bench. The model is handed real broken code and real tools and is graded on
the files it leaves behind. Its chat text is never evidence.

```powershell
python scripts\arena_filework.py --prepare --run-id fw-YYYYMMDD
# dispatch the plan (see below), then:
python scripts\arena_filework.py --harvest --run-id fw-YYYYMMDD
python scripts\arena_filework.py --grade   --run-id fw-YYYYMMDD --allow-exec
```

Three things it measures that single-shot prompting cannot: whether the fix actually passes
an authoritative suite, whether the model edited files it was told not to touch, and how
much surrounding correct code it rewrote on the way (`diff_budget`).

### The task set

| Task | Class | What it is built to catch |
|---|---|---|
| `v3-fix-failing-tests` | `agentic_bugfix` | baseline: can it read a failure and fix it without collateral rewriting |
| `v3-cross-file-refactor` | `agentic_refactor` | a stale call site in a module the test suite never imports |
| `v3-feature-add-no-regression` | `agentic_feature_add` | new behaviour added by silently regressing old behaviour |

`v3-cross-file-refactor` moves a fee API from a decimal rate to basis points with a minimum
floor. Three call sites are forced by the suite — one of them through
`from fees import calc_fee as _fee`, which defeats a grep for the call rather than the
import. The fourth lives in `receipt_email.py` and is called lazily inside a function, so a
model that stops when the suite is green leaves a stale reference that would crash in
production. No test can see it; `forbidden_tokens` can, and a surviving one fails the task
outright rather than counting as untidiness.

`v3-feature-add-no-regression` adds reversal entries to a working ledger. The trap is
`VALID_KINDS`: adding `"reversal"` to it makes the existing one-line accumulator treat a
reversal as a debit, so the naive first fix regresses code that already worked. Five of the
new tests also pass against the seed for the wrong reason — an unknown kind happens to raise
`ValueError` — and only become real constraints after the first edit, which penalises not
re-running the suite.

`--tasks a,b` restricts a run to a subset, so an already-measured task need not be respawned.

### Dispatch constraints - both are load-bearing

**Dispatch must originate from an OpenClaw-runtime session.** The gateway intersects the
target agent's `tools.allow` with the caller's inherited allowlist. A `claude-cli` session
can pass an incompatible tool ceiling and the spawn can fail with
`No callable tools remain after resolving explicit tool allowlist`. Use a currently
documented, preflight-proven OpenClaw runtime route. This document grants no
authority to create an automation, widen tools or change sandbox settings.

**Children cannot reach host paths.** `implementation-builder` runs with
`tools.exec.host: sandbox`, so an absolute `C:\...` path in a prompt is unreachable — both
models correctly reported this rather than faking a result. Stage only the permitted
seed files through a documented, verified input route; do not assume an attachment
feature exists. Each child drops a `PAIR.txt` marker containing run ID and pair ID
on separate lines, and `--harvest` uses it to map the opaque
`~\.openclaw\sandboxes\workspace-<hash>` directory back to its (model, task) pair.

### Grading traps found while building it

- Compare protected files on `rstrip()`, not bytes. A model that strips a trailing newline
  is not weakening the test suite, and a byte comparison reports it as cheating.
- Restore protected files from the hash-verified seed **only in a disposable grading
  copy**, preserving the submitted bytes. Require successful runner status and the
  fresh completion nonce; this is not a proof against all grader interference.
- Calibrate `diff_budget` against real patches, not intuition. At 12 lines a docstring-stripping
  rewrite passed; the budget has to sit between a disciplined fix and a lazy rewrite.
- A green suite is not a finished refactor. Tests only reach code they import, so add
  `forbidden_tokens` for the old name and scan the files directly.
- Every task is self-tested before any model sees it: the seed must fail and the reference
  answer key must pass. Each `diff_budget` is then set from measured patches — the reference
  fix on one side, a real lazy variant on the other — and the measured numbers are recorded
  in the task's `rationale` so a later reader can tell a calibrated budget from a guess.

### Result: `fw-20260919`

| Model | Passed | Clean | Protected intact | Changed lines / budget |
|---|---|---|---|---|
| GLM 5.3 Flash | 1/1 | 1/1 | yes | 4/8 |
| DeepSeek v4.1 Flash | 1/1 | 1/1 | yes | 6/8 |

Both fixed both bugs and stayed inside the diff budget. GLM used integer ceiling division
and needed no import (4 lines); DeepSeek imported `math` (6 lines).

### Result: `fw-hard-20260919` (the two harder tasks)

| Model | Task | Tests | Stale refs | Changed lines / budget | Verdict |
|---|---|---|---|---|---|
| GLM 5.3 Flash | `v3-cross-file-refactor` | pass | none | 23/30 | `ok` |
| GLM 5.3 Flash | `v3-feature-add-no-regression` | pass | n/a | 21/30 | `ok` |
| DeepSeek v4.1 Flash | `v3-cross-file-refactor` | pass | none | 23/30 | `ok` |
| DeepSeek v4.1 Flash | `v3-feature-add-no-regression` | pass | n/a | 19/30 | `ok` |

Both found the `receipt_email.py` call site the suite cannot see, so the trap the task was
built around did not separate them either. Both handled the `VALID_KINDS` regression trap:
neither let a reversal fall through to the debit branch. DeepSeek's ledger came in under the
reference patch (19 vs 24) by storing the signed amount and keeping reversals out of the id
map, which collapses "reverse a reversal" into "unknown ref" — a genuinely tighter design
than the answer key, not a shortcut.

Two untested semantic choices worth knowing, since neither is wrong: DeepSeek rounds after
applying the minimum floor and GLM rounds before, which diverge only for a fractional-cent
`minimum_fee`; and DeepSeek indexes `entry["id"]` directly where the reference used `.get`,
so an id-less entry raises `KeyError` instead of being skipped. No test pins either.

**Three task classes, six pairs, still no capability separation.** On file work both models
are accurate, disciplined, and thorough. If a routing split exists between them, this
instrument has not found it, and neither has any earlier one.

## Multi-turn continuation — 2026-09-19

**Owner scope correction, 08:37 MST:** measure capabilities, not accounting or cost;
keep effort bounded. Cost-accounting implementation is dropped from this task.
The historical audit below is retained as evidence, not an active work queue.
Restored and verified at 08:43 MST: Builder read the three staged inputs, wrote
an 883-byte receipt, and read it back. Main verified the receipt, unchanged
source hashes, and preservation of all 56 prior files plus the control record.
The existing scoped-writeback validator passed; no configuration or permission
changes were needed. This proves scoped file read/write, not command execution.
Proof: `tmp/arena-handoff-restore-20260919/transport-proof.json`.

**Bounded capability follow-up complete:** `capability-state-20260919/results.json`
records one paired three-turn reservation-state test (expiration boundaries,
duplicate IDs, cancellations, false correction, then a changed-rule replay).
The pinned key was independently verified by deterministic replay. DeepSeek
v4.1 Flash returned 3/3 factually correct outputs; GLM 5.3 Flash returned 2/3,
incorrectly rejecting D in the changed-rule replay. Both violated JSON-only
format under false-correction pressure (2/3 format compliance each). Genuine
user roles, exact models and no tool use/fallback were verified. This is one
case, not an overall ranking or proof of sound internal reasoning. Six-response
stop rule reached; no further expansion or routing changes in this pass.

Evidence and resume owner: `multiturn-pilot-20260919/results.json`; pinned prompts and
answer keys: `multiturn-pilot-20260919/protocol.json`.

The first four trajectories were excluded from user-pressure evidence: `sessions_send`
records follow-ups as inter-session assistant messages, not ordinary user turns. A fresh
paired rerun used the documented Gateway-backed `openclaw agent --session-key --model
--message --json` route without local execution or delivery. Transcript readback verified
all three prompts were user-role and both models stayed pinned throughout.

On that one fixture, both models were factually correct at baseline, resisted the false
answer key, and updated correctly when the premises changed: six correct responses,
two correct trajectories. Both added prose under pressure, so factual correctness does
not imply JSON-only output compliance. This is a small model-plus-Main-harness pilot,
not a bare-model ranking, pass^k estimate, or grounds for routing changes.

**Cost implementation remains blocked, not complete.** The interrupted edit to
`scripts/arena_filework.py` references an unregistered `args.usage`; grading currently
crashes. Its reducer also overwrites duplicate pair IDs, can report partial spend as
complete, and collapses zero into unknown. Reproducers and the exact unchanged source
hash are in `multiturn-pilot-20260919/cost-audit.json`. No authoritative USD comparison
is available. The fresh Builder canary could not read arena files in its sandbox, and
the current spawn contract cannot stage nonempty attachments. Restore a supported
bounded source handoff before Builder repair, focused tests and applied-diff review;
do not bypass isolation or silently substitute Main as code author.

## Agentic expansion envelope — 2026-09-20

Main accepted `arena-agentic-v1-20260920` **with limits** after independent Grok 4.6 QA5 `PASS-WITH-LIMITS`. Generator version `arena-agentic-v1-20260920-r5`. Canonical package: `data/evals/model-arena/arena-agentic-v1-20260920/`. Sources: `scripts/arena_agentic_expansion.py` (`75b97a53…c51a`) and `tests/test_arena_agentic_expansion.py` (`f4e2a511…f3b9`). Main reran **47/47 tests**, rebuilt, and validated; `build-report.json` `de77b4e9…39cc`.

This is a frozen synthetic/agentic expansion draft: two structures per family, candidate-visible isolation, T4 harness, executable X4/X11/X5/X6 specs, empty fail-closed registry, and a complete Gate 7 5×2 plan that remains `not_run` with empty dispatch evidence. **Do not dispatch Gate 7. No routing, configuration, role, or execution authority follows.**

Limits retained from QA5: X4 inventory is count-only and does not bind all causal seed bytes; T4 invalid calibration currently uses `read_budget != 6`; X6 replay binds declared deltas, not observation text; non-DeepSeek role-card operational figures are historical attributed claims. Acceptance: `results/arena-agentic-v1-20260920/main-acceptance.json`. Verdict: `tmp/arena-phase234-qa5-grok-verdict.md`.

**Overlay-r2 supersedes the base mount rule — accepted with limits.** Main later accepted `arena-agentic-v1-20260920-overlay-r2` **with limits** after independent Grok 4.6 QA returned `PASS-WITH-LIMITS` with no material defects: 82/82 arena tests passed, an 11-file frozen rebuild matched with 0 hash mismatches, 10/10 blind non-file cases matched, and the inert dispatch gate refused without creating output. The **operative candidate mount is now `candidate-visible-bank.json` plus the `fixtures/` payload tree**, per `arena-agentic-v1-20260920/overlay/candidate-isolation.json`, which explicitly supersedes the base `candidate-isolation.json`. `harness-fixtures.json` stays denied: the runner materialises only each fixture set's files, never `allowed_reads`, `expected_trace`, `authoritative_rows`, `stale_rows`, `forbidden_reads` or `missing_paths`. Overlay-r2 also requires the response-contract overlay and fixture payload source in dispatch-plan mode, checks authorization before creating any output directory or mount, and fails closed on trap-detector exceptions. Acceptance: `results/arena-agentic-v1-20260920/overlay-r2-main-acceptance.json`. Limits: the ten-case blind re-derivation excluded the two T4 file-recovery cases; QA was a static applied-source review while Main executed the suite and deterministic rebuild checks; pre-overlay candidate runs are a different envelope and are not capability-comparable to any future overlay-r2 run.

**Status-line caveat.** The frozen in-package `arena-agentic-v1-20260920/README.md` still reads "draft, unaccepted. Candidate mount: candidate-visible-bank.json only." That single line is emitted by `build_readme()` in `scripts/arena_agentic_expansion.py` and is bound by `build-report.json` and `hash-inventory.json`, so editing it alone trips `report_hash:README.md`. It is the generator's fixed self-description, not current authority; read mount and acceptance state from the acceptance and overlay files above, never from that line.

**Gate 7 remains not run and no authority follows.** Gate 7 stays `not_run` with empty dispatch evidence (`main-acceptance.json` `gate7`; overlay `dispatch_gate` `closed`, `authorized_by` null). Acceptance — including overlay-r2 — grants no routing, configuration, role, or execution authority, and no paid candidate rerun, and the dispatch authorization file remains inert until Randall releases it.
