# Model Arena — Harder Benchmark Expansion Plan (2026-09-19)

Status: expansion plan. X0 now has accepted three-model evidence, but its family-discrimination synthesis is still open; X1-X12 below are not implemented. Companion to `Model Arena Enhancement Plan - 2026-09-19.md`, which remains the governing plan for the current slice.

Revision 2 (2026-09-19) merges an external expansion suggestion. Cost/pricing tracking is **out of scope by owner decision** — gating below is expressed in wall-clock and attention, never money.

Revision 3 (2026-09-19) narrows the expansion to **agentic AI capability only**. In scope: reasoning, planning, tool selection and sequencing, observation-grounded replanning, terminal/repository work, recovery, durable continuity, delegation, orchestration, verification, truthful completion and authority control. Out of scope: PDF rendering, image/video/audio understanding or generation, GUI perception, and other multimodal benchmarks. Plain-text and structured files remain valid agentic fixtures and artifacts.

## Current X0 evidence checkpoint - 2026-09-19 17:52 MST

The frozen `arena-six-20260919` envelope has now run three candidates under the same keys and two-repetition contract. Main accepted Grok 4.6 with limits at 9/12 strict, 10/12 factual, 11/12 full-interaction format and 12/12 tool discipline; all 12 trajectories were operationally eligible and all 20 terminal receipts proved exact `xai/grok-4.6` with no fallback or reroute. DeepSeek 4.1 Flash and GLM 5.3 Flash each remain at 8/12 strict. Grok leads this bounded envelope by one strict trajectory, not by enough evidence to infer general reliability or authorize routing/configuration change. Proof root: `data/evals/model-arena/arena-six-20260919/results/grok46-20260919/`; Main acceptance: `main-acceptance.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

Observed Grok weaknesses are now frozen regressions: one false-correction factual miss in T2, one whole-visible-stream narration failure in T4, and one exact structured-package miss in T5. Independent GLM 5.3 QA returned PASS after the packet gained all 20 terminal receipts, full incumbent comparison evidence, transcript-derived T4 evidence and an explicit two-layer scoring contract. The X0 per-family discrimination labels still need a dedicated synthesis before X1-X12 expansion work begins; this result does not silently satisfy that exit gate. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Conclusion First

Every instrument the arena has ever run is saturated. Both enabled flash models score 8/8 on `model-arena-core-v1`, 8/8 on `model-arena-hard-v2`, pass^3 = 100% on the 3-epoch probe, and passed all three agentic filework classes across six pairs with no separation. Those sets discriminate on cost, latency and verbosity — not capability.

The frozen `arena-six-20260919` envelope is the first instrument built with deliberate headroom, but it is hand-authored and static. It contains ten prompt turns in total, with at most four turns inside any one trajectory. It will saturate too.

The external suggestion is directionally right and contributes two things this plan genuinely lacked: **cross-family integrated missions** and **progressive gating**. Three of its items need correcting before adoption — the horizon ladder uses the wrong unit, the fixture-count target ignores the real authoring constraint, and it under-weights generators relative to hand-authored breadth. Those corrections are argued in place below.

The arena must also distinguish three different claims that are often collapsed in public leaderboards: a model can reason about a task, a single agent can execute it with tools, or an orchestrator can coordinate workers to finish it. These become separate lanes with separate denominators; none may inherit credit from another.

## Assessment of the External Suggestion

| Item | Disposition |
| --- | --- |
| Hidden fixture bank, 5–10 per family | **Modified.** Structural diversity yes, the 30–60 count no. See X2. |
| Difficulty tiers | **Adopted** as X1. Gives the gating ladder something to gate on. |
| Cross-family integrated missions | **Adopted** as X5. Real gap in revision 1. |
| Longer horizon | **Modified.** Wall-clock minutes is the wrong unit. See X6. |
| Controlled perturbations | **Adopted** and merged into X3; its perturbation catalogue is better than mine. |
| Strengthen scoring | **Adopted** into X7; adds three dimensions the envelope lacks. |
| Contamination protection | **Adopted** into X8; mostly already doctrine, but fixture rotation and regression promotion are new. |
| Progressive gating | **Adopted** as X9. Valuable even without cost tracking. |
| "Roughly 24 core challenges" target | **Rejected as a quota.** Earn the number from X0 evidence; a quota produces unvalidated cases. |

Its closing principle is correct and worth keeping verbatim as a design test: frontier difficulty comes from unfamiliarity, interaction, recovery, long-horizon constraint preservation and verifiable artifact production — not from longer prompts or more obscure puzzles.

## X0 — Measure Real Difficulty (gate for everything)

No expansion item is worth building on speculation about where models fail. The frozen envelope has now run three candidates; use those accepted results for the first discrimination map and add later candidates only through open enrollment. Do not rerun or tune the accepted attempts. Produce, per case-turn and per dimension:

- strict pass rate per candidate
- which trap each failure actually hit, quoted from the response
- pass^2 reliability across the two repetitions, reported separately from single-run pass

Then label every case-turn `discriminating`, `too easy`, `too hard`, or `ambiguous`. An item every candidate passes, or every candidate fails, carries no information regardless of how hard it felt to author.

**This gate exists because perturbing or replicating a non-discriminating case multiplies noise, not signal.** That is why X0 stays ahead of the perturbation engine, which the external sequence placed fourth.

**Exit gate:** all six families labelled with evidence attached; items outside the band queued for hardening or retirement, not silently kept.

## X1 — Difficulty Tiers

Adopted. The arena currently has no difficulty taxonomy, which is why saturation kept surprising us.

| Tier | Purpose | Character |
| --- | --- | --- |
| Smoke | Catch obvious regressions cheaply | Exact JSON, simple bugfix, basic tool recovery |
| Professional | Representative daily work | Multi-file changes, source reconciliation, checkpoint recovery |
| Frontier | Separate strong models | Long context, hidden interactions, incomplete evidence, multiple tool failures |
| Adversarial | Test robustness | Injection, tampered tests, false authority, misleading corrections |
| Integrated | End-to-end competence | One mission crossing research, planning, coding, verification, handoff |

Honest placement of what exists: the legacy sets are smoke. `arena-six-20260919` is frontier on T1/T2/T6, adversarial in part on T3/T5, and has no integrated tier at all.

## X2 — Hidden Fixture Bank, Sized to Real Authoring Cost

Adopted in direction, resized. The external suggestion asks for 5–10 cases per family, 30–60 total.

**The binding constraint is authoring and oracle throughput, not ambition.** Each of the six frozen cases required a derived reference implementation, five calibration controls, and an independent blind derivation. That oracle pass found a real key error in T1 — a wrong key that had passed all 50 calibration controls cleanly. Skipping oracle review to hit a case count would produce fixtures that silently punish models reasoning correctly. That is worse than having fewer cases.

Target instead: **2–3 structurally distinct cases per family (12–18 total), each fully oracle-reviewed**, and get volume from X3 generators rather than from hand-authoring sixty keys.

Structural distinctness is the requirement. A second settlement puzzle with different numbers is not a second case; a settlement puzzle whose constraints are mutually unsatisfiable in a non-obvious way is.

**Initial X2 exit gate:** before Progressive Gate 3 opens, the bank contains at least two structurally distinct cases per family (12 total). Every included case has frozen prompt/fixture/key/grader hashes, all five calibration controls passing, an independent oracle verdict, and a candidate-visible isolation manifest. A third case per family remains continuous expansion work, not permission to admit an unreviewed fixture.

## X3 — Parametric Generators and Preregistered Perturbations

Highest leverage item. Hand-authored fixtures have one instance and one key, so they are memorizable, un-tunable, and give a binary saturated/not-saturated reading.

**Generators and the X2 bank are not alternatives.** A generator varies *instances within a structure*; the bank varies *structures*. A generator cannot invent a structure it was not given. Generators come first only because their cost per unit of discrimination is far lower.

Each family gets a seeded generator whose oracle is the existing reference implementation:

| Family | Difficulty dials |
| --- | --- |
| T1 settlement | order count, how many bounds bind, whether a lower bound releases |
| T2 event replay | stream length, revert depth, size of contested groups |
| T3 evidence | chain depth, validity windows, injection count |
| T4 tool recovery | hop count, decoy count, read-budget tightness |
| T5 authority | item count, false approvals, distance to the constraint |
| T6 induction | rule composition depth, DAG width vs worker count |

Layered on top, the preregistered perturbation catalogue (adopted from the suggestion, which states it better than revision 1 did):

- rename entities and alter values
- reorder irrelevant information
- change one decisive rule
- remove a required input
- inject a plausible but incorrect "official answer"
- cause one permitted tool to fail
- add distracting files or stale documentation

Variants must be frozen and oracle-reviewed before any candidate run — same standard as the base fixtures, no exceptions.

**Risk to manage:** generators emit degenerate or infeasible instances. Every generated instance passes the same five calibration controls and, where the prompt states properties, a property check of the kind that now guards T1.

**Exit gate:** generators reproduce the frozen hand-authored instances at their frozen seeds, and 100 random instances per family pass calibration and property verification.

## X4 — Real Tool Depth with Verifiable End State

T4 allows read only, six calls. Expand into the already-accepted Docker harness: read, write and execute against a sandbox, graded on the resulting filesystem state matching a checked target rather than on the model's narration.

Add failure injection — a tool returns an error, a truncated result, or silently wrong data partway through — and require detection and recovery. The harness already provides the timeout, output-cap and symlink-rejection controls this needs.

Agentic tool tasks must cover environment discovery, tool choice, argument correctness, sequencing, observation use, replanning, verification and stopping. Include terminal/repository changes, stateful workflow operations, and fixed-source research/reconciliation using frozen local snapshots. Live-web diagnostics, if ever run, stay separate because mutable search results are not a reproducible ranking instrument.

Grade the observed trace and resulting artifacts, not a self-report. A correct result with fabricated tool claims fails trace integrity; a plausible final message without the required artifact fails completion; unnecessary or prohibited calls fail boundaries even when the artifact is correct. Record failed, redundant and recovery calls as behavioral evidence. Token usage is not required, recorded, scored or used for gating; monetary cost is also outside the instrument.

**Lane preparation checkpoint — 2026-09-19:** owner-approved conversion of persistent ID `oxalpha-functional-lab` produced the Model Arena Functional Lab at a fresh workspace while preserving the historical workspace. Its default GLM 5.3 Flash canary used all five allowed tools and produced verified artifacts with no fallback, but retained a fenced-JSON format miss and one unattributed failed tool call before recovery. A Grok 4.6 override resolved exactly with no fallback and proved UID 65534, workspace write, blocked root write and blocked networking with zero tool failures. Independent GLM 5.3 QA and focused follow-up passed. This prepares the single-agent transport/containment lane only; it does not satisfy X4's fixture, failure-injection or grading exit work, and it does not grant session/spawn tools for orchestration. Proof: `tmp/arena-functional-lab-conversion-20260919/`.

**X4 is a hard prerequisite for X5.** Missions graded from artifacts and tool traces cannot be built before artifact grading exists.

## X5 — Cross-Family Integrated Missions

Adopted from the suggestion; the clearest gap in revision 1. Single-skill cases do not test whether capabilities survive contact with each other.

Six bounded missions, one led by each family, each crossing at least three capabilities:

- Diagnose an unfamiliar repository, implement a change, test it, produce a truthful handoff.
- Reconcile conflicting documents, identify missing evidence, update an artifact, preserve approval boundaries.
- Resume an interrupted project from incomplete checkpoints, distinguishing completed, failed and unverified work.
- Recover from missing files, truncated output and a denied tool without inventing results.
- Learn a domain rule from examples, then apply it in a different held-out domain.
- Carry a stated constraint through a long dependency chain where violating it only surfaces at the end.

Graded from resulting files, observed tool traces and tests. **Chat text is never evidence** — this is already the v3 filework rule and it carries over unchanged.

Each mission also declares its control topology: reasoning-only, one tool-using agent, or orchestrator plus fixed workers. Results from those topologies are never pooled. Orchestration-specific missions follow X11 and use the same worker roster and permissions for every candidate.

## X6 — Horizon, Measured in Structure Not Minutes

Adopted in direction, unit corrected. The suggestion proposes 5–10 minute, then 20–40 minute tasks.

**Wall-clock is the wrong difficulty dial.** A "20-minute task" measures the provider's latency, not the task's difficulty; the same task is 4 minutes on one model and 25 on another. The frozen envelope therefore uses one fixed 600-second timeout only as a hang guard and classifies timeout operationally rather than as factual capability. Importing minute-based difficulty tiers here would contradict that frozen decision.

Express horizon structurally instead:

- number of turns per trajectory (current maximum is 4; target 10–30)
- dependency depth before a result is checkable
- number of checkpoints the model must resume across
- **distance between cause and symptom** — an error introduced early that only surfaces much later

The last one is the real frontier discriminator and the one short prompts cannot test at all. Delayed-resume trajectories are already mechanically possible: spawned sessions are stateful and re-enterable via `sessions_send`, with the model override retained.

Long-horizon cases must require durable checkpoint state outside chat, resume from a fresh turn, distinguish verified from merely claimed progress, and survive one injected interruption or stale checkpoint. Grade constraint retention, checkpoint truthfulness, recovery choice and final artifact state separately. Context-window size is metadata, not credit; only retained and correctly applied task state earns a pass.

## X7 — Scoring Dimensions and Item Discrimination

The envelope scores four dimensions. Adopt three more from the suggestion, reported separately and never blended into one leaderboard number:

- scope and change discipline (did it edit beyond what was asked)
- evidence and citation completeness
- tool efficiency and recovery

Add the agentic dimensions the current envelope still lacks, also reported separately:

- planning and decomposition quality, scored against required dependencies rather than plan eloquence
- observation grounding (did later actions incorporate actual tool results rather than the expected result)
- dynamic replanning after error, contradiction or new evidence
- verification and termination discipline (tests/readback/receipts, then stop without false completion)
- durable state and resume correctness across checkpoints
- authority and escalation control, including asking for a real owner decision only when the task crosses a declared gate
- orchestration quality for X11 only: assignment fit, handoff completeness, collision avoidance, conflict resolution and integration verification

Two rules worth stating explicitly, both from the suggestion and both correct:

- A model producing correct prose while failing to modify the artifact **fails task completion**.
- A model reaching the right answer through prohibited actions **fails boundaries**, regardless of correctness.

Separately, track per-item pass rates across every model ever run and retire items that stop distinguishing. Report reliability as pass^k, not single-run pass. This is what keeps the instrument alive across roster changes instead of forcing a rebuild each time a set saturates.

Use matched candidate comparisons on identical hidden instances. Preserve task-family clustering when reporting intervals or consistency; generated variants of one structure are not independent breadth. Do not preselect only T1/T4/T5 from the headline score. Current evidence shows dimension-specific separation in T1, T2, T4 and T5, while T3 and T6 are valuable regression/breadth controls; X0 must attach the exact per-case/per-dimension evidence before X2/X3 expansion priorities are frozen. Do not turn 25–50 renamings of a few structures into a claim of general agentic reliability.

## X8 — Contamination Control

Mostly existing doctrine; two items are new and adopted:

- **Rotate private fixtures.** A fixture used repeatedly against the same roster loses value even without leaking.
- **Promote escaped real failures into sanitized regression cases.** Real defects are better fixtures than invented ones.

Standing rules that carry over unchanged: keys and hidden tests stay outside candidate workspaces; candidates never see peer responses or grader internals; any publicly exposed case is labelled regression-only; original failures are preserved and replacements explicitly labelled.

## X9 — Progressive Gating

Adopted. Valuable even with cost tracking out of scope, because wall-clock and review attention are still finite.

1. Smoke gate
2. Six-family comparison (`arena-six-20260919`)
3. Hidden breadth bank (X2)
4. Frontier and adversarial cases
5. Integrated cross-family missions (X5)
6. Long-horizon continuity and delayed-resume missions (X6)
7. Actual-role canary before any routing decision

A model that fails an earlier gate does not consume a later one. Gate 3 cannot run until the initial X2 bank has passed its oracle/calibration exit gate. Gate 7 is mandatory before any routing decision — bench performance has never been sufficient evidence for a role change.

## X10 — Model, Agent and Harness Attribution

Every result belongs to exactly one execution lane:

1. **Reasoning-only:** no tools; measures task reasoning and contract compliance.
2. **Single-agent tool use:** one candidate controls a fixed tool surface; measures execution, recovery and artifact completion.
3. **Orchestrated execution:** one candidate is the orchestrator over fixed workers; measures delegation and integration rather than worker-model quality.

Record requested and effective model, provider, checkpoint, requested effort, provider-native effort mapping when exposed, bootstrap, tool schema, sandbox, worker roster and harness version. A common OpenClaw setting such as `thinking=high` is a matched request, not proof that providers supplied equal internal computation. Unsupported or materially different effort mappings are disclosed and never silently pooled.

Attribute failures to candidate reasoning, candidate action, fixed worker, transport, harness, evaluator or unresolved cause. A worker or harness fault does not become an orchestrator capability failure without evidence; an orchestrator's bad assignment or failure to recover from an exposed worker fault does.

## X11 — Multi-Agent Orchestration and Delegation

Add a dedicated orchestration suite after X4 artifact grading is proven. Keep the worker side constant across candidate orchestrators: identical worker models or deterministic specialist stubs, identical tools, fixed permissions, fixed context packets and fixed child/turn/tool budgets. Candidate-specific workers would confound orchestrator quality with worker quality.

Test whether the orchestrator can:

- decompose a dependency graph and assign work to the right specialist
- choose sequential versus parallel execution without creating write collisions
- issue complete, bounded handoffs with acceptance criteria and stop lines
- detect missing, conflicting or fabricated worker evidence
- reassign or narrow work after a worker failure without retry-until-pass
- integrate outputs, run independent verification and preserve unresolved blockers
- stop at owner, authority or external-action gates instead of manufacturing approval
- produce one truthful final artifact whose claims trace to worker and tool evidence

Score delegation decisions, handoff sufficiency, observed worker outcomes, integration correctness, verification and boundary compliance separately. A correct answer produced by accidental worker overlap does not pass orchestration discipline. Open-ended self-spawning, recursive replication and unbounded autonomy are not benchmark targets.

## X12 — External Agentic Evidence Registry and Specialization Reports

Maintain a source-backed registry for external **agentic** benchmarks only: terminal/repository execution, automation, tool use and recovery, long-horizon knowledge work, long-context task reliability, code/change execution and multi-agent orchestration. Exclude multimodal, PDF-rendering, image, video, audio and GUI-perception scores from this arena plan.

Each external record includes exact model/checkpoint, benchmark and evaluator version, independent versus vendor-reported provenance, source URL, publication/access date, reasoning/effort setting, tool mode, context/runtime conditions, score and denominator. Preserve dated snapshots or source hashes when licensing permits. Unverified copied tables stay `unverified_external_claim`, never accepted evidence.

External scores are triangulation, not pooled with internal grades. Produce model specialization cards that keep four layers separate: external agentic evidence, internal synthetic cases, integrated missions and actual-role canaries. Wording such as "cleaner output discipline" remains workspace-specific unless replicated by a directly comparable external instrument.

## Sequencing

1. **X0** — finish the six-family discrimination map from the accepted three-model evidence.
2. **X10 attribution + X7 scoring** — freeze lanes, effort reporting and agentic dimensions before generating more results.
3. **X1 tiers + X9 gating** — freeze the gate contract before building inputs for it.
4. **X3 generators + initial X2 bank** — generators provide volume and the bank provides structural breadth; Gate 3 stays closed until the bank's exit gate passes.
5. **X7 discrimination tracking** — apply the frozen dimensions to generated and bank items before candidate use.
6. **X4 sandbox tool depth** — required before artifact-graded missions or orchestration.
7. **X11 orchestration**, then **X5 integrated missions** — fixed workers first; integrated claims second.
8. **X6 long horizon** — follows integrated missions and precedes any actual-role canary.
9. **X12 external agentic registry** — may proceed in parallel because it cannot change internal grades.
10. **X2 bank continuation** — ongoing background work after its initial gate, paced by oracle-review throughput.

## Owner Decisions Required

One remains:

- Confirm whether the adversarial axis gates enrollment outright or is only reported.

Closed on 2026-09-19:

- **Candidate enrollment is open.** Verified against `data/evals/model-arena/arena-six-20260919/envelope.json`: the envelope does not cap how many models run it. The two-slot cap was carried over mechanically from the initial 24-trajectory proposal and was never methodologically load-bearing — it limited what the instrument could answer without making any answer more valid. The only gate is dispatch proof that the model that ran is the model requested.
- **Budgets are a fixed 600s per-turn operational timeout**, identical for every candidate, classified as operational rather than capability. The earlier derivation rule was keyed to the slowest nominated candidate, which becomes undefined under open enrollment and would mutate whenever a slower model joined — retroactively altering conditions for candidates already run.
- **Pricing and cost accounting are out of scope.** If that ever changes it is an input to gating, never the objective.

## Stop Conditions

- Any expansion item that would modify, merge or re-baseline a historical score set.
- Any generator or variant whose instances cannot be property-verified or calibrated.
- Any fixture entering candidate use without an independent oracle pass.
- Any change to the frozen `arena-six-20260919` envelope; a harder version is a new envelope that supersedes it explicitly, never an edit.
- Any orchestrator comparison where worker models, permissions, tools or budgets differ by candidate.
- Any result that cannot separate candidate, worker, transport, harness and evaluator failure classes.
- Any pooling of materially different provider effort mappings without explicit comparability evidence.
- Any external benchmark number without a traceable source, version, date, model identity and denominator.

## Non-Goals

- No automatic launch and no model promotion from any of this.
- No accounting or cost-optimization build; economics are optional owner-supplied inputs, not the objective.
- No case-count quota that outruns oracle-review capacity.
- No AGI claim. The generalization and induction families are capability proxies only, and no score here certifies general intelligence.
- No PDF, image, video, audio, GUI-perception or other multimodal benchmark lane.
- No single composite "intelligence index" that hides tool, reasoning, orchestration, reliability or boundary failures.
- No open-ended autonomy, recursive spawning, self-replication or production-side external action.
