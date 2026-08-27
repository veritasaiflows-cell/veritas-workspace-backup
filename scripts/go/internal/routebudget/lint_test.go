package routebudget

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestRouteBudgetLintCatchesMissingRequiredGoProofCommand(t *testing.T) {
	root := t.TempDir()
	writeJSON(t, root, "tmp/changed-file-validator-router.json", map[string]any{
		"status": "ok",
		"authority_boundary": map[string]any{
			"review_only":         true,
			"executes_validators": false,
		},
		"summary": map[string]any{
			"changed_path_count": 2,
			"recommended_budget": "shared",
		},
		"changed_paths": []any{
			"scripts/go/cmd/example/main.go",
			"scripts/go_fast_proof_validators.py",
		},
		"recommendations": []any{
			map[string]any{"command": "python scripts\\go_binary_freshness_guard.py --write --validate", "budget": "narrow"},
			map[string]any{"command": "python scripts\\test_go_fast_proof_validators.py", "budget": "narrow"},
			map[string]any{"command": "python scripts\\go_fast_proof_validators.py --write --validate", "budget": "shared"},
		},
	})
	writeJSON(t, root, "tmp/validator-bundle-router.json", map[string]any{
		"status": "ok",
		"mode":   "plan",
		"summary": map[string]any{
			"selected_budget":        "shared",
			"selected_command_count": 2,
			"executed_command_count": 0,
			"failed_command_count":   0,
		},
		"selected_validators": []any{
			map[string]any{"command": "python scripts\\go_binary_freshness_guard.py --write --validate"},
			map[string]any{"command": "python scripts\\test_go_fast_proof_validators.py"},
		},
		"command_safety": []any{
			map[string]any{"command": "python scripts\\go_binary_freshness_guard.py --write --validate", "allowed": true},
			map[string]any{"command": "python scripts\\test_go_fast_proof_validators.py", "allowed": true},
		},
	})
	writeJSON(t, root, "tmp/validator-timing-ledger.json", map[string]any{
		"status": "ok",
		"summary": map[string]any{
			"measured_validator_failures": []any{},
			"timing_collection_failures":  []any{},
		},
	})

	report := Run(Options{Root: root, AllowTimingWarns: true})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked report, got %s", report.Status)
	}
	if report.Summary.MissingRequiredCommandCount != 1 {
		t.Fatalf("expected one missing required command, got %+v", report.Summary)
	}
}

func TestRouteBudgetLintAllowsClassifiedTimingWarnings(t *testing.T) {
	root := t.TempDir()
	writeJSON(t, root, "tmp/changed-file-validator-router.json", map[string]any{
		"status": "ok",
		"authority_boundary": map[string]any{
			"review_only":         true,
			"executes_validators": false,
		},
		"summary":       map[string]any{"changed_path_count": 1, "recommended_budget": "narrow"},
		"changed_paths": []any{"scripts/go/cmd/example/main.go"},
		"recommendations": []any{
			map[string]any{"command": "python scripts\\go_binary_freshness_guard.py --write --validate", "budget": "narrow"},
		},
	})
	writeJSON(t, root, "tmp/validator-bundle-router.json", map[string]any{
		"status": "ok",
		"mode":   "plan",
		"summary": map[string]any{
			"selected_budget":        "narrow",
			"selected_command_count": 1,
			"executed_command_count": 0,
			"failed_command_count":   0,
		},
		"selected_validators": []any{
			map[string]any{"command": "python scripts\\go_binary_freshness_guard.py --write --validate"},
		},
		"command_safety": []any{
			map[string]any{"command": "python scripts\\go_binary_freshness_guard.py --write --validate", "allowed": true},
		},
	})
	writeJSON(t, root, "tmp/validator-timing-ledger.json", map[string]any{
		"status": "warning",
		"summary": map[string]any{
			"measured_validator_failures": []any{"cron_control_packet"},
			"timing_collection_failures":  []any{},
		},
	})

	report := Run(Options{Root: root, AllowTimingWarns: true})
	if report.Status != "warning" {
		t.Fatalf("expected warning report, got %s", report.Status)
	}
	if report.Summary.MeasuredValidatorFailureCount != 1 {
		t.Fatalf("expected timing warning count, got %+v", report.Summary)
	}
}

func writeJSON(t *testing.T, root, rel string, value any) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, append(bytes, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}
