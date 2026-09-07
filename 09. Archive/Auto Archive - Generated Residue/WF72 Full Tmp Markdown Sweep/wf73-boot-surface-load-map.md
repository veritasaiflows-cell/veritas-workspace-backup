# WF73 Boot Surface Load Map

Status: `review_only` / review-only. No target files edited.

## Authority flags

- `review_only`: `True`
- `core_boot_files_edited`: `False`
- `active_workflows_edited`: `False`
- `startup_truth_index_edited`: `False`
- `new_durable_control_surface_created`: `False`
- `destructive_cleanup_allowed`: `False`
- `config_auth_channel_service_mutation_allowed`: `False`
- `canonical_note_mutation_allowed`: `False`
- `portfolio_mutation_allowed`: `False`
- `trade_or_account_action_allowed`: `False`
- `paper_execution_authorized_by_this_artifact`: `False`
- `owner_approval_inferred`: `False`

## Reuse-before-new-surface gate

- **decision:** Reuse and rewrite Startup Truth Index and Active Workflows rather than creating a third durable boot/control-plane file.
- **rationale:** `["Startup Truth Index already owns startup routing and post-compaction pickup.", "Active Workflows already owns live workflow status and queue truth.", "WF71 department ownership and WF72 script ownership artifacts can feed indexes inside those existing surfaces instead of becoming new canon."]`
- **proposed_new_surfaces:** `[]`

## Boot load tiers

### T0_doctrine_identity_runtime

- **tier:** T0_doctrine_identity_runtime
- **load_posture:** always_load_or_confirm_present_before_real_work
- **files:** `[{"path": "SOUL.md", "purpose": "Identity, mission, hard finance/safety boundaries.", "load_budget": "thin; full read acceptable because it is the constitution", "stop_if_conflict": "SOUL wins for identity/boundary conflicts."}, {"path": "AGENTS.md", "purpose": "Startup, orchestration, action boundaries, response shape.", "load_budget": "thin/core sections; read when not already injected or after compaction", "stop_if_conflict": "Do not reconstruct helper-lane or startup rules from memory."}, {"path": "USER.md", "purpose": "Randall preferences and standing finance boundaries.", "load_budget": "thin; full read acceptable", "stop_if_conflict": "Owner preferences do not override SOUL hard boundaries."}, {"path": "TOOLS.md", "purpose": "Workspace/runtime/tool posture and Windows constraints.", "load_budget": "thin; exact sections for config/runtime/PowerShell when relevant", "stop_if_conflict": "Ask before config/auth/channel/service/runtime mutation outside approved gates."}]`

### T1_session_orientation

- **tier:** T1_session_orientation
- **load_posture:** always_load_for_direct_main_or_after_compaction
- **files:** `[{"path": "06. Playbooks/Startup Truth Index.md", "purpose": "Thin routing map to avoid broad vault reads.", "load_budget": "always; should stay short enough for one read", "route_after_read": "Use this to choose owner notes/artifacts, not to replace them."}, {"path": "06. Playbooks/Active Workflows.md", "purpose": "Authoritative live workflow status and queue control surface.", "load_budget": "always; proposal should compress to top snapshot plus compact register", "route_after_read": "Drill only into current workflow continuity note and exact proof artifacts."}, {"path": "memory/YYYY-MM-DD.md and previous day", "purpose": "Latest material deltas, repair/proof outcomes, active blockers.", "load_budget": "targeted recent section/read via search first", "route_after_read": "Promote durable decisions only through memory-continuity rules."}, {"path": "MEMORY.md", "purpose": "Durable preferences, decisions, finance authority posture.", "load_budget": "direct main sessions and prior-work/date/decision questions; use search/excerpt when possible", "route_after_read": "Do not treat MEMORY as live state when Active Workflows/owner notes disagree."}]`

### T2_task_routed_control_files

- **tier:** T2_task_routed_control_files
- **load_posture:** route_by_task_only
- **files:** `[{"path": "HEARTBEAT.md", "when_to_load": "Heartbeat poll or heartbeat behavior question only.", "avoid_by_default_because": "Heartbeat is not normal workflow advancement."}, {"path": "06. Playbooks/Automation Orchestration Protocol.md", "when_to_load": "Substantial workflow advancement, implementation, audit, broad inspection, helper-lane spawning, or proof-heavy validation.", "avoid_by_default_because": "Not needed for simple direct answers."}, {"path": "06. Playbooks/Spawn and Closeout Governance Matrix.md", "when_to_load": "Spawning helpers, independent QA, or closeout risk decisions.", "avoid_by_default_because": "Main can do bounded one-step work without extra orchestration overhead."}, {"path": "06. Playbooks/Subagent Spawn Handoff Template.md", "when_to_load": "Only when drafting a helper handoff.", "avoid_by_default_because": "Do not load template when no spawn is planned."}, {"path": "06. Playbooks/Obsidian CLI Runtime Note.md", "when_to_load": "Note-layer/Obsidian CLI behavior matters.", "avoid_by_default_because": "Most finance/queue work does not need CLI details."}]`

### T3_owner_notes_and_proof

- **tier:** T3_owner_notes_and_proof
- **load_posture:** route_by_workflow_or_question
- **files:** `[{"path": "06. Playbooks/Project Continuity/<current workflow>.md", "when_to_load": "Continuing a named workflow or changing its status.", "proof_link_rule": "Continuity note points to proof; proof artifacts remain in tmp unless promoted."}, {"path": "03. Portfolio/Execution Board.md", "when_to_load": "Ticker action state, bands, stops, repair/no-chase, deployment status.", "proof_link_rule": "Canonical owner note wins over dashboards; generated packets support only."}, {"path": "03. Portfolio/Portfolio Snapshot.md", "when_to_load": "Portfolio posture/model weights/exposure.", "proof_link_rule": "Do not infer cash/sizing/sleeve changes without gated apply proof."}, {"path": "04. Research/Coverage and Watchlist.md", "when_to_load": "Universe/thesis/watchlist membership.", "proof_link_rule": "Generated research packets do not promote tickers by themselves."}, {"path": "tmp/current-window-artifacts.json", "when_to_load": "Need current proof inventory or latest run artifacts.", "proof_link_rule": "Index only; inspect target artifact before claiming content."}]`


## Proposed main-session boot path

- Confirm T0 doctrine/runtime surfaces are present or read them.
- Read Startup Truth Index for routing.
- Read compact Active Workflows top snapshot and current workflow row only after compression is applied.
- Search/read today's and yesterday's daily memory for material deltas.
- Read MEMORY.md only for direct main startup or prior-decision questions; otherwise use targeted memory search.
- Load exact continuity notes/proof artifacts for the current task; do not reread the full finance stack by habit.

## Department/skill route sources

### tmp/wf71-department-skill-ownership-proposal.json

- **source:** tmp/wf71-department-skill-ownership-proposal.json
- **proposed_home_after_review:** Startup Truth Index compact routing table or IC Project Registry thin owner/lane index
- **do_not_duplicate:** Do not create another staff registry unless WF71 is formally applied.


## Script ownership route sources

### tmp/wf72-script-ownership-inventory.json

- **source:** tmp/wf72-script-ownership-inventory.json
- **summary:** 633 scripts files classified; high-authority finance/paper/canon surfaces are no-delete/gated-review.
- **proposed_home_after_review:** Startup Truth Index pointer plus WF72 continuity note; not a new durable index unless a validator needs it.


## Proof link preservation rules

- Never replace proof artifact paths with prose-only summaries.
- Active Workflows compressed rows must preserve continuity note link plus 2-5 primary proof links.
- Startup Truth Index must point to current-window artifact index for generated proof lookup instead of enumerating every tmp artifact forever.
- Generated proof links do not become canonical truth or approval surfaces.
- Archive candidates require reference checks and owner approval before move/delete/archive.

## Global stop lines

- No identity/doctrine rewrite without proven stale/conflicting rule and review.
- No core boot-file edits from this artifact.
- No file move/delete/archive/rename without reference checks and explicit owner approval.
- No config/auth/channel/service/runtime mutation without explicit approval.
- No portfolio/canon/sizing/cash/risk/execution entitlement mutation from WF73 alone.
- No live/paper order, account action, money movement, or owner approval inference.
- No generated dashboard/report/proposal becomes canon or approval.

## Recommended next action

Main review these WF73 proposals, then if accepted apply low-risk text-only rewrites to Startup Truth Index and Active Workflows with a link-check/JSON proof pass.
