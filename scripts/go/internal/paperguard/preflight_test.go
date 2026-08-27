package paperguard

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestRunWarnsOnMissingGuardUnlessRequireReady(t *testing.T) {
	root := t.TempDir()
	report := Run(Options{
		Root:            root,
		GuardPaths:      []string{"tmp/missing-guard.json"},
		KillSwitchPaths: []string{"tmp/missing-kill.json"},
		Now:             time.Date(2026, 6, 22, 0, 0, 0, 0, time.UTC),
	})
	if report.Status != "warning" {
		t.Fatalf("expected warning, got %s", report.Status)
	}
	readyReport := Run(Options{
		Root:            root,
		GuardPaths:      []string{"tmp/missing-guard.json"},
		KillSwitchPaths: []string{"tmp/missing-kill.json"},
		RequireReady:    true,
		Now:             time.Date(2026, 6, 22, 0, 0, 0, 0, time.UTC),
	})
	if readyReport.Status != "blocked" {
		t.Fatalf("expected blocked when require-ready, got %s", readyReport.Status)
	}
}

func TestRunDetectsLiveEndpointAndAuthorityFlag(t *testing.T) {
	root := t.TempDir()
	writeJSON(t, root, "tmp/guard.json", map[string]any{
		"status":                        "ok",
		"generated_at_utc":              "2026-06-22T00:00:00Z",
		"ready_for_paper_submit_cancel": true,
		"live_trading_allowed":          true,
		"endpoint":                      "https://api.alpaca.markets",
		"forbidden_live_endpoint":       "https://api.alpaca.markets",
	})
	writeJSON(t, root, "tmp/kill.json", map[string]any{
		"paper_only":     true,
		"endpoint":       "https://paper-api.alpaca.markets",
		"expires_at_utc": "2026-06-22T01:00:00Z",
	})
	report := Run(Options{
		Root:            root,
		GuardPaths:      []string{"tmp/guard.json"},
		KillSwitchPaths: []string{"tmp/kill.json"},
		Now:             time.Date(2026, 6, 22, 0, 0, 0, 0, time.UTC),
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.UnsafeTrueFlagCount != 1 || report.Summary.LiveEndpointHitCount != 1 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestRunRequireReadyAcceptsFreshPaperOnlyGuard(t *testing.T) {
	root := t.TempDir()
	writeJSON(t, root, "tmp/guard.json", map[string]any{
		"status":                        "ok",
		"ready_for_paper_submit_cancel": true,
		"endpoint":                      "https://paper-api.alpaca.markets",
		"live_trading_allowed":          false,
		"owner_approval_inferred":       false,
	})
	writeJSON(t, root, "tmp/kill.json", map[string]any{
		"paper_only":     true,
		"endpoint":       "https://paper-api.alpaca.markets",
		"expires_at_utc": "2026-06-22T01:00:00Z",
	})
	report := Run(Options{
		Root:            root,
		GuardPaths:      []string{"tmp/guard.json"},
		KillSwitchPaths: []string{"tmp/kill.json"},
		RequireReady:    true,
		Now:             time.Date(2026, 6, 22, 0, 0, 0, 0, time.UTC),
	})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %#v", report.Status, report.Summary)
	}
}

func writeJSON(t *testing.T, root, rel string, value any) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
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
