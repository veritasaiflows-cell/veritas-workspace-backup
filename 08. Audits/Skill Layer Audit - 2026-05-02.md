# Skill Layer Audit - 2026-05-02

## Scope
Bounded read-heavy audit of the active workspace `skills/` layer for overlap, drift, boundary clarity, naming quality, stale/incomplete surfaces, and near-term hardening opportunities.

Out of scope: editing skill files, config/auth/network changes, folder reorganization, and canonical finance-note edits.

## Evidence checked
### Governance and operating context
- `TOOLS.md`
- `06. Playbooks/Notes Layer Governance Protocol.md`
- `06. Playbooks/Workspace Structure Protocol.md`
- `06. Playbooks/Notes Layer Audit Checklist.md`

### Skill inventory and health
- `skills/` folder listing (workspace skills)
- Each workspace skill folder structure (`SKILL.md` and optional subfolders)
- `openclaw skills check` (live status)
  - Result: 26 eligible/ready, 0 missing requirements

### Skill content sampled/inspected directly
- Full reads of:
  - `skills/automation-hardening-manager/SKILL.md`
  - `skills/cron-automation-manager/SKILL.md`
  - `skills/openclaw-operator/SKILL.md`
  - `skills/openclaw-troubleshooter/SKILL.md`
  - `skills/project-continuity-manager/SKILL.md`
  - `skills/technical-chart-pass/SKILL.md`
  - `skills/veritas-technical-pass/SKILL.md`
  - `skills/veritas-weekly-brief/SKILL.md`
  - `skills/veritas-portfolio-update/SKILL.md`
  - `skills/veritas-positioning-pass/SKILL.md`
  - `skills/veritas-self-improvement/SKILL.md`
  - `skills/workspace-governor/SKILL.md`
  - `skills/workspace-qa-pass/SKILL.md`
- Structural checks across all workspace skills:
  - SKILL line counts
  - placeholder scan (`TODO`, `TBD`, template markers)
  - optional `references/` presence

## Findings

### 1) Overall coherence is strong
The layer is largely coherent and intentionally scoped:
- clear domain clusters (operator/runtime, continuity/automation governance, finance execution)
- strong trigger language in frontmatter descriptions
- no missing-requirements failures in live check
- skill files are mostly concise and under the recommended context budget

### 2) Primary overlap risk: `technical-chart-pass` vs `veritas-technical-pass`
These two skills are very close in objective and output shape (levels, MA posture, entries, stops, readiness/state), creating avoidable trigger ambiguity.

- `veritas-technical-pass` is the clearly richer, workspace-integrated, stateful variant (Deployable/Blocked/Repair mode/Watch-only + board context + portfolio linkage).
- `technical-chart-pass` appears as a generic parallel path and can split behavior standards for similar prompts.

Assessment: this is the highest-value cleanup target.

### 3) Secondary overlap cluster is manageable but should be explicitly precedence-ordered
Potentially adjacent scopes:
- `openclaw-operator` (maintenance/hardening)
- `openclaw-troubleshooter` (incident diagnosis)
- `workspace-governor` (structure organization)
- `workspace-qa-pass` (post-change independent QA)

Current docs do differentiate these, but operationally there is still a mild chance of lane collision when prompts are vague ("audit/clean/fix workspace").

Assessment: boundary quality is good; precedence signaling can be tightened.

### 4) Minor stale/hygiene signals
- `skills/technical-chart-pass/references/` exists but is empty.
- `project-continuity-manager` includes `<Project Name>` template marker (intentional in template block, low risk).

No critical stale/incomplete skill folders found.

### 5) Skills vs playbooks vs scripts boundary is generally clear
From protocol files and skill text, ownership is consistent:
- playbooks define governance and routing doctrine
- skills define repeatable execution patterns
- scripts execute deterministic generation/validation
- `tmp/` remains generated surface; canonical notes remain authority

This is aligned with current notes-layer governance hardening.

## Concrete risks
1. **Trigger ambiguity risk (medium):** parallel technical-pass skills can yield inconsistent readiness language and board-state semantics across runs.
2. **Operator-lane collision risk (low/medium):** without explicit precedence guidance, similar prompts can route to operator/governor/QA skills inconsistently.
3. **Hygiene drift risk (low):** empty resource folders and parallel near-duplicate skills can accumulate and weaken layer clarity over time.

## Strengths
- Strong live health posture (`skills check` clean)
- Clear governance doctrine in playbooks and TOOLS posture
- Good use of explicit workflow gates, trust language, and verification steps in major finance workflow skills
- Mostly bounded skill sizes with practical structure and explicit “do not” constraints

## Prioritized recommendations

### P1 (near-term): Resolve technical-pass duplication
Choose one of:
1. **Recommended:** keep `veritas-technical-pass` as canonical and tighten `technical-chart-pass` into a lightweight non-Veritas/general-market fallback with explicit “not for Veritas board sync” language; or
2. Merge/archive `technical-chart-pass` if no separate use case remains.

Goal: one unambiguous path for Veritas technical state decisions.

### P2 (near-term): Add explicit precedence note across operator/governor/QA/troubleshooter
In the relevant skills (or one shared governance note), add quick routing precedence such as:
- broken behavior -> troubleshooter
- architecture/maintenance change -> operator
- structure/file-placement cleanup -> workspace-governor
- post-change independent audit -> workspace-qa-pass

Goal: reduce lane collisions on vague prompts.

### P3 (hygiene): Remove or populate empty skill resource directories
If `technical-chart-pass/references/` has no planned content, remove it at next maintenance pass; otherwise add a targeted reference and link it from SKILL.md.

### P4 (quality guard): Add periodic skill-layer QA checkpoint
Include a lightweight monthly/major-change check in audit cadence:
- duplicate-trigger scan
- stale folder scan
- skill count/change log
- boundary drift check against playbook governance

## Verdict
The workspace skill layer is coherent enough for current operation and does **not** require emergency refactor. It does need near-term cleanup for one meaningful duplication (`technical-chart-pass` vs `veritas-technical-pass`) and a small boundary-precedence tightening pass across the operator/governor/QA/troubleshooter cluster.