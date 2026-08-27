# Workspace Boundary and Root Entitlement Audit - 2026-07-05

Scope: root-boundary entitlement, data-surface documentation, cache cleanup posture, and boot/control surface size pressure.

Authority boundary: review-only. No archive, delete, move, rename, policy edit, config/auth/runtime change, finance/canon mutation, paper/live/account action, or external action was performed.

## Verdict

The workspace is usable, but the root is not clean yet.

This is mostly a governance and entitlement issue, not a large space-recovery issue. The live root has several surfaces that appear legitimate or historically useful, but the policy, validator allowlist, and live root do not fully agree.

Immediate cleanup value is low. The only currently obvious cleanup-class items are runtime caches.

## Evidence

| Check | Result | Meaning |
|---|---:|---|
| `workspace_boundary_check.py` | warning, 20 findings, 16 warnings, 4 info | Root/data/tmp/script debris review still sees boundary drift. |
| `workspace_governance_truth_check.py --write` | ok, 0 warnings, 0 critical | Core governance truth checks are not red. |
| `archive_suggester.py --write-md` | review_required, 2 suggestions | Only `scripts/__pycache__/` and `scripts/lib/__pycache__/` are suggested by the archive route. |
| `boot_surface_size_guard.py --write --validate` | blocked | Startup Truth Index is over the hard size ceiling. |

Boot guard detail: `06. Playbooks/Startup Truth Index.md` is 18,648 bytes against an 18,000-byte hard failure ceiling. Warnings also hit `AGENTS.md`, `TOOLS.md`, `MEMORY.md`, `06. Playbooks/Active Workflows.md`, `06. Playbooks/Startup Truth Index.md`, and `06. Playbooks/Automation Orchestration Protocol.md`.

## Findings

| Surface | Size | Classification | Finding | Recommendation |
|---|---:|---|---|---|
| `08. Audit and Governance/` | 39,080 bytes | Legacy duplicate audit root | Two old audit files remain outside the active `08. Audits/` route. At least one state ledger still references a file there. | Reference-review, then prepare an archive-or-promote packet. Do not move blindly. |
| `Audit/` | 21,548 bytes | Legacy duplicate audit root | Two old June audit/planning files remain in an unnumbered root. | Reference-review, then archive into `09. Archive/` or promote into `08. Audits/` with approval. |
| `10. Deliverables/` | 5,593,637 bytes | Active but underdocumented | `Home.md` and `01. Dashboards/Executive Brief.md` route human deliverables here, but current root standards list only `01` through `09`. | Decide whether it is a permanent root domain. If yes, update standards and validators. If no, migrate by packet. |
| `node_modules/` | 20,633,498 bytes | Dev dependency cache/local tooling | Supports root `package.json` local-only training QA dependencies. | Keep until QA dependency posture is decided. Rebuildable, but do not delete without a cache/dependency packet. |
| `package.json` / `package-lock.json` | 2,954 bytes | Root tooling manifest/lockfile | Local-only Playwright/axe QA dependency route for interactive training assets. | Document root entitlement or relocate with the training/tooling surface. |
| `requirements-dev.txt` | 51 bytes | Dev dependency manifest | Holds pytest dev/test dependency. | Document entitlement or move to dependency governance. Do not delete while pytest is expected. |
| `schemas/` | 4,710 bytes | Durable schema surface | Contains `interactive_training_module.schema.json`. | Likely legitimate; document root entitlement or move under `training/` after reference review. |
| `tests/` | 1,727 bytes | Root test surface | Contains `test_chain_manifest_incremental_contract.py`. | Decide whether root `tests/` is approved, or move into the existing scripts/test convention with validator updates. |
| `wiki/` | 20,740 bytes | Policy/validator mismatch | Workspace standards explicitly allow `wiki/`, but `workspace_boundary_check.py` still warns on it. | Patch validator allowlist or policy source of truth in a separate governance-fix lane. |
| `DREAMS.md` | 35,439 bytes | Bootstrap/reference policy mismatch | User has treated it as read-only bootstrap/reference material, but boundary checker does not allowlist it. | Do not edit content. Decide whether to add a root exception/allowlist row. |
| `openclaw-workspace-state.json` | 120 bytes | OpenClaw runtime bootstrap state | Small setup state file. | Treat as runtime-owned unless proven otherwise; document exception instead of moving/deleting. |
| `data/vector-memory-sources.json` | 18,178 bytes | Durable derived data | Actively referenced by vector-memory and checkpoint routes; includes its own authority boundary. | Keep. Add data README coverage so validator stops treating it as undocumented. |
| `data/wf74-learning-loop-evals/` | 16,266 bytes | Durable derived data | Referenced by WF74/WF88 eval/checkpoint routes. | Keep. Add README with producer, authority, proof, and retention posture. |
| `data/workflow-checkpoints/` | 13,579 bytes | Durable derived data | Referenced by workflow checkpoint runner and vector-memory source registry. | Keep. Add README with producer, authority, proof, and retention posture. |
| `.pytest_cache/` | 1,020 bytes | Runtime cache | Rebuildable pytest cache. | Cleanup candidate after exact approval, but negligible space recovery. |
| `scripts/__pycache__/` | 2,254,316 bytes | Runtime cache | Rebuildable Python bytecode cache. | Cleanup candidate after exact approval. |
| `scripts/lib/__pycache__/` | 20,357 bytes | Runtime cache | Rebuildable Python bytecode cache. | Cleanup candidate after exact approval. |

## Recommendations

1. Patch the policy/validator mismatch for `wiki/` and `DREAMS.md`.
2. Prepare a reference-reviewed archive/promote packet for `08. Audit and Governance/` and `Audit/`.
3. Make an explicit root entitlement decision for `10. Deliverables/`.
4. Add README authority boundaries for `data/vector-memory-sources.json`, `data/wf74-learning-loop-evals/`, and `data/workflow-checkpoints/`.
5. Prepare an exact cache cleanup packet for `.pytest_cache/` and Python `__pycache__/` caches.
6. Run a boot-surface compaction pass; `Startup Truth Index` is now a hard failure under the size guard.

## Stop Lines

- Do not blind-delete `node_modules/`, package manifests, schemas, tests, deliverables, wiki, DREAMS, OpenClaw state, or data-derived surfaces.
- Do not archive legacy audit roots until references are reviewed.
- Do not edit bootstrap/reference files as part of cleanup without explicit scope.
- Do not treat generated packets as authority to mutate finance/canon, portfolio, paper/live, account, credentials, config, network, or runtime surfaces.
