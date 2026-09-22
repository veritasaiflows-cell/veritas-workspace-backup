"""Tests for the unified arena intake runner.

All tests are file-only: no network, no model call, no live dispatch, no gate
write. Run either with `python scripts/test_unified_intake.py` or under pytest.
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arena_unified_intake as ui  # noqa: E402

# Executable paths that would let this module reach a transport or a model.
FORBIDDEN_IMPORTS = frozenset({
    "subprocess", "socket", "http", "urllib", "requests", "ftplib",
    "smtplib", "telnetlib", "xmlrpc", "ssl", "asyncio", "multiprocessing",
    "openclaw", "httpx", "aiohttp",
})
FORBIDDEN_CALL_NAMES = frozenset({
    "spawn", "spawnSync", "exec", "execl", "system", "popen", "Popen",
    "check_output", "check_call", "urlopen", "request", "connect",
})


def _mk_items(surface: str, n: int) -> list[dict]:
    return [
        {"surface": surface, "case_id": f"{surface}-case-{i:02d}", "rep": 1, "lane_lock": None}
        for i in range(n)
    ]


# --- 1. probe receipt validation -------------------------------------------

def test_probe_record_accepts_clean_pin():
    receipt = ui.make_probe_receipt("ollama-cloud/glm-5.3:cloud")
    assert ui.probe_record(receipt) is True


def test_probe_record_rejects_requested_effective_mismatch():
    receipt = ui.make_probe_receipt("ollama-cloud/glm-5.3:cloud")
    receipt["effective"] = "openai/gpt-5.6-sol"
    assert ui.probe_record(receipt) is False


def test_probe_record_rejects_fallback_and_missing_fields():
    receipt = ui.make_probe_receipt("m/x", applied=False, fallback=True)
    assert ui.probe_record(receipt) is False
    assert ui.probe_record({"requested": "m/x", "effective": "m/x"}) is False
    assert ui.probe_record(None) is False
    assert ui.probe_record({"requested": "", "effective": "", "modelApplied": True,
                            "fallbackUsed": False}) is False


def test_probe_record_rejects_non_boolean_flags():
    receipt = {"requested": "m/x", "effective": "m/x",
               "modelApplied": 1, "fallbackUsed": 0}
    assert ui.probe_record(receipt) is False


# --- 2. scheduler: cap, stagger, determinism -------------------------------

def test_slots_free_never_negative():
    assert ui.slots_free(0) == 4
    assert ui.slots_free(4) == 0
    assert ui.slots_free(9) == 0


def test_wave_lane_count_never_exceeds_cap():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60)
    plan = sched.plan(_mk_items("A", 12))
    assert plan["max_lane_count"] <= 4
    assert all(w["lane_count"] <= 4 for w in plan["waves"])
    assert plan["item_count"] == 12


def test_cap_never_exceeded_under_simulated_slow_lanes():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60)
    items = _mk_items("B", 12)
    sim = sched.simulate(items, lane_duration_s=5000.0)
    assert sim["cap_respected"] is True
    assert sim["observed_max_concurrent"] <= 4


def test_cap_holds_with_tiny_stagger_and_many_lanes():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=1)
    sim = sched.simulate(_mk_items("A", 40), lane_duration_s=900.0)
    assert sim["observed_max_concurrent"] <= 4


def test_stagger_offsets_respected():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60)
    plan = sched.plan(_mk_items("A", 12))
    for wave in plan["waves"]:
        assert wave["planned_start_s"] == wave["wave_index"] * 60
        for lane in wave["items"]:
            assert lane["planned_start_s"] == wave["planned_start_s"]
    sim = sched.simulate(_mk_items("A", 12), lane_duration_s=120.0)
    for a in sim["assignments"]:
        assert a["actual_start_s"] >= a["planned_start_s"]


def test_scheduler_is_deterministic_given_input_order():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60)
    items = _mk_items("C", 12)
    first = json.dumps(sched.plan(items), sort_keys=True)
    second = json.dumps(sched.plan(items), sort_keys=True)
    assert first == second


def test_surface_d_serializes_sequential_on_one_lane():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60)
    items = ui.plan_surface_d("m/x")
    plan = sched.plan(items)
    assert plan["wave_count"] == 3
    assert all(w["lane_count"] == 1 for w in plan["waves"])
    order = [w["items"][0]["case_id"] for w in plan["waves"]]
    assert order == ["mission-1", "mission-2", "mission-3"]


# --- 3. adapters reference frozen paths only -------------------------------

def _referenced_paths(items: list[dict]) -> list[str]:
    refs: list[str] = []
    for item in items:
        for key in ("turns", "prompt_paths", "mounts"):
            refs.extend(item.get(key) or [])
        for key in ("runner_path", "grader_path", "keys_path", "gate_path", "mission_dir"):
            if item.get(key):
                refs.append(item[key])
        cli = item.get("cli") or {}
        if cli.get("pattern_path"):
            refs.append(cli["pattern_path"])
    return refs


def test_adapters_reference_existing_frozen_paths_only():
    plan = ui.build_plan("ollama-cloud/glm-5.3:cloud")
    checked = 0
    for surface in ui.SURFACES:
        refs = _referenced_paths(plan["surfaces"][surface]["items"])
        assert refs, f"surface {surface} referenced no paths"
        for ref in refs:
            assert ".." not in ref
            target = ui.WORKSPACE / ref
            assert target.exists(), f"surface {surface}: missing frozen path {ref}"
            checked += 1
    assert checked > 0


def test_surface_c_overlay_root_is_sealed_bank_overlay_with_all_four_files():
    """Regression: Surface C must grade against the sealed BANK overlay.

    The former constant pointed at `arena-agentic-v1-20260920-overlay/`, a
    stale 2-file copy (key-shapes + quarantine). It resolved fine and passed
    the existence checks, so the plan silently graded Surface C against an
    unsealed overlay missing dispatch-authorization.json and
    candidate-isolation.json. Guard the sealed root and all four files.
    """
    bank = ui.SURFACE_B_DIR.resolve()
    overlay = ui.SURFACE_C_OVERLAY_DIR.resolve()

    # 1. The overlay root must live inside the sealed BANK directory.
    assert overlay.is_dir(), f"overlay root missing: {overlay}"
    assert overlay == bank / "overlay", f"overlay root not BANK/overlay: {overlay}"
    assert bank in overlay.parents, f"overlay root escapes sealed BANK: {overlay}"
    assert "20260920-overlay" not in overlay.as_posix(), (
        f"overlay root still points at the stale copy: {overlay}")

    # 2. All four sealed overlay files must be present.
    sealed_files = (
        "key-shapes.json",
        "quarantine.json",
        "dispatch-authorization.json",
        "candidate-isolation.json",
    )
    for name in sealed_files:
        target = overlay / name
        assert target.is_file(), f"sealed overlay file missing: {name}"
        assert target.resolve().parent == overlay, (
            f"sealed overlay file escapes overlay root: {name}")
    assert sorted(p.name for p in overlay.iterdir() if p.is_file()) == sorted(sealed_files)

    # 3. The graded Surface C keys file must be the sealed one, not the stale copy.
    plan = ui.build_plan("m/x")
    items = plan["surfaces"]["C"]["items"]
    assert items, "surface C planned no items"
    for item in items:
        keys = (ui.WORKSPACE / item["keys_path"]).resolve()
        assert keys == (overlay / "key-shapes.json").resolve(), (
            f"surface C graded against a non-sealed keys file: {item['keys_path']}")
    assert ui.SURFACE_C_KEY_SHAPES.resolve() == (overlay / "key-shapes.json").resolve()
    assert ui.SURFACE_C_QUARANTINE.resolve() == (overlay / "quarantine.json").resolve()

    # 4. The gate consumed by Surface B/D is the same sealed overlay file.
    assert ui.DISPATCH_GATE.resolve() == (overlay / "dispatch-authorization.json").resolve()


def test_surface_c_grader_path_is_the_live_lineage_not_the_packet_snapshot():
    """Regression: the plan must reference the grader that actually ran.

    `SURFACE_B_GRADER` pointed at `BANK/reference/grader-frozen.py`, a sealed
    packet snapshot that is an OLDER generation of the runner: it has no
    overlay/authorization/contamination hardening, no `--fixtures`/`--exposure`
    flags, and its `grade_text` emits only
    `instance_id, family, json_valid, factual, strict_pass, parse_error`. It cannot
    produce the sealed run's `graded-results.json` (which carries
    `strict_pass_clean`, `operational_timeout`, `contamination_*`), so a plan
    pointing at it documents a grader that did not grade the run.

    Correcting this reference changes no sealed artifact, grade, or board: only
    the intake plan's own pointer.
    """
    live = (ui.WORKSPACE / "scripts" / "arena_hidden_bank_runner.py").resolve()
    frozen = ui.SURFACE_B_GRADER_FROZEN.resolve()
    assert live.is_file(), f"live grader missing: {live}"
    assert frozen.is_file(), f"packet snapshot missing (sealed record): {frozen}"
    assert live != frozen

    plan = ui.build_plan("m/x")
    for surface in ("B", "C"):
        for item in plan["surfaces"][surface]["items"]:
            grader = (ui.WORKSPACE / item["grader_path"]).resolve()
            assert grader == live, (
                f"surface {surface} grader is not the live lineage: "
                f"{item['grader_path']}")
            assert grader != frozen, (
                f"surface {surface} still points at the packet snapshot: "
                f"{item['grader_path']}")
            assert item["exposure"] == ui.SURFACE_B_EXPOSURE == "with-fixtures"

    # The live runner must be the hardened one, not the packet snapshot: the
    # grade-file/exposure machinery only exists in the live generation.
    source = live.read_text(encoding="utf-8")
    for marker in ("--exposure", "--fixtures", "strict_pass_clean",
                   "check_overlay", "check_authorization"):
        assert marker in source, f"live grader missing {marker!r}"
    assert "strict_pass_clean" not in frozen.read_text(encoding="utf-8")


def test_adapter_item_counts_match_locked_transports():
    plan = ui.build_plan("m/x")
    counts = {s: plan["surfaces"][s]["item_count"] for s in ui.SURFACES}
    assert counts == {"A": 12, "B": 12, "C": 12, "D": 3}


def test_transports_match_locked_decisions():
    plan = ui.build_plan("m/x")
    transports = {s: {i["transport"] for i in plan["surfaces"][s]["items"]}
                  for s in ui.SURFACES}
    assert transports["A"] == {"collectors"}
    assert transports["B"] == {"collectors"}
    assert transports["C"] == {"cli-lab-pipe"}
    assert transports["D"] == {"spawn-visible-mount"}
    cli = plan["surfaces"]["C"]["items"][0]["cli"]
    assert cli["agent"] == "oxalpha-functional-lab"
    assert cli["pattern_path"].endswith("cli-dispatch.py")


def test_script_duplicates_no_prompt_text():
    source = (ui.WORKSPACE / "scripts" / "arena_unified_intake.py").read_text(encoding="utf-8")
    for banned in ("Return only the required JSON object", "settlement cascade",
                   "declared_row_count"):
        assert banned not in source, f"prompt text leaked into runner: {banned}"


# --- 4. adjudication labels ------------------------------------------------

def test_labels_match_overlay_taxonomy_and_have_definitions():
    assert set(ui.ALL_LABELS) == {
        "TIMEOUT_EMPTY", "ANSWERED_FAIL", "INVENTED", "CONTAMINATED", "TRANSPORT_TAINT"}
    for label in ui.ALL_LABELS:
        assert ui.label_definition(label).strip()
        assert isinstance(ui.LABEL_DEFINITIONS[label], str)


def test_adjudicate_maps_records_to_labels():
    assert ui.adjudicate({"response_text": "", "strict_pass": False}) == ui.TIMEOUT_EMPTY
    assert ui.adjudicate({"response_text": "{}", "strict_pass": False}) == ui.ANSWERED_FAIL
    assert ui.adjudicate({"response_text": "{}", "strict_pass": True,
                          "invented": True}) == ui.INVENTED
    assert ui.adjudicate({"response_text": "{}", "strict_pass": True,
                          "contaminated": True}) == ui.CONTAMINATED
    assert ui.adjudicate(None) == ui.TRANSPORT_TAINT
    assert ui.adjudicate({"response_text": "{}", "strict_pass": True}) is None


def test_transport_taint_outranks_everything_else():
    record = {"response_text": "", "strict_pass": True, "contaminated": True,
              "invented": True, "transport_failed": True}
    assert ui.adjudicate(record) == ui.TRANSPORT_TAINT
    bad_probe = {"requested": "m/x", "effective": "other", "modelApplied": True,
                 "fallbackUsed": False}
    assert ui.adjudicate({"response_text": "{}", "strict_pass": True,
                          "probe": bad_probe}) == ui.TRANSPORT_TAINT


# --- 5. model card ---------------------------------------------------------

def test_model_card_has_no_merged_score():
    plan = ui.build_plan("m/x")
    summaries = {
        "A": {"total": 12, "strict": 3, "eligible": 12, "transport": "clean",
              "take_voided": False, "flags": {}},
        "B": {"total": 12, "strict": 2, "eligible": 12, "transport": "clean",
              "take_voided": False, "flags": {}},
        "C": {"total": 12, "strict": 0, "eligible": 0, "transport": "quarantined",
              "take_voided": True, "flags": {"TRANSPORT_TAINT": 1}},
        "D": {"total": 3, "strict": 1, "eligible": 3, "transport": "clean",
              "take_voided": False, "flags": {}},
    }
    card = ui.build_model_card("m/x", ui.make_probe_receipt("m/x"), summaries)
    assert card["schema"] == ui.CARD_SCHEMA
    for banned in ui.FORBIDDEN_CARD_KEYS:
        assert banned not in card, f"merged score key present: {banned}"
    assert card["quarantined_surfaces"] == ["C"]
    assert "not comparable" in card["comparability"]
    for surface in ui.SURFACES:
        assert "strict" in card["surfaces"][surface]
        assert "strict_clean" not in card["surfaces"][surface]


def test_summarize_surface_voids_take_on_taint():
    records = [{"response_text": "{}", "strict_pass": True}] * 11
    records.append({"response_text": "{}", "strict_pass": True,
                    "probe": {"requested": "m/x", "effective": "other",
                              "modelApplied": True, "fallbackUsed": False}})
    summary = ui.summarize_surface(records)
    assert summary["transport"] == "quarantined"
    assert summary["take_voided"] is True
    assert summary["strict"] == 0 and summary["eligible"] == 0
    assert summary["flags"]["TRANSPORT_TAINT"] == 1


def test_summarize_surface_clean_counts_strict():
    records = [
        {"response_text": "{}", "strict_pass": True},
        {"response_text": "{}", "strict_pass": False},
        {"response_text": "", "strict_pass": False},
    ]
    summary = ui.summarize_surface(records)
    assert summary["transport"] == "clean"
    assert summary["strict"] == 1 and summary["eligible"] == 2
    assert summary["eligible_rule"] == "operational_excluded"
    assert summary["operational_count"] == 1
    assert summary["flags"] == {"ANSWERED_FAIL": 1, "TIMEOUT_EMPTY": 1}


# --- 6. dry-run: taint quarantine, intact gate, artifacts -------------------

def test_dry_run_quarantines_tainted_surface_and_keeps_gate_intact():
    gate_before = ui.read_gate()
    assert gate_before["dispatch_ready"] is False

    out = Path(tempfile.mkdtemp(prefix="unified-intake-test-"))
    outcome = ui.run_dry_run("ollama-cloud/glm-5.3:cloud", out_dir=out)
    summary = outcome["summary"]

    assert summary["status"] == "dry_run_complete"
    assert summary["spend"] == {"model_calls": 0, "live_dispatch": 0, "network": 0}
    assert summary["taint_injection"] is not None
    assert summary["taint_injection"]["label"] == ui.TRANSPORT_TAINT
    assert summary["taint_injection"]["surface"] == "C"
    assert summary["quarantined_surfaces"] == ["C"]
    assert summary["surfaces"]["C"]["transport"] == "quarantined"
    assert summary["surfaces"]["C"]["strict"] == 0
    assert summary["surfaces"]["C"]["take_voided"] is True
    for surface in ("A", "B", "D"):
        assert summary["surfaces"][surface]["transport"] == "clean"

    gate_after = ui.read_gate()
    assert gate_after["dispatch_ready"] is False
    assert gate_after["sha256"] == gate_before["sha256"]
    assert summary["gate"]["intact_after_dry_run"] is True

    for name in ("plan.json", "waves.json", "model-card.json", "dryrun-summary.json"):
        assert (out / name).exists(), f"dry-run artifact missing: {name}"
    card = json.loads((out / "model-card.json").read_text(encoding="utf-8"))
    for banned in ui.FORBIDDEN_CARD_KEYS:
        assert banned not in card


def test_dry_run_plan_covers_all_surfaces_without_spend():
    out = Path(tempfile.mkdtemp(prefix="unified-intake-test-"))
    outcome = ui.run_dry_run("m/x", out_dir=out, lane_duration_s=600.0)
    plan = outcome["result"]["plan"]
    for surface in ui.SURFACES:
        assert plan["surfaces"][surface]["item_count"] > 0
    assert outcome["result"]["model_calls"] == 0
    assert outcome["result"]["live_dispatch"] == 0
    assert outcome["result"]["gate_intact"] is True


def test_live_dispatch_is_refused():
    gate = ui.read_gate()
    try:
        ui.refuse_live_dispatch(gate)
    except PermissionError as exc:
        assert "dispatch_ready" in str(exc)
    else:
        raise AssertionError("live dispatch must be refused while the gate is closed")


# --- 7. no model-call path in the runner source ----------------------------

def test_runner_source_has_no_model_call_paths():
    """Executable code only: no transport/model import and no dispatch call.

    Documentation prose may name a canonical transport (e.g. in the module
    docstring). What must not exist is any import or call expression that could
    actually reach a model, a gateway or a subprocess, so this checks the parsed
    AST rather than raw substrings.
    """
    source = (ui.WORKSPACE / "scripts" / "arena_unified_intake.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    leaked_imports = imported & FORBIDDEN_IMPORTS
    assert not leaked_imports, f"runner imports a live-call module: {sorted(leaked_imports)}"

    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    leaked_calls = called & FORBIDDEN_CALL_NAMES
    assert not leaked_calls, f"runner calls a live-dispatch primitive: {sorted(leaked_calls)}"

    # A bare mention is prose; an invocation is a call site.
    assert "sessions_spawn(" not in source
    assert "openclaw agent" not in source


def test_runner_does_not_write_the_gate():
    source = (ui.WORKSPACE / "scripts" / "arena_unified_intake.py").read_text(encoding="utf-8")
    assert "DISPATCH_GATE.write" not in source
    assert "dispatch_ready\"] =" not in source


# --- 8. per-item budgets and token-cap classification ------------------------

def test_scheduler_honours_per_item_timeout_s():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60, turn_deadline_s=600)
    items = [
        {"surface": "A", "case_id": "custom", "rep": 1, "lane_lock": None,
         "timeout_s": 120},
        {"surface": "A", "case_id": "plain", "rep": 1, "lane_lock": None},
    ]
    plan = sched.plan(items)
    lanes = [lane for wave in plan["waves"] for lane in wave["items"]]
    by_case = {lane["case_id"]: lane for lane in lanes}
    assert by_case["custom"]["deadline_s"] == 120
    assert by_case["custom"]["timeout_s"] == 120
    assert by_case["plain"]["deadline_s"] == 600
    assert by_case["plain"]["timeout_s"] == 600


def test_scheduler_falls_back_on_absent_or_invalid_per_item_budget():
    sched = ui.WaveScheduler(max_concurrent=4, stagger_s=60, turn_deadline_s=600)
    items = [
        {"surface": "A", "case_id": f"c{i}", "rep": 1, "lane_lock": None, **extra}
        for i, extra in enumerate(({}, {"timeout_s": 0}, {"timeout_s": -5},
                                   {"timeout_s": "600"}, {"timeout_s": True}))
    ]
    plan = sched.plan(items)
    lanes = [lane for wave in plan["waves"] for lane in wave["items"]]
    assert [lane["deadline_s"] for lane in lanes] == [600] * 5


def test_scheduler_carries_token_budget_with_fallback():
    sched = ui.WaveScheduler(max_concurrent=2, stagger_s=60, turn_deadline_s=600,
                             max_output_tokens=64000)
    items = [
        {"surface": "A", "case_id": "custom", "rep": 1, "lane_lock": None,
         "timeout_s": 300, "max_output_tokens": 8000},
        {"surface": "A", "case_id": "plain", "rep": 1, "lane_lock": None},
    ]
    plan = sched.plan(items)
    lanes = [lane for wave in plan["waves"] for lane in wave["items"]]
    by_case = {lane["case_id"]: lane for lane in lanes}
    assert by_case["custom"]["max_output_tokens"] == 8000
    assert by_case["custom"]["deadline_s"] == 300
    assert by_case["plain"]["max_output_tokens"] == 64000
    assert by_case["plain"]["deadline_s"] == 600


def test_adapters_author_both_budgets_on_every_item():
    plan = ui.build_plan("m/x")
    for surface in ui.SURFACES:
        for item in plan["surfaces"][surface]["items"]:
            assert item["timeout_s"] == 600, (surface, item["case_id"])
            assert item["max_output_tokens"] == ui.DEFAULT_MAX_OUTPUT_TOKENS, (
                surface, item["case_id"])
    sched = ui.WaveScheduler()
    for surface in ui.SURFACES:
        waves = sched.plan(plan["surfaces"][surface]["items"])
        for wave in waves["waves"]:
            for lane in wave["items"]:
                assert lane["deadline_s"] == 600
                assert lane["max_output_tokens"] == ui.DEFAULT_MAX_OUTPUT_TOKENS


def test_code_budget_matches_overlay_and_clears_max_observed():
    overlay = json.loads(ui.SURFACE_A_TOKEN_OVERLAY.read_text(encoding="utf-8"))
    assert overlay["budgets"]["max_output_tokens"] == ui.DEFAULT_MAX_OUTPUT_TOKENS
    assert ui.DEFAULT_MAX_OUTPUT_TOKENS == 64000
    assert overlay["budgets"]["max_output_tokens"] > 46288
    assert "not comparable" in overlay["comparability"]


def test_token_capped_turn_is_operational_not_factual():
    record = ui.make_truncated_turn_evidence(
        '{"partial": "capped"}',
        {"input_tokens": 512, "output_tokens": 64000},
        "max_output_tokens",
    )
    assert record["partial_response_text"] == '{"partial": "capped"}'
    assert record["usage"]["output_tokens"] == 64000
    assert record["stop_reason"] == "max_output_tokens"
    assert ui.is_operational_outcome(record) is True
    assert ui.adjudicate(record) == ui.TIMEOUT_EMPTY
    summary = ui.summarize_surface([record])
    assert summary["flags"] == {ui.TIMEOUT_EMPTY: 1}
    assert summary["strict"] == 0 and summary["eligible"] == 0
    assert summary["eligible_rule"] == "operational_excluded"
    assert summary["operational_count"] == 1
    assert summary["truncated_with_pass"] == 0
    assert summary["transport"] == "clean"


def test_truncated_flag_with_partial_text_is_operational():
    record = {"response_text": '{"a": 1}', "strict_pass": False,
              "truncated": True, "stop_reason": "wall_clock",
              "partial_response_text": '{"a": 1}',
              "usage": {"input_tokens": 10, "output_tokens": 4000}}
    assert ui.adjudicate(record) == ui.TIMEOUT_EMPTY


def test_ordinary_wrong_answer_still_factual():
    assert ui.adjudicate({"response_text": '{"a": 1}',
                           "strict_pass": False}) == ui.ANSWERED_FAIL
    assert ui.is_operational_outcome({"response_text": "x",
                                       "strict_pass": True}) is False
    try:
        ui.make_truncated_turn_evidence("x", {}, "complete")
    except ValueError:
        pass
    else:
        raise AssertionError("non-operational stop_reason must be refused")


def test_dry_run_truncation_stays_operational_end_to_end():
    out = Path(tempfile.mkdtemp(prefix="unified-intake-truncation-"))
    ex = ui.MockExecutor("m/x", taint_surface="C", taint_index=99,
                         truncate=("A", 0))
    outcome = ui.run_dry_run("m/x", out_dir=out, executor=ex)
    summary = outcome["summary"]
    assert summary["surfaces"]["A"]["transport"] == "clean"
    assert summary["surfaces"]["A"]["flags"].get(ui.TIMEOUT_EMPTY, 0) >= 1


# --- 9. adjudication-gap regressions (2026-09-21 token-budget follow-up) ----
# Each of these FAILS against the pre-fix code (contamination masked by
# truncation; truncated pass silently absorbed; eligible counted operational)
# and PASSES after the fix.

def test_gap1_contaminated_truncated_quarantines_take():
    """Gap 1a: contaminated + truncated voids the whole take."""
    clean = {"response_text": '{}', "strict_pass": True}
    leaked = ui.make_truncated_turn_evidence(
        '{"alloc": [1], "structure_id": "hidden-only"}',
        {"input_tokens": 10, "output_tokens": 64000},
        "max_output_tokens",
        contaminated=True,
    )
    summary = ui.summarize_surface([clean, leaked])
    assert summary["transport"] == "quarantined"
    assert summary["take_voided"] is True
    assert summary["strict"] == 0 and summary["eligible"] == 0
    assert summary["flags"].get(ui.CONTAMINATED, 0) == 1


def test_gap1_contaminated_truncated_is_not_timeout_empty():
    """Gap 1b: the leak is reported as CONTAMINATED, never TIMEOUT_EMPTY."""
    assert ui._LABEL_PRECEDENCE == (
        ui.TRANSPORT_TAINT, ui.CONTAMINATED, ui.TIMEOUT_EMPTY,
        ui.INVENTED, ui.ANSWERED_FAIL)
    record = ui.make_truncated_turn_evidence(
        "partial leak", {"output_tokens": 64000}, "max_output_tokens",
        contaminated=True,
    )
    assert ui.is_operational_outcome(record) is True
    assert ui.adjudicate(record) == ui.CONTAMINATED
    # Same record without the truncation fields still contaminates.
    plain = {"response_text": "partial leak", "strict_pass": False,
             "contaminated": True}
    assert ui.adjudicate(plain) == ui.CONTAMINATED


def test_gap1_truncation_grading_wires_partial_text_flag():
    """Gap 1c: the flag must come from grading the preserved partial text."""
    record = ui.make_truncated_turn_evidence(
        '{"x": 1}', {"output_tokens": 5}, "wall_clock")
    assert record["contaminated"] is False
    ui.attach_truncation_grading(record, {
        "contaminated": True, "contamination_severity": "conclusive",
        "contamination_tokens": ["hidden-only"],
        "strict_pass": False, "invented": False,
    })
    assert record["contaminated"] is True
    assert ui.adjudicate(record) == ui.CONTAMINATED
    assert ui.summarize_surface([record])["take_voided"] is True


def test_gap1_transport_taint_still_outranks_contamination():
    """Gap 1d: TRANSPORT_TAINT remains the highest precedence."""
    record = ui.make_truncated_turn_evidence(
        "leak", {"output_tokens": 1}, "max_output_tokens",
        contaminated=True,
    )
    record["transport_failed"] = True
    assert ui.adjudicate(record) == ui.TRANSPORT_TAINT
    bad_probe = {"requested": "m/x", "effective": "other",
                 "modelApplied": True, "fallbackUsed": False}
    record2 = ui.make_truncated_turn_evidence(
        "leak", {"output_tokens": 1}, "max_output_tokens",
        contaminated=True,
    )
    record2["probe"] = bad_probe
    assert ui.adjudicate(record2) == ui.TRANSPORT_TAINT


def test_gap2_truncated_pass_stays_operational_but_counted():
    """Gap 2 (decision b): correct-but-truncated stays operational, counted."""
    record = ui.make_truncated_turn_evidence(
        '{"complete": "answer"}', {"output_tokens": 64000},
        "max_output_tokens", strict_pass=True,
    )
    assert ui.adjudicate(record) == ui.TIMEOUT_EMPTY
    assert ui.is_truncated_with_pass(record) is True
    assert ui.is_truncated_with_pass(
        {"response_text": "", "strict_pass": False}) is False
    summary = ui.summarize_surface([record])
    assert summary["transport"] == "clean"
    assert summary["strict"] == 0
    assert summary["eligible"] == 0
    assert summary["operational_count"] == 1
    assert summary["truncated_with_pass"] == 1
    assert summary["flags"] == {ui.TIMEOUT_EMPTY: 1}


def test_gap3_operational_excluded_from_eligible_mixed_set():
    """Gap 3: eligible = total - operational; cap cannot depress scores."""
    records = [
        {"response_text": '{}', "strict_pass": True},
        {"response_text": '{}', "strict_pass": False},
        ui.make_truncated_turn_evidence('{"a": 1}', {"output_tokens": 1},
                                        "max_output_tokens"),
        ui.make_truncated_turn_evidence('{"k": "v"}', {"output_tokens": 2},
                                        "wall_clock", strict_pass=True),
        {"response_text": "", "strict_pass": False},
    ]
    summary = ui.summarize_surface(records)
    assert summary["total"] == 5
    assert summary["flags"] == {"ANSWERED_FAIL": 1, "TIMEOUT_EMPTY": 3}
    assert summary["operational_count"] == 3
    assert summary["eligible"] == 2
    assert summary["eligible_rule"] == "operational_excluded"
    assert summary["strict"] == 1
    assert summary["truncated_with_pass"] == 1
    assert summary["transport"] == "clean"


# --- runner ---------------------------------------------------------------

def _all_tests() -> list:
    return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main() -> int:
    failures = []
    for test in _all_tests():
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures.append((test.__name__, exc))
            print(f"FAIL  {test.__name__}: {exc!r}")
    print(f"\n{len(_all_tests()) - len(failures)}/{len(_all_tests())} passed")
    if failures:
        print("FAILED: " + ", ".join(name for name, _ in failures))
        return 1
    print("ALL GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
