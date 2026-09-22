#!/usr/bin/env python3
"""A4 draft-scratch tests for main_model_selection. Stdlib only; no workspace
imports and no live config/DB reads (synthetic fixtures only).
Run from the scratch dir:  python test_main_model_selection.py"""
from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import main_model_selection as mms

ERRORS: list[str] = []
TMP = Path(tempfile.mkdtemp(prefix="mms-a4-scratch-"))
SEQ = 0


def expect(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def config(payload) -> Path:
    global SEQ
    SEQ += 1
    path = TMP / f"cfg-{SEQ}.json"
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload,
                    encoding="utf-8")
    return path


def make_db(rows, *, agent_id="main", version=19, role="agent") -> Path:
    """rows: (session_key, current_session_id, provider, model, source, entry_valid)."""
    global SEQ
    SEQ += 1
    path = TMP / f"session-{SEQ}.sqlite"
    db = sqlite3.connect(str(path))
    db.execute("CREATE TABLE schema_meta(meta_key TEXT,role TEXT,schema_version INTEGER,agent_id TEXT)")
    db.execute("INSERT INTO schema_meta VALUES('primary',?,?,?)", (role, version, agent_id))
    db.execute("CREATE TABLE session_nodes(session_key TEXT PRIMARY KEY,current_session_id TEXT,entry_json TEXT,entry_valid INTEGER,updated_at INTEGER)")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for key, sid, provider, model, source, valid in rows:
        entry = json.dumps({"providerOverride": provider, "modelOverride": model,
                            "modelOverrideSource": source})
        db.execute("INSERT INTO session_nodes VALUES(?,?,?,?,?)",
                   (key, sid, entry, valid, now_ms))
    db.commit()
    db.close()
    return path


KEY = "agent:main:dashboard:07d1719a-cb15-44a6-9549-c47e6e577517"
SID = "c855774f-22ea-4620-95e9-6d62095d3e0c"
GLM = "xai/grok-4.6"


def cfg_main(model_value, defaults_value="openai/gpt-6-astra"):
    agents: dict = {"entries": {"main": {"identity": "veritas-main", "model": model_value}}}
    if defaults_value is not None:
        agents["defaults"] = {"model": defaults_value}
    return config({"agents": agents})


def cfg_entry(entry, defaults_value="openai/gpt-6-astra"):
    agents: dict = {"entries": {"main": entry}}
    if defaults_value is not None:
        agents["defaults"] = {"model": defaults_value}
    return config({"agents": agents})


def codes(findings) -> set:
    return {item["code"] for item in findings}


def test_config_precedence_and_inherit() -> None:
    r = mms.resolve_configured(cfg_entry({"identity": "veritas-main"}, "openai/gpt-6-astra"))
    expect(r["model"] == "openai/gpt-6-astra" and r["source"] == "inherited-defaults"
           and r["error"] is None, "valid Main entry with other metadata and no model inherits")
    r = mms.resolve_configured(cfg_main("xai/grok-4.6", "openai/gpt-6-astra"))
    expect(r["model"] == "xai/grok-4.6" and r["source"] == "explicit-string",
           "explicit string beats defaults")
    r = mms.resolve_configured(cfg_main({"primary": "xai/grok-4.6"}, "openai/gpt-6-astra"))
    expect(r["model"] == "xai/grok-4.6" and r["source"] == "explicit-object",
           "explicit object beats defaults")
    r = mms.resolve_configured(cfg_main({}, "openai/gpt-6-astra"))
    expect(r["model"] == "openai/gpt-6-astra", "empty model {} inherits primary")
    r = mms.resolve_configured(cfg_main({"fallbacks": []}, "openai/gpt-6-astra"))
    expect(r["model"] == "openai/gpt-6-astra", "valid {fallbacks:[]} inherits primary")


def test_production_fallback_shape() -> None:
    """Current production shape: defaults primary exact + non-empty exact fallbacks."""
    payload = {"agents": {"defaults": {"model": {"primary": "xai/grok-4.6",
                                                 "fallbacks": ["zai/glm-5.3"]}}}}
    r = mms.resolve_configured(config(payload))
    expect(r["model"] == "xai/grok-4.6" and r["source"] == "legacy-defaults"
           and r["error"] is None, "well-formed non-empty fallbacks accepted as metadata; primary selects")
    payload = {"agents": {"entries": {"main": {"model": {"primary": "openai/gpt-6-astra",
                                                         "fallbacks": ["zai/glm-5.3"]}}}}}
    r = mms.resolve_configured(config(payload))
    expect(r["model"] == "openai/gpt-6-astra" and r["source"] == "explicit-object",
           "explicit object with exact fallbacks selects primary")
    r = mms.resolve_configured(cfg_main({"primary": "xai/grok-4.6", "fallbacks": ["bare-alias"]}))
    expect(r["model"] is None and r["error"] == "main_model_malformed",
           "fallback alias without provider slash fails closed")
    r = mms.resolve_configured(cfg_main({"primary": "xai/grok-4.6", "fallbacks": "zai/glm-5.3"}))
    expect(r["model"] is None, "non-list fallbacks fails closed")
    r = mms.resolve_configured(cfg_main({"primary": "xai/grok-4.6", "fallbacks": [123]}))
    expect(r["model"] is None, "numeric fallback fails closed")
    r = mms.resolve_configured(cfg_main({"primary": "xai/grok-4.6", "shadow": "z"}))
    expect(r["model"] is None, "invented model keys fail closed")


def test_strict_model_tokens() -> None:
    bad = ["xai/grok-4.6 ", " xai/grok-4.6", "xai/grok-4.6\n", "xai/grok-4.6\x01",
           "openai/gpt-6-astra@main", "xai/grok-4.6?x=1", "xai/grok-4.6#frag",
           "./local", "../escape", "~/home", "xai//double", "provideronly",
           "a/b/c", ".hidden/x", "xai/grok 4.6"]
    for value in bad:
        r = mms.resolve_configured(cfg_main(value, "openai/gpt-6-astra"))
        expect(r["model"] is None, f"non-exact model ref must fail: {value!r}")
    r = mms.resolve_configured(cfg_main("grok-alias", "openai/gpt-6-astra"))
    expect(r["model"] is None, "bare alias fails closed")


def test_config_malformed_matrix() -> None:
    expect(mms.resolve_configured(cfg_main("main", "openai/gpt-6-astra"))["model"] is None,
           "non-dict Main entry fails closed")
    expect(mms.resolve_configured(cfg_main(123))["model"] is None, "numeric model fails")
    expect(mms.resolve_configured(cfg_main(None))["model"] is None, "null model fails, never inherits")
    expect(mms.resolve_configured(cfg_main("  "))["model"] is None, "blank model fails")
    expect(mms.resolve_configured(cfg_main({"primary": 123}))["model"] is None, "numeric primary fails")
    expect(mms.resolve_configured(cfg_main({"primary": "  "}))["model"] is None, "blank primary fails")
    expect(mms.resolve_configured(config({"agents": {"entries": ["main"]}}))["model"] is None,
           "list entries fails closed")
    expect(mms.resolve_configured(config({"agents": {"entries": None}}))["model"] is None,
           "null entries fails closed")
    expect(mms.resolve_configured(config(["agents"]))["model"] is None, "non-dict payload fails")
    expect(mms.resolve_configured(config({"agents": "entries"}))["model"] is None, "non-dict agents fails")
    payload = {"agents": {"defaults": {"model": "xai/grok-4.6"},
                          "entries": {"research-scout": {"model": "xai/grok-4.6"}}}}
    expect(mms.resolve_configured(config(payload))["model"] is None,
           "missing roster member never inherits matching defaults")
    r = mms.resolve_configured(config({"agents": {"defaults": {"model": "openai/gpt-6-astra"}}}))
    expect(r["model"] == "openai/gpt-6-astra" and r["source"] == "legacy-defaults",
           "absent entries+list keeps legacy Main default fallback")
    r = mms.resolve_configured(config(
        {"agents": {"defaults": {"model": "openai/gpt-6-astra"},
                    "list": [{"id": "main", "model": "openai/gpt-6-astra"}]}}))
    expect(r["model"] is None and r["error"] == "legacy_list_unsupported",
           "unsupported legacy list fails closed")
    r = mms.resolve_configured(TMP / "does-not-exist.json")
    expect(r["model"] is None and r["error"] == "config_unreadable",
           "read failure is null, never a fallback model")
    src = Path(inspect.getsourcefile(mms)).read_text(encoding="utf-8")
    expect("grok" not in src.lower().replace("grok-4.6", "").replace("veritas-main", ""),
           "module names no fallback model")


def test_reference_keys_per_level() -> None:
    base = {"agents": {"entries": {"main": {"model": "xai/grok-4.6"}}}}
    expect(mms.resolve_configured(config(dict(base)))["model"] == "xai/grok-4.6", "clean baseline resolves")
    for level in ("payload", "agents", "defaults", "entry", "model"):
        for ref in ("$include", "includes", "include", "extends", "$ref"):
            payload = json.loads(json.dumps(base))
            if level == "payload":
                payload[ref] = ["other.json"]
            elif level == "agents":
                payload["agents"][ref] = {}
            elif level == "defaults":
                payload["agents"]["entries"]["main"] = {"identity": "veritas-main"}
                payload["agents"]["defaults"] = {"model": "openai/gpt-6-astra", ref: "x"}
            elif level == "entry":
                payload["agents"]["entries"]["main"][ref] = "x"
            else:
                payload["agents"]["entries"]["main"]["model"] = {"primary": "xai/grok-4.6", ref: "x"}
            r = mms.resolve_configured(config(payload))
            expect(r["model"] is None and r["error"] == "selection_reference_unsupported",
                   f"reference key {ref!r} at {level} fails closed")
    benign = {"agents": {"bindings": {"x": 1}, "ownership": {"y": 2},
                         "entries": {"main": {"models": ["a"], "workspace": "w",
                                              "model": "xai/grok-4.6"}}},
              "bindings": {"top": True}}
    expect(mms.resolve_configured(config(benign))["model"] == "xai/grok-4.6",
           "unrelated valid metadata is ignored, never rejected")


def test_config_bytes_binding() -> None:
    path = cfg_main("xai/grok-4.6", "openai/gpt-6-astra")
    r = mms.resolve_configured(path)
    expect(r["config_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(),
           "config hash binds the exact bytes read")


def test_session_pin_and_negatives() -> None:
    cfg = cfg_main("openai/gpt-6-astra")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)])
    env = mms.resolve_effective(cfg, session_key=KEY, session_id=SID)
    eff = env["effective"]
    expect(eff["model"] == GLM and eff["basis"] == "user-pin-selected" and eff["source"] == "user",
           "exact user pin resolves SELECTED")
    expect(eff["session_key_sha256"] == hashlib.sha256(KEY.encode()).hexdigest()
           and KEY not in json.dumps(env) and SID not in json.dumps(env),
           "only hashes serialized, never raw identifiers")
    expect(mms.validate_main_route({"expected_model_path": GLM, "model": GLM,
                                    "model_selection": env}, cfg) == [],
           "fresh valid pin envelope validates clean")
    cases = [
        ([(KEY, SID, None, None, None, 1)], "configured-unpinned", "openai/gpt-6-astra", "all-null counts as unpinned"),
        ([(KEY, SID, "xai", "grok-4.6", "auto", 1)], "blocked", "session_source_auto_blocked", "auto never permission"),
        ([(KEY, SID, "xai", "grok-4.6", "observed", 1)], "blocked", "session_source_unknown", "unknown source blocks"),
        ([(KEY, SID, "xai", None, "user", 1)], "blocked", "session_pin_partial", "partial blocks"),
        ([(KEY, SID, None, "grok-4.6", "user", 1)], "blocked", "session_pin_partial", "partial blocks (provider)"),
        ([(KEY, SID, "", "grok-4.6", "user", 1)], "blocked", "session_pin_partial", "blank provider is not absent"),
        ([(KEY, SID, "xai", 123, "user", 1)], "blocked", "session_pin_partial", "numeric model is not absent"),
        ([(KEY, SID, None, None, "user", 1)], "blocked", "session_source_unknown", "non-null source with no pin blocks"),
        ([(KEY, SID, None, None, "auto", 1)], "blocked", "session_source_auto_blocked", "auto source with no pin blocks"),
        ([(KEY, SID, "xai", "grok-4.6", "user", 0)], "blocked", "session_entry_invalid", "invalid entry blocks"),
        ([(KEY, SID, "openai", "xai/grok-4.6", "user", 1)], "blocked", "session_provider_model_mismatch", "provider/model contradiction blocks"),
    ]
    for rows, basis, code_or_model, label in cases:
        mms.SESSION_DB_PATH = make_db(rows)
        env = mms.resolve_effective(cfg, session_key=KEY, session_id=SID)
        if basis == "blocked":
            expect(env["effective"]["basis"] == "blocked" and env["effective"]["error"] == code_or_model, label)
        else:
            expect(env["effective"]["basis"] == basis and env["effective"]["model"] == code_or_model, label)
    mms.SESSION_DB_PATH = make_db([(KEY, "00000000-0000-0000-0000-000000000000", "xai", "grok-4.6", "user", 1)])
    expect(mms.resolve_effective(cfg, session_key=KEY, session_id=SID)["effective"]["error"] == "session_unknown_or_replaced",
           "replaced window id fails closed")
    expect(mms.resolve_effective(cfg, session_key="not-a-key\n", session_id=SID)["effective"]["error"] == "session_key_malformed",
           "key with newline fails closed")
    expect(mms.resolve_effective(cfg, session_key=KEY, session_id="short")["effective"]["error"] == "session_id_malformed",
           "malformed id fails closed")
    expect(mms.resolve_effective(cfg, session_key=KEY, session_id=None)["effective"]["error"] == "session_pair_required",
           "half session pair fails closed")
    mms.SESSION_DB_PATH = TMP / "missing.sqlite"
    expect(mms.resolve_effective(cfg, session_key=KEY, session_id=SID)["effective"]["error"] == "session_db_unavailable",
           "missing db fails closed")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)], agent_id="other")
    expect(mms.resolve_effective(cfg, session_key=KEY, session_id=SID)["effective"]["error"] == "session_schema_unexpected",
           "wrong ownership fails closed")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)], version=18)
    expect(mms.resolve_effective(cfg, session_key=KEY, session_id=SID)["effective"]["error"] == "session_schema_unsupported",
           "unsupported schema version is an explicit blocker")


def test_forged_configured_envelope() -> None:
    """A3 fail-open #1: forged configured effective.model + matching expected must NOT validate."""
    cfg = cfg_main("openai/gpt-6-astra")
    env = mms.resolve_effective(cfg)
    forged = json.loads(json.dumps(env))
    forged["effective"]["model"] = "other/arbitrary-model"
    found = mms.validate_main_route({"expected_model_path": "other/arbitrary-model",
                                     "model_selection": forged}, cfg)
    expect(len(found) > 0 and "main_model_invalid" in codes(found),
           "forged configured effective model is rejected")


def test_invalid_present_envelope_no_downgrade() -> None:
    cfg = cfg_main("openai/gpt-6-astra")
    env = mms.resolve_effective(cfg)
    cases = [
        ("bad agent", {"agent_id": "evil"}, "model_selection_agent_invalid"),
        ("bad schema", {"schema": "other.v9"}, "model_selection_schema_invalid"),
        ("bad basis", None, "model_selection_basis_invalid"),
        ("unknown field", {"zzz": 1}, "model_selection_envelope_unknown_field"),
        ("raw identifier", {"session_key": KEY}, "session_raw_identifier_exposed"),
        ("non-dict envelope", "not-a-dict", "model_selection_envelope_invalid"),
    ]
    for label, mutation, code in cases:
        forged = json.loads(json.dumps(env))
        if mutation is None:
            forged["effective"]["basis"] = "whatever"
        elif isinstance(mutation, str):
            envelope = mutation
        elif label in ("bad agent", "bad schema"):
            forged.update(mutation)
        else:
            forged["effective"].update(mutation)
            envelope = forged
        if isinstance(mutation, str):
            found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                             "model_selection": envelope}, cfg)
        else:
            found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                             "model_selection": forged}, cfg)
        expect(code in codes(found), f"invalid-present envelope never downgrades ({label})")
    forged = json.loads(json.dumps(env))
    forged["effective"]["model"] = "other/arbitrary-model"
    forged["effective"]["basis"] = "user-pin-selected"
    forged["effective"]["session_key_sha256"] = "0" * 64
    forged["effective"]["session_id_sha256"] = "0" * 64
    found = mms.validate_main_route({"expected_model_path": "other/arbitrary-model",
                                     "model_selection": forged}, cfg)
    expect(len(found) > 0, "forged pin basis with fabricated hashes is rejected")


def test_forged_unpinned_hashes_and_transitions() -> None:
    """A3 fail-open #2: fabricated zero-identity unpinned hashes must NOT validate."""
    cfg = cfg_main("openai/gpt-6-astra")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, None, None, None, 1)])
    env = mms.resolve_effective(cfg, session_key=KEY, session_id=SID)
    expect(env["effective"]["basis"] == "configured-unpinned"
           and env["effective"]["model"] == "openai/gpt-6-astra", "genuine unpinned binds config model")
    expect(mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                    "model_selection": env}, cfg) == [],
           "genuine unpinned reread validates")
    forged = json.loads(json.dumps(env))
    forged["effective"]["session_key_sha256"] = "0" * 64
    forged["effective"]["session_id_sha256"] = "0" * 64
    found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                     "model_selection": forged}, cfg)
    expect("session_unknown_or_replaced" in codes(found), "fabricated unpinned hashes fail closed")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)])
    found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                     "model_selection": env}, cfg)
    expect("session_pin_changed" in codes(found), "newly pinned window blocks stale unpinned proof")
    mms.SESSION_DB_PATH = make_db([])
    found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                     "model_selection": env}, cfg)
    expect("session_unknown_or_replaced" in codes(found), "reset/deleted window blocks stale proof")


def test_pin_reread_transitions() -> None:
    cfg = cfg_main("openai/gpt-6-astra")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)])
    env = mms.resolve_effective(cfg, session_key=KEY, session_id=SID)
    route = {"expected_model_path": GLM, "model_selection": env}
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "other-model", "user", 1)])
    expect("session_pin_tampered" in codes(mms.validate_main_route(route, cfg)),
           "replaced pin fails closed")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, None, None, None, 1)])
    expect("session_pin_changed" in codes(mms.validate_main_route(route, cfg)),
           "reset-to-unpinned fails closed")


def test_timestamp_robustness() -> None:
    cfg = cfg_main("openai/gpt-6-astra")
    mms.SESSION_DB_PATH = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)])
    env = mms.resolve_effective(cfg, session_key=KEY, session_id=SID)
    naive = json.loads(json.dumps(env))
    naive["effective"]["resolved_at_utc"] = "2026-09-12T12:00:00"
    try:
        found = mms.validate_main_route({"expected_model_path": GLM, "model_selection": naive}, cfg)
    except TypeError as exc:
        ERRORS.append(f"naive timestamp raised TypeError: {exc}")
        return
    expect("session_packet_unreadable" not in codes(found), "naive timestamp parses as UTC, no exception")
    for bad in (123, None, "not-a-time", "2026-13-99T99:99:99Z"):
        tampered = json.loads(json.dumps(env))
        tampered["effective"]["resolved_at_utc"] = bad
        try:
            found = mms.validate_main_route({"expected_model_path": GLM, "model_selection": tampered}, cfg)
        except TypeError as exc:
            ERRORS.append(f"bad timestamp {bad!r} raised TypeError: {exc}")
            continue
        expect("session_packet_unreadable" in codes(found), f"bad timestamp {bad!r} is a finding")
    stale = json.loads(json.dumps(env))
    stale["effective"]["resolved_at_utc"] = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat().replace("+00:00", "Z")
    expect("session_packet_stale" in codes(mms.validate_main_route(
        {"expected_model_path": GLM, "model_selection": stale}, cfg)), "stale packet fails closed")
    future = json.loads(json.dumps(env))
    future["effective"]["resolved_at_utc"] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    expect("session_packet_future" in codes(mms.validate_main_route(
        {"expected_model_path": GLM, "model_selection": future}, cfg)), "future packet fails closed")


def test_drift_alias_legacy_and_unreadable() -> None:
    cfg_a = cfg_main("openai/gpt-6-astra")
    cfg_b = cfg_main("xai/grok-4.6")
    env = mms.resolve_effective(cfg_a)
    found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                     "model_selection": env}, cfg_b)
    expect("main_selection_config_drift" in codes(found),
           "config drift between build and validate fails closed")
    expect(mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                    "model": "openai/gpt-6-astra"}, cfg_a) == [],
           "legacy handmade packet matching configured model validates conservatively")
    found = mms.validate_main_route({"expected_model_path": "x/y", "model": "x/y"}, cfg_a)
    expect({"main_model_invalid", "main_live_model_mismatch"} <= codes(found),
           "legacy compat codes kept when expected differs from configured")
    found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                     "model": "other/model"}, cfg_a)
    expect("model_alias_mismatch" in codes(found), "alias must equal expected when present")
    found = mms.validate_main_route({"expected_model_path": "x/y", "session_pin": {"model": "x/y"}}, cfg_a)
    expect("session_pin_without_envelope" in codes(found), "pin claim without envelope never accepted")
    found = mms.validate_main_route({"expected_model_path": None}, TMP / "does-not-exist.json")
    expect("main_selection_unreadable" in codes(found), "read failure blocks, no historical fallback")
    sig = inspect.signature(mms.resolve_effective)
    expect("caller_model" not in sig.parameters and "model" not in sig.parameters,
           "bare --model has no parameter path into selection")
    allowed = {"schema", "agent_id", "configured", "effective"}
    expect(set(env.keys()) == allowed and "caller_model_claim_ignored" not in json.dumps(env),
           "no caller claim enters the trusted envelope")


def test_legacy_model_only_packets() -> None:
    cfg = cfg_main("openai/gpt-6-astra")
    expect(mms.validate_main_route({"model": "openai/gpt-6-astra"}, cfg) == [],
           "model-only packet matching configured validates")
    found = mms.validate_main_route({"model": "other/model"}, cfg)
    expect({"main_model_invalid", "main_live_model_mismatch"} <= codes(found),
           "model-only mismatch fails with compat codes")
    found = mms.validate_main_route({"expected_model_path": "openai/gpt-6-astra",
                                     "model": "other/model"}, cfg)
    expect("model_alias_mismatch" in codes(found), "differing alias and expected still flagged")
    expect(mms.validate_main_route({}, cfg) != [], "model-less main packet cannot validate")


def test_no_db_writes() -> None:
    db = make_db([(KEY, SID, "xai", "grok-4.6", "user", 1)])
    before = (db.stat().st_mtime_ns, db.stat().st_size)
    mms.SESSION_DB_PATH = db
    mms.resolve_effective(cfg_main("openai/gpt-6-astra"), session_key=KEY, session_id=SID)
    expect(before == (db.stat().st_mtime_ns, db.stat().st_size), "session reads never write the database")


def main() -> int:
    for test in (test_config_precedence_and_inherit, test_production_fallback_shape,
                 test_strict_model_tokens, test_config_malformed_matrix,
                 test_reference_keys_per_level, test_config_bytes_binding,
                 test_session_pin_and_negatives, test_forged_configured_envelope,
                 test_invalid_present_envelope_no_downgrade, test_forged_unpinned_hashes_and_transitions,
                 test_pin_reread_transitions, test_timestamp_robustness,
                 test_drift_alias_legacy_and_unreadable, test_legacy_model_only_packets,
                 test_no_db_writes):
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            ERRORS.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if ERRORS:
        for error in ERRORS:
            print(f"FAIL: {error}")
        return 1
    print("ok: main_model_selection tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
