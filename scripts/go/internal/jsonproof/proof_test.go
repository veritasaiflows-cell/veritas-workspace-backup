package jsonproof

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestRunAcceptsCleanPacket(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/good.json", `{
  "schema_version": "fixture.v1",
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {
    "review_only": true,
    "paper_or_live_execution_allowed": false,
    "owner_approval_inferred": false
  }
}`)
	report := Run(Options{
		Root:        root,
		Packets:     []string{"tmp/good.json"},
		MaxAgeHours: 24,
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
	})
	if report.Status != "ok" {
		t.Fatalf("status=%s critical=%d warnings=%d", report.Status, report.Summary.Critical, report.Summary.Warnings)
	}
}

func TestRunBlocksForbiddenAuthority(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/bad.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"owner_approval_inferred": true}
}`)
	report := Run(Options{
		Root:        root,
		Packets:     []string{"tmp/bad.json"},
		MaxAgeHours: 24,
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
	})
	if report.Status != "blocked" || report.Summary.Critical == 0 {
		t.Fatalf("expected blocked, got status=%s critical=%d", report.Status, report.Summary.Critical)
	}
}

func TestRunWarnsOnStalePacket(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/stale.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-20T00:00:00Z",
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"review_only": true}
}`)
	report := Run(Options{
		Root:        root,
		Packets:     []string{"tmp/stale.json"},
		MaxAgeHours: 24,
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
	})
	if report.Status != "warning" || report.Summary.StalePackets != 1 {
		t.Fatalf("expected warning stale=1, got status=%s stale=%d", report.Status, report.Summary.StalePackets)
	}
}

func write(t *testing.T, root, rel, content string) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func mustTime(t *testing.T, value string) time.Time {
	t.Helper()
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		t.Fatal(err)
	}
	return parsed
}
