"""Shared missing-usage classification constants (WF88 RSI streamlining, Phase 2).

Created 2026-09-18 under Randall's owner direction to collapse three divergent
literal copies of ACCEPTED_MISSING_USAGE_CLASSIFICATIONS into one module, so future
divergence is impossible by omission. Per-consumer membership is preserved
byte-for-byte; semantic unification is a separate open decision recorded in
"06. Playbooks/Project Continuity/Workflow 88 - Veritas OS 2.0.md".

Known divergence (deliberately preserved here, NOT adjudicated):

- CLOSEOUT_GATE_* (concurrent_lane_manager): the strict lane-closeout gate.
  Excludes manual_runtime_unavailable and self_declared_usage_rejected so no future
  lane can close on self-declared or manual totals. Includes
  isolated_session_usage_unavailable.

- BRIDGE_* (implementation_token_attribution_bridge): historical claim-limit
  classifier. Includes manual_runtime_unavailable and self_declared_usage_rejected
  (pre-cutover lanes that closed on self-declared totals are named and rejected,
  not silently accepted). Excludes isolated_session_usage_unavailable.

- FRONTIER_* (frontier_capability_eval_spine): fixture JSON-schema enum. Includes
  manual_runtime_unavailable; excludes isolated_session_usage_unavailable and
  self_declared_usage_rejected (the bridge added self_declared_usage_rejected after
  the spine froze).

Open question for owner/Phase 3: should all three converge on CANONICAL, with only
the closeout gate remaining narrower? Deferred - behavior-preserving collapse first.

All tuples are sorted alphabetically so list()/enum serialization is deterministic.
"""

CANONICAL_MISSING_USAGE_CLASSIFICATIONS = (
    "current_chat_runtime_unavailable",
    "historical_pre_token_closeout_guard_unavailable",
    "historical_pre_token_stamping_unavailable",
    "isolated_session_usage_unavailable",
    "manual_runtime_unavailable",
    "provider_usage_unavailable",
    "runtime_usage_unavailable",
    "self_declared_usage_rejected",
    "unsupported_legacy_model_route",
)

CLOSEOUT_GATE_MISSING_USAGE_CLASSIFICATIONS = (
    "current_chat_runtime_unavailable",
    "historical_pre_token_closeout_guard_unavailable",
    "historical_pre_token_stamping_unavailable",
    "isolated_session_usage_unavailable",
    "provider_usage_unavailable",
    "runtime_usage_unavailable",
    "unsupported_legacy_model_route",
)

BRIDGE_ACCEPTED_MISSING_USAGE_CLASSIFICATIONS = (
    "current_chat_runtime_unavailable",
    "historical_pre_token_closeout_guard_unavailable",
    "historical_pre_token_stamping_unavailable",
    "manual_runtime_unavailable",
    "provider_usage_unavailable",
    "runtime_usage_unavailable",
    "self_declared_usage_rejected",
    "unsupported_legacy_model_route",
)

FRONTIER_ACCEPTED_MISSING_USAGE_CLASSIFICATIONS = (
    "current_chat_runtime_unavailable",
    "historical_pre_token_closeout_guard_unavailable",
    "historical_pre_token_stamping_unavailable",
    "manual_runtime_unavailable",
    "provider_usage_unavailable",
    "runtime_usage_unavailable",
    "unsupported_legacy_model_route",
)
