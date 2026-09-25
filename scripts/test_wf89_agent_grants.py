#!/usr/bin/env python3
"""Tests for wf89_agent_grants (synthetic configs only; never reads live config)."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from wf89_agent_grants import UNPROVENANCED, approve, check, init_ledger, notable, record  # noqa: E402

SECRET = "s3cr3t-value-never-in-ledger"


def base_config() -> dict:
    return {
        "agents": {
            "defaults": {"maxConcurrent": 4, "subagents": {"maxConcurrent": 8}},
            "entries": {
                "main": {"workspace": "W", "subagents": {"allowAgents": ["scout"]}},
                "scout": {"name": "Scout", "identity": {"name": "S"}, "model": {"primary": "m1"},
                          "tools": {"allow": ["read", "web_fetch"], "deny": ["exec", "write"],
                                    "elevated": {"enabled": False}, "fs": {"workspaceOnly": True}}},
                "builder": {"model": {"primary": "m2"},
                            "tools": {"allow": ["read", "write", "exec"], "fs": {"workspaceOnly": False},
                                      "exec": {"host": "sandbox"}},
                            "sandbox": {"mode": "all", "backend": "docker", "workspaceAccess": "none",
                                        "docker": {"dangerouslyAllowExternalBindSources": True,
                                                   "readOnlyRoot": True, "network": "none",
                                                   "user": "65534:65534", "capDrop": ["ALL"],
                                                   "env": {"TOKENISH": SECRET},
                                                   "binds": ["C:\\src:/role:ro", "C:\\wt:/worktree:rw"]}}},
            },
        },
        "tools": {"profile": "coding", "agentToAgent": {"enabled": True, "allow": ["main", "scout"]},
                  "sessions": {"visibility": "all"}},
    }


PROV = {"builder": {"docker.dangerouslyAllowExternalBindSources": "Randall 2026-09-24 14:03 option B"}}


class GrantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = base_config()
        self.ledger = init_ledger(self.cfg, PROV, "test baseline")

    def test_clean_config_has_no_drift(self) -> None:
        res = check(self.cfg, self.ledger)
        self.assertEqual(res["drift"], [])
        self.assertIn(res["status"], ("PASS", "WARN"))

    def test_approved_override_carries_its_approval(self) -> None:
        n = self.ledger["agents"]["builder"]["notable"]
        self.assertEqual(n["docker.dangerouslyAllowExternalBindSources"]["approval_ref"],
                         "Randall 2026-09-24 14:03 option B")
        self.assertTrue(n["tools.write"]["approval_ref"].startswith(UNPROVENANCED))

    def test_planted_bind_mode_drift_fails_with_path(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["builder"]["sandbox"]["docker"]["binds"][0] = "C:\\src:/role:rw"
        res = check(cfg, self.ledger)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("~sandbox.docker.binds", res["drift"][0]["paths"])

    def test_workspace_access_rw_is_notable_and_fails(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["builder"]["sandbox"]["workspaceAccess"] = "rw"
        res = check(cfg, self.ledger)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["drift"][0]["notable_now"]["sandbox.workspaceAccess"], "rw")

    def test_tool_grant_added_to_scout_fails(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["scout"]["tools"]["allow"].append("write")
        res = check(cfg, self.ledger)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("unsandboxed.write_or_exec", res["drift"][0]["notable_now"])

    def test_agent_added_and_removed_fail(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["newbie"] = {"model": {"primary": "m"}}
        del cfg["agents"]["entries"]["scout"]
        kinds = {d["drift"] for d in check(cfg, self.ledger)["drift"]}
        self.assertEqual(kinds, {"agent_added", "agent_removed"})

    def test_global_reach_change_fails(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["tools"]["agentToAgent"]["allow"].append("builder")
        res = check(cfg, self.ledger)
        self.assertEqual(res["drift"][0]["agent"], "_global")

    def test_cosmetic_identity_change_is_not_drift(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["scout"]["identity"]["name"] = "Renamed"
        self.assertEqual(check(cfg, self.ledger)["drift"], [])

    def test_env_secret_never_stored_but_change_detected(self) -> None:
        self.assertNotIn(SECRET, json.dumps(self.ledger))
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["builder"]["sandbox"]["docker"]["env"]["TOKENISH"] = "other"
        res = check(cfg, self.ledger)
        self.assertEqual(res["status"], "FAIL")
        self.assertNotIn(SECRET, json.dumps(res))

    def test_record_refuses_new_notable_without_approval(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["builder"]["sandbox"]["docker"]["network"] = "bridge"
        with self.assertRaises(PermissionError):
            record(cfg, self.ledger, "builder", "try", None)

    def test_record_with_approval_clears_drift_and_keeps_old_refs(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["builder"]["sandbox"]["docker"]["network"] = "bridge"
        new = record(cfg, self.ledger, "builder", "net change", "Randall test approval")
        self.assertEqual(check(cfg, new)["drift"], [])
        n = new["agents"]["builder"]["notable"]
        self.assertEqual(n["docker.network"]["approval_ref"], "Randall test approval")
        self.assertEqual(n["docker.dangerouslyAllowExternalBindSources"]["approval_ref"],
                         "Randall 2026-09-24 14:03 option B")
        self.assertEqual(new["history"][-1]["paths"], ["~sandbox.docker.network"])

    def test_non_notable_change_records_without_approval(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["scout"]["model"]["primary"] = "m9"
        new = record(cfg, self.ledger, "scout", "model pin change", None)
        self.assertEqual(check(cfg, new)["drift"], [])

    def test_notable_flags_for_hardening_regressions(self) -> None:
        g = copy.deepcopy(self.cfg["agents"]["entries"]["builder"])
        g["sandbox"]["docker"].update(readOnlyRoot=False, capDrop=[], user="0:0")
        flags = notable("builder", g)
        for f in ("docker.readOnlyRoot!=true", "docker.capDrop!=ALL", "docker.user=root"):
            self.assertIn(f, flags)

    def test_approve_attaches_ref_and_clears_warning(self) -> None:
        new = approve(self.cfg, self.ledger, "builder", "tools.write", "Randall test ok")
        self.assertEqual(new["agents"]["builder"]["notable"]["tools.write"]["approval_ref"], "Randall test ok")
        self.assertNotIn(("builder", "tools.write"),
                         {(w["agent"], w["notable"]) for w in check(self.cfg, new)["unprovenanced_notable"]})
        self.assertEqual(new["history"][-1]["action"], "approve")

    def test_approve_refuses_drifted_value_and_fake_refs(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["agents"]["entries"]["builder"]["tools"]["allow"].append("edit")
        with self.assertRaises(PermissionError):
            approve(cfg, self.ledger, "builder", "tools.write", "Randall")
        with self.assertRaises(ValueError):
            approve(self.cfg, self.ledger, "builder", "tools.write", UNPROVENANCED + ": x")
        with self.assertRaises(ValueError):
            approve(self.cfg, self.ledger, "scout", "tools.write", "Randall")


if __name__ == "__main__":
    unittest.main(verbosity=2)
