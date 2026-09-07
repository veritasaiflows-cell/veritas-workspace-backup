from pathlib import Path

p = Path('scripts/test_dashboard_acceptance.py')
s = p.read_text(encoding='utf-8')

repls = []
repls.append((r'''        research = json.loads(original_research or "{}")
        rows = [row for row in research.get("candidate_reviews", []) if row.get("ticker") != "ETN"]
        rows.append({
            "ticker": "ETN",
            "queue_judgment": "stale prose says trigger not live despite machine green",
            "blocking_gate": "approval-on-hold / review-only",
            "next_action": "Sync stale prose; do not infer owner approval or execution authority",
            "below_stop_or_repair": False,
            "blocked_reasons": ["review-only owner hold"],
            "monitoring_flags": [],
        })
        research["candidate_reviews"] = rows
        research_path.write_text(json.dumps(research, indent=2), encoding="utf-8")
        deployment_readiness_surface.main()
        generic_surface = read_json(TMP / "deployment-readiness-surface.json")
        generic_groups = generic_surface.get("groups") or {}
        generic_deployable = {row.get("ticker") for row in generic_groups.get("DEPLOYABLE NOW") or []}
        etn_conflict = [row for row in generic_groups.get("AUTHORITY CONFLICT") or [] if row.get("ticker") == "ETN"]
        expect("ETN" in generic_deployable, f"machine-green ETN should remain DEPLOYABLE NOW despite stale prose, got {sorted(generic_deployable)}", errors)
        expect(not etn_conflict, f"stale prose alone must not move ETN to AUTHORITY CONFLICT, got {generic_groups.get('AUTHORITY CONFLICT')}", errors)
''', r'''        # Capture the machine-owned ETN bucket first. This case verifies that stale
        # research prose does not demote the current machine state into AUTHORITY
        # CONFLICT; it must not freeze a historical ETN deployable-now expectation
        # after price has legitimately moved above band/no-chase.
        baseline_surface = read_json(TMP / "deployment-readiness-surface.json")
        baseline_groups = baseline_surface.get("groups") or {}
        baseline_etn_bucket = next((
            bucket for bucket, rows_for_bucket in baseline_groups.items()
            if any(row.get("ticker") == "ETN" for row in (rows_for_bucket or []))
        ), None)

        research = json.loads(original_research or "{}")
        rows = [row for row in research.get("candidate_reviews", []) if row.get("ticker") != "ETN"]
        rows.append({
            "ticker": "ETN",
            "queue_judgment": "stale prose says trigger not live despite current machine state",
            "blocking_gate": "approval-on-hold / review-only",
            "next_action": "Sync stale prose; do not infer owner approval or execution authority",
            "below_stop_or_repair": False,
            "blocked_reasons": ["review-only owner hold"],
            "monitoring_flags": [],
        })
        research["candidate_reviews"] = rows
        research_path.write_text(json.dumps(research, indent=2), encoding="utf-8")
        deployment_readiness_surface.main()
        generic_surface = read_json(TMP / "deployment-readiness-surface.json")
        generic_groups = generic_surface.get("groups") or {}
        generic_etn_bucket = next((
            bucket for bucket, rows_for_bucket in generic_groups.items()
            if any(row.get("ticker") == "ETN" for row in (rows_for_bucket or []))
        ), None)
        etn_conflict = [row for row in generic_groups.get("AUTHORITY CONFLICT") or [] if row.get("ticker") == "ETN"]
        expect(generic_etn_bucket == baseline_etn_bucket, f"stale prose should preserve ETN machine bucket {baseline_etn_bucket}, got {generic_etn_bucket}", errors)
        expect(not etn_conflict, f"stale prose alone must not move ETN to AUTHORITY CONFLICT, got {generic_groups.get('AUTHORITY CONFLICT')}", errors)
'''))
repls.append((r'''    expect(technical.get("ETN", {}).get("actionState") == "DEPLOYABLE NOW", "ETN technical state should reflect owner-promoted DEPLOYABLE NOW", errors)
    expect(deployment.get("ETN", {}).get("state") == "DEPLOYABLE", "ETN deployment state should reflect owner-promoted DEPLOYABLE", errors)
''', r'''    etn_technical = technical.get("ETN", {})
    etn_deployment = deployment.get("ETN", {})
    etn_in_band = etn_technical.get("inBand") is True
    if etn_in_band:
        expect(etn_technical.get("actionState") == "DEPLOYABLE NOW", f"ETN in-band owner-approved setup should be DEPLOYABLE NOW, got {etn_technical.get('actionState')}", errors)
        expect(etn_deployment.get("state") == "DEPLOYABLE", f"ETN in-band owner-approved setup should be DEPLOYABLE, got {etn_deployment.get('state')}", errors)
    else:
        expect(etn_technical.get("actionState") == "ALMOST DEPLOYABLE", f"ETN outside live band should stay ALMOST DEPLOYABLE / no-chase, got {etn_technical.get('actionState')}", errors)
        expect(etn_deployment.get("state") == "ALMOST", f"ETN outside live band should stay ALMOST / no-chase, got {etn_deployment.get('state')}", errors)
'''))
repls.append((r'''    actionable_alias = (payload.get("today_action") or {}).get("actionable") or []
    expect({card.get("ticker") for card in actionable_alias} == {"ETN"}, f"today_action.actionable alias should contain only clean deployable ETN, got {actionable_alias}", errors)
''', r'''    actionable_alias = (payload.get("today_action") or {}).get("actionable") or []
    expected_actionable = {"ETN"} if etn_in_band else set()
    expect({card.get("ticker") for card in actionable_alias} == expected_actionable, f"today_action.actionable alias should match clean deployable ETN state {expected_actionable}, got {actionable_alias}", errors)
'''))
repls.append((r'''    expect("ETN" in deployable_bucket, f"deployment_summary.deployable should include ETN, got {summary.get('deployable')}", errors)
''', r'''    if etn_in_band:
        expect("ETN" in deployable_bucket, f"deployment_summary.deployable should include in-band ETN, got {summary.get('deployable')}", errors)
        expect("ETN" not in almost_bucket, f"deployment_summary.almost should not include in-band ETN, got {summary.get('almost')}", errors)
    else:
        expect("ETN" not in deployable_bucket, f"deployment_summary.deployable should not include above-band/no-chase ETN, got {summary.get('deployable')}", errors)
        expect("ETN" in almost_bucket, f"deployment_summary.almost should include above-band/no-chase ETN, got {summary.get('almost')}", errors)
'''))
repls.append((r'''    expect(
        any(card.get("ticker") == "ETN" for card in (payload.get("today_action") or {}).get("deployable") or []),
        "today_action.deployable should render owner-promoted ETN separately from almost/promotion-review",
        errors,
    )
''', r'''    etn_deployable_cards = [card for card in (payload.get("today_action") or {}).get("deployable") or [] if card.get("ticker") == "ETN"]
    if etn_in_band:
        expect(len(etn_deployable_cards) == 1, f"today_action.deployable should render in-band ETN exactly once, got {etn_deployable_cards}", errors)
    else:
        expect(not etn_deployable_cards, f"today_action.deployable should not render above-band/no-chase ETN, got {etn_deployable_cards}", errors)
'''))
repls.append((r'''        research = json.loads(original_research or "{}")
        rows = research.setdefault("candidate_reviews", [])
        rows = [row for row in rows if row.get("ticker") != "ETN"]
        rows.append({
            "ticker": "ETN",
            "queue_judgment": "stale prose says trigger not live despite machine green",
            "blocking_gate": "approval-on-hold / review-only",
            "next_action": "Sync stale prose; do not infer owner approval or execution authority",
            "below_stop_or_repair": False,
            "blocked_reasons": ["review-only owner hold"],
            "monitoring_flags": [],
        })
        research["candidate_reviews"] = rows
        research_path.write_text(json.dumps(research, indent=2), encoding="utf-8")

        payload = build_payload(load_sources())
        technical = {row["ticker"]: row for row in payload.get("technical") or []}
        deployment = {row["ticker"]: row for row in payload.get("deployment_records") or []}
        deployable_cards = [card for card in (payload.get("today_action") or {}).get("deployable") or [] if card.get("ticker") == "ETN"]
        expect(technical.get("ETN", {}).get("actionState") == "DEPLOYABLE NOW", f"machine-green ETN should remain DEPLOYABLE NOW, got {technical.get('ETN')}", errors)
        expect(deployment.get("ETN", {}).get("state") == "DEPLOYABLE", f"ETN deployment state should stay machine-green/owner-gated, got {deployment.get('ETN')}", errors)
        expect("ETN" in ((payload.get("deployment_summary") or {}).get("deployable") or []), "ETN should remain in deployable summary when only stale prose conflicts", errors)
        expect(len(deployable_cards) == 1, f"ETN should render exactly one deployable card, got {deployable_cards}", errors)
        for card in deployable_cards:
            expect((card.get("reviewOnlyNoApplyArtifact") is True), f"ETN deployable card must remain review-only/no-apply, got {card}", errors)
''', r'''        baseline_payload = build_payload(load_sources())
        baseline_technical = {row["ticker"]: row for row in baseline_payload.get("technical") or []}
        baseline_deployment = {row["ticker"]: row for row in baseline_payload.get("deployment_records") or []}
        baseline_summary = baseline_payload.get("deployment_summary") or {}
        baseline_etn_action = baseline_technical.get("ETN", {}).get("actionState")
        baseline_etn_state = baseline_deployment.get("ETN", {}).get("state")
        baseline_etn_bucket = "deployable" if "ETN" in (baseline_summary.get("deployable") or []) else ("almost" if "ETN" in (baseline_summary.get("almost") or []) else None)

        research = json.loads(original_research or "{}")
        rows = research.setdefault("candidate_reviews", [])
        rows = [row for row in rows if row.get("ticker") != "ETN"]
        rows.append({
            "ticker": "ETN",
            "queue_judgment": "stale prose says trigger not live despite current machine state",
            "blocking_gate": "approval-on-hold / review-only",
            "next_action": "Sync stale prose; do not infer owner approval or execution authority",
            "below_stop_or_repair": False,
            "blocked_reasons": ["review-only owner hold"],
            "monitoring_flags": [],
        })
        research["candidate_reviews"] = rows
        research_path.write_text(json.dumps(research, indent=2), encoding="utf-8")

        payload = build_payload(load_sources())
        technical = {row["ticker"]: row for row in payload.get("technical") or []}
        deployment = {row["ticker"]: row for row in payload.get("deployment_records") or []}
        deployable_cards = [card for card in (payload.get("today_action") or {}).get("deployable") or [] if card.get("ticker") == "ETN"]
        summary = payload.get("deployment_summary") or {}
        actual_bucket = "deployable" if "ETN" in (summary.get("deployable") or []) else ("almost" if "ETN" in (summary.get("almost") or []) else None)
        expect(technical.get("ETN", {}).get("actionState") == baseline_etn_action, f"stale prose should preserve ETN technical state {baseline_etn_action}, got {technical.get('ETN')}", errors)
        expect(deployment.get("ETN", {}).get("state") == baseline_etn_state, f"stale prose should preserve ETN deployment state {baseline_etn_state}, got {deployment.get('ETN')}", errors)
        expect(actual_bucket == baseline_etn_bucket, f"stale prose should preserve ETN deployment summary bucket {baseline_etn_bucket}, got {summary}", errors)
        if baseline_etn_bucket == "deployable":
            expect(len(deployable_cards) == 1, f"deployable ETN should render exactly one deployable card, got {deployable_cards}", errors)
            for card in deployable_cards:
                expect((card.get("reviewOnlyNoApplyArtifact") is True), f"ETN deployable card must remain review-only/no-apply, got {card}", errors)
        else:
            expect(not deployable_cards, f"non-deployable ETN must not render a deployable card, got {deployable_cards}", errors)
'''))

for old, new in repls:
    if old not in s:
        raise SystemExit('missing target block:\n' + old[:400])
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
