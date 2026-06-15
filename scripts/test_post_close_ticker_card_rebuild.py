from chain_manifest import manifest_steps
from finance_ticker_card_refresh_gate import build_commands
from pathlib import Path


def main() -> int:
    steps = manifest_steps("post-close")
    order = [step["script"] for step in steps]
    errors: list[str] = []

    required = [
        "post_close_final_quote_ledger.py",
        "ticker_card_freshness_owner_runner.py",
        "wf78_capital_review_queue.py",
        "finance_decision_factory.py",
        "wf78_tier_weighted_freshness_resolver.py",
        "artifact_index.py",
    ]
    positions = {}
    for script in required:
        try:
            positions[script] = order.index(script)
        except ValueError:
            errors.append(f"missing post-close step: {script}")

    if not errors:
        quote_pos = positions["post_close_final_quote_ledger.py"]
        card_pos = positions["ticker_card_freshness_owner_runner.py"]
        if not quote_pos < card_pos:
            errors.append("ticker-card rebuild must run after post-close final quote ledger")
        for script in (
            "wf78_capital_review_queue.py",
            "finance_decision_factory.py",
            "wf78_tier_weighted_freshness_resolver.py",
            "artifact_index.py",
        ):
            if not card_pos < positions[script]:
                errors.append(f"ticker-card rebuild must run before {script}")

    by_script = {step["script"]: step for step in steps}
    card_step = by_script.get("ticker_card_freshness_owner_runner.py", {})
    if "--skip-provider-refresh" not in card_step.get("args", []):
        errors.append("post-close ticker-card rebuild should reuse refreshed local evidence")
    if "post_close_final_quote_ledger.py" not in card_step.get("depends_on", []):
        errors.append("ticker-card rebuild must depend on post-close final quote ledger")

    for script in (
        "wf78_capital_review_queue.py",
        "finance_decision_factory.py",
        "wf78_tier_weighted_freshness_resolver.py",
    ):
        depends_on = by_script.get(script, {}).get("depends_on", [])
        if "ticker_card_freshness_owner_runner.py" not in depends_on:
            errors.append(f"{script} must depend on ticker-card freshness owner runner")

    refresh_commands = [" ".join(command) for command in build_commands(True, card_summary=Path("tmp/test-card-summary.json"))]
    card_build_index = next((idx for idx, command in enumerate(refresh_commands) if "ticker_intelligence_card.py" in command), None)
    price_bridge_indices = [idx for idx, command in enumerate(refresh_commands) if "wf77_price_freshness_bridge.py" in command]
    if card_build_index is None:
        errors.append("ticker-card refresh gate is missing ticker_intelligence_card.py")
    elif not any(idx > card_build_index for idx in price_bridge_indices):
        errors.append("ticker-card refresh gate must refresh WF77 price-state after card rebuild")

    if errors:
        print("post-close ticker-card rebuild test failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("post-close ticker-card rebuild test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
