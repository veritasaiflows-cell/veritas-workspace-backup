package pmlint

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestMissingPacketWarnsUnlessRequired(t *testing.T) {
	root := t.TempDir()
	report := Run(Options{Root: root})
	if report.Status != "warning" {
		t.Fatalf("expected warning for missing optional packet, got %s", report.Status)
	}
	if !report.Summary.PacketMissing {
		t.Fatalf("expected packet_missing summary")
	}

	required := Run(Options{Root: root, Require: true})
	if required.Status != "blocked" {
		t.Fatalf("expected blocked for missing required packet, got %s", required.Status)
	}
}

func TestRunWarnsForStaleReviewOnlyQueueResidue(t *testing.T) {
	root := t.TempDir()
	mustWritePMJSON(t, filepath.Join(root, "tmp", "pm-control-packet.json"), map[string]any{
		"schema":           "veritas.pm_control_packet.v1",
		"status":           "ok",
		"generated_at_utc": "2026-06-22T02:00:00Z",
		"summary": map[string]any{
			"pm_readiness": map[string]any{
				"stale_lanes":            1,
				"blocked_lanes":          0,
				"needs_validation_lanes": 0,
			},
			"stale_lane_digest": map[string]any{
				"stale_lane_count": 1,
				"lanes": []any{
					map[string]any{
						"lane_id":        "retail_truth_routing",
						"top_job_id":     "pm-retail-truth-routing-refresh-artifact",
						"proof_commands": []any{"python scripts\\retail_truth_routing_contract.py --write --validate"},
					},
				},
			},
			"implementation_queue": map[string]any{
				"ready_job_count":                     1,
				"blocked_job_count":                   0,
				"owner_decision_job_count":            0,
				"auto_main_executable_job_count":      1,
				"auto_cron_executable_job_count":      1,
				"auto_heartbeat_executable_job_count": 0,
			},
		},
		"sections": map[string]any{
			"pm_implementation_job_queue": map[string]any{
				"jobs": []any{
					map[string]any{
						"job_id":                     "pm-safe-proof",
						"proof_only":                 true,
						"auto_main_may_execute":      true,
						"auto_cron_may_execute":      true,
						"auto_heartbeat_may_execute": false,
						"owner_gate_required":        false,
						"stop_lines":                 []any{"no owner approval inference"},
						"authority_boundary": map[string]any{
							"review_only":                     true,
							"paper_or_live_execution_allowed": false,
							"owner_approval_inferred":         false,
						},
						"automation_capabilities": map[string]any{
							"proof_only":            true,
							"unsafe_proof_commands": []any{},
						},
					},
				},
			},
			"pm_main_session_handoff": map[string]any{
				"status": "ready_for_main_session",
				"selected_action": map[string]any{
					"authority":                "review_only",
					"inline_execution_allowed": false,
					"heartbeat_may_execute":    false,
					"stop_lines":               []any{"no paper/live/account action"},
				},
				"signal_classification": map[string]any{
					"class":                   "MAIN_SESSION_REQUIRED",
					"heartbeat_may_execute":   false,
					"owner_decision_required": false,
				},
				"validation": map[string]any{
					"status":   "ok",
					"errors":   []any{},
					"warnings": []any{},
				},
			},
		},
		"authority_boundary": map[string]any{
			"review_only":                           true,
			"paper_or_live_execution_allowed":       false,
			"owner_approval_inferred":               false,
			"customer_or_external_delivery_allowed": false,
		},
		"validation": map[string]any{
			"status":   "ok",
			"errors":   []any{},
			"warnings": []any{},
		},
	})

	report := Run(Options{
		Root:        root,
		MaxAgeHours: 6,
		Now:         time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "warning" {
		t.Fatalf("expected warning for stale lane residue, got %s: %#v", report.Status, report.Summary)
	}
	if report.Summary.Critical != 0 {
		t.Fatalf("expected no criticals, got %#v", report.Summary)
	}
	if report.Summary.StaleLaneCount != 1 || report.Summary.DetailJobCount != 1 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestRunBlocksOwnerGatedAutoExecution(t *testing.T) {
	root := t.TempDir()
	mustWritePMJSON(t, filepath.Join(root, "tmp", "pm-control-packet.json"), map[string]any{
		"schema":           "veritas.pm_control_packet.v1",
		"status":           "ok",
		"generated_at_utc": "2026-06-22T02:00:00Z",
		"summary": map[string]any{
			"pm_readiness": map[string]any{},
			"stale_lane_digest": map[string]any{
				"stale_lane_count": 0,
				"lanes":            []any{},
			},
			"implementation_queue": map[string]any{
				"auto_heartbeat_executable_job_count": 0,
			},
		},
		"sections": map[string]any{
			"pm_implementation_job_queue": map[string]any{
				"jobs": []any{
					map[string]any{
						"job_id":                "pm-unsafe-owner-gate",
						"proof_only":            false,
						"auto_main_may_execute": true,
						"owner_gate_required":   true,
						"stop_lines":            []any{"owner approval required"},
						"authority_boundary": map[string]any{
							"review_only": true,
						},
						"automation_capabilities": map[string]any{
							"proof_only":            false,
							"owner_gate_required":   true,
							"unsafe_proof_commands": []any{"python scripts\\unsafe.py --apply"},
						},
					},
				},
			},
			"pm_main_session_handoff": map[string]any{
				"status": "not_needed",
				"validation": map[string]any{
					"status": "ok",
					"errors": []any{},
				},
			},
		},
		"authority_boundary": map[string]any{
			"review_only":                     true,
			"owner_approval_inferred":         false,
			"paper_or_live_execution_allowed": false,
		},
		"validation": map[string]any{
			"status": "ok",
			"errors": []any{},
		},
	})

	report := Run(Options{
		Root:        root,
		MaxAgeHours: 6,
		Now:         time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s: %#v", report.Status, report.Summary)
	}
	if report.Summary.OwnerGateAutoExecutionCount != 1 || report.Summary.UnsafeAutoJobCount != 1 {
		t.Fatalf("expected unsafe owner-gated auto job counts, got %#v", report.Summary)
	}
}

func mustWritePMJSON(t *testing.T, path string, value any) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	bytes, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, bytes, 0o644); err != nil {
		t.Fatal(err)
	}
}
