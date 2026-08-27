package cronproof

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestRunClassifiesCronControlWarningsWithoutBlocking(t *testing.T) {
	root := t.TempDir()
	mustWriteJSON(t, filepath.Join(root, "state", "cron-contracts", "sample.json"), map[string]any{
		"schema":  "veritas.cron_contract.v1",
		"job_id":  "job-1",
		"name":    "Sample Cron",
		"enabled": true,
		"schedule": map[string]any{
			"kind": "cron",
			"expr": "0 7 * * *",
			"tz":   "America/Phoenix",
		},
		"expected_artifacts": []string{"tmp/sample-proof.json"},
		"authority_boundary": map[string]any{
			"review_only":                     true,
			"cron_schedule_mutation_allowed":  false,
			"paper_or_live_execution_allowed": false,
			"owner_approval_inferred":         false,
		},
	})
	mustWriteJSON(t, filepath.Join(root, "tmp", "sample-proof.json"), map[string]any{"status": "ok"})
	mustWriteJSON(t, filepath.Join(root, "tmp", "cron-control-packet.json"), map[string]any{
		"status":           "error",
		"generated_at_utc": "2026-06-22T02:00:00Z",
		"summary": map[string]any{
			"blocked_count":           1,
			"escalation_signal_count": 1,
		},
		"authority_boundary": map[string]any{
			"review_only":                     true,
			"cron_schedule_mutation_allowed":  false,
			"paper_or_live_execution_allowed": false,
			"owner_approval_inferred":         false,
		},
		"validation": map[string]any{
			"errors": []any{"freshness_status_not_ok"},
		},
		"freshness": map[string]any{
			"status": "blocked",
			"validation": map[string]any{
				"errors": []any{"blocked_signals_present"},
			},
		},
	})

	report := Run(Options{
		Root:        root,
		MaxAgeHours: 96,
		Now:         time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "warning" {
		t.Fatalf("expected warning, got %s: %#v", report.Status, report.Summary)
	}
	if report.Summary.ContractCount != 1 || report.Summary.EnabledContractCount != 1 {
		t.Fatalf("unexpected contract summary: %#v", report.Summary)
	}
	if report.Summary.ControlValidationErrorCount != 1 {
		t.Fatalf("expected control validation error count 1, got %#v", report.Summary)
	}
}

func TestRunBlocksForbiddenCronAuthority(t *testing.T) {
	root := t.TempDir()
	mustWriteJSON(t, filepath.Join(root, "state", "cron-contracts", "sample.json"), map[string]any{
		"schema":  "veritas.cron_contract.v1",
		"job_id":  "job-1",
		"name":    "Sample Cron",
		"enabled": true,
		"schedule": map[string]any{
			"kind": "cron",
			"expr": "0 7 * * *",
			"tz":   "America/Phoenix",
		},
		"expected_artifacts": []string{},
		"authority_boundary": map[string]any{
			"review_only":                    true,
			"cron_schedule_mutation_allowed": true,
		},
	})
	mustWriteJSON(t, filepath.Join(root, "tmp", "cron-control-packet.json"), map[string]any{
		"status":           "ok",
		"generated_at_utc": "2026-06-22T02:00:00Z",
		"summary":          map[string]any{},
		"authority_boundary": map[string]any{
			"review_only":                    true,
			"cron_schedule_mutation_allowed": false,
		},
		"validation": map[string]any{},
		"freshness":  map[string]any{"status": "ok", "validation": map[string]any{}},
	})
	report := Run(Options{
		Root:        root,
		MaxAgeHours: 96,
		Now:         time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
}

func TestRunFlagsPromptBloatAndDeliveryMismatch(t *testing.T) {
	root := t.TempDir()
	longMessage := strings.Repeat("send telegram update\n", 8)
	mustWriteJSON(t, filepath.Join(root, "state", "cron-contracts", "sample.json"), map[string]any{
		"schema":  "veritas.cron_contract.v1",
		"job_id":  "job-1",
		"name":    "Sample Cron",
		"enabled": true,
		"schedule": map[string]any{
			"kind": "cron",
			"expr": "0 7 * * *",
			"tz":   "America/Phoenix",
		},
		"delivery": map[string]any{
			"mode":    "none",
			"channel": "last",
		},
		"payload": map[string]any{
			"kind":    "agentTurn",
			"message": longMessage,
		},
		"expected_artifacts": []string{"tmp/sample-proof.json"},
		"authority_boundary": map[string]any{
			"review_only":                     true,
			"cron_schedule_mutation_allowed":  false,
			"paper_or_live_execution_allowed": false,
			"owner_approval_inferred":         false,
		},
	})
	mustWriteJSON(t, filepath.Join(root, "tmp", "sample-proof.json"), map[string]any{"status": "ok"})
	mustWriteJSON(t, filepath.Join(root, "tmp", "cron-control-packet.json"), map[string]any{
		"status":           "ok",
		"generated_at_utc": "2026-06-22T02:00:00Z",
		"summary": map[string]any{
			"blocked_count":           0,
			"escalation_signal_count": 0,
		},
		"authority_boundary": map[string]any{
			"review_only":                     true,
			"sends_messages":                  false,
			"cron_schedule_mutation_allowed":  false,
			"paper_or_live_execution_allowed": false,
			"owner_approval_inferred":         false,
		},
		"validation": map[string]any{
			"errors": []any{},
		},
		"freshness": map[string]any{
			"status": "ok",
			"validation": map[string]any{
				"errors": []any{},
			},
			"jobs": []any{
				map[string]any{
					"id":           "job-1",
					"name":         "Sample Cron",
					"signal_class": "NO_REPLY",
					"expected_artifacts": []any{
						map[string]any{
							"path":            "tmp/sample-proof.json",
							"operator_action": "MAIN_HANDOFF_REQUIRED",
						},
					},
				},
			},
		},
	})

	report := Run(Options{
		Root:            root,
		MaxAgeHours:     96,
		MaxPromptChars:  40,
		MaxMessageLines: 3,
		Now:             time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "warning" {
		t.Fatalf("expected warning, got %s: %#v", report.Status, report.Summary)
	}
	if report.Summary.PromptBloatContractCount != 1 || report.Summary.MessageLineBloatContractCount != 1 {
		t.Fatalf("expected prompt and line bloat counts, got %#v", report.Summary)
	}
	if report.Summary.DeliveryMismatchCount == 0 || report.Summary.ControlDeliveryMismatchCount == 0 {
		t.Fatalf("expected contract and control delivery mismatch counts, got %#v", report.Summary)
	}
}

func mustWriteJSON(t *testing.T, path string, value any) {
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
