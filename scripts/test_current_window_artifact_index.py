from __future__ import annotations

from current_window_artifact_index import build_index


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    post_close = build_index("full")
    require(post_close["window"] == "post-close", "full alias should normalize to post-close")
    authority = post_close.get("authority", {})
    for field in (
        "artifact_mutation_allowed_by_this_index",
        "trade_execution_allowed",
        "paper_trade_submit_cancel_allowed_by_this_index",
        "generated_report_is_canonical",
    ):
        require(authority.get(field) is False, f"{field} must stay fail-closed")
    for field in (
        "canonical_mutation_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "deployment_state_mutation_allowed",
        "owner_approval_granted",
    ):
        require(authority.get(field) is True, f"{field} should mirror main-session standing maintenance scope")
    require(
        authority.get("standing_authority_scope") == "main_session_bounded_workspace_canon_portfolio_maintenance",
        "standing authority scope label must remain explicit",
    )
    require(post_close["rendered_outputs"]["json"] == "tmp/current-window-artifacts.json", "stable JSON output path required")
    roles = {item["role"] for item in post_close["artifacts"]}
    require("run_summary" in roles, "run_summary role should be indexed")
    require("full_portfolio_view" in roles, "post-close portfolio view should be indexed")
    require("capital_deployment_recommendations" in roles, "capital recommendation JSON role should be indexed")
    require("capital_deployment_recommendations_md" in roles, "capital recommendation Markdown role should be indexed")
    require("capital_deployment_recommendation_validation" in roles, "capital recommendation validator role should be indexed")
    require("goog_official_ir_capture" in roles, "official capture aliases should be indexed")
    require("goog_official_ir_capture_validation" in roles, "official capture validation aliases should be indexed")
    aliases = post_close.get("role_aliases", {})
    require(aliases.get("goog_official_ir_capture") == "tmp/official-ir-captures/goog-q1-2026.json", "GOOG alias should preserve current Q1 path")

    post_earnings = build_index("post-earnings")
    roles = {item["role"] for item in post_earnings["artifacts"]}
    require("post_earnings_prep" in roles, "post-earnings prep should be indexed")
    require("full_portfolio_view" not in roles, "post-earnings should not advertise non-produced portfolio view")
    print("current_window_artifact_index_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
