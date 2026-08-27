package jsonstruct

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestRunFlagsForbiddenAuthority(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/bad.json", `{"status":"ok","generated_at_utc":"2026-06-22T00:00:00Z","authority_boundary":{"owner_approval_inferred":true}}`)
	db := filepath.Join(root, "tmp", "veritas-artifact-index.sqlite")
	makeIndex(t, db, "tmp/bad.json")

	report := Run(Options{
		Root:        root,
		IndexPath:   "tmp/veritas-artifact-index.sqlite",
		Driver:      "inprocess",
		MaxAgeHours: 24,
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
	})
	if report.Status != "blocked" || report.Summary.AuthorityViolationCount == 0 {
		t.Fatalf("expected blocked authority violation, got status=%s violations=%d", report.Status, report.Summary.AuthorityViolationCount)
	}
}

func TestRunAllowsProtectiveOwnerApprovalRequiredFlag(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/protective.json", `{"status":"ok","generated_at_utc":"2026-06-22T00:00:00Z","authority_boundary":{"owner_approval_required_for_capital_deployment_or_execution":true,"trade_execution_allowed":false}}`)
	db := filepath.Join(root, "tmp", "veritas-artifact-index.sqlite")
	makeIndex(t, db, "tmp/protective.json")

	report := Run(Options{
		Root:        root,
		IndexPath:   "tmp/veritas-artifact-index.sqlite",
		Driver:      "inprocess",
		MaxAgeHours: 24,
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
	})
	if report.Status != "ok" || report.Summary.AuthorityViolationCount != 0 {
		t.Fatalf("expected ok protective authority flag, got status=%s violations=%d", report.Status, report.Summary.AuthorityViolationCount)
	}
}

func TestRunAcceptsCleanIndexedJSON(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/good.json", `{"status":"ok","schema_version":"fixture.v1","generated_at_utc":"2026-06-22T00:00:00Z","authority_boundary":{"owner_approval_inferred":false}}`)
	db := filepath.Join(root, "tmp", "veritas-artifact-index.sqlite")
	makeIndex(t, db, "tmp/good.json")

	report := Run(Options{
		Root:        root,
		IndexPath:   "tmp/veritas-artifact-index.sqlite",
		Driver:      "inprocess",
		MaxAgeHours: 24,
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
	})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got status=%s critical=%d warnings=%d", report.Status, report.Summary.Critical, report.Summary.Warnings)
	}
}

func makeIndex(t *testing.T, dbPath, relPath string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(dbPath), 0o755); err != nil {
		t.Fatal(err)
	}
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	_, err = db.Exec(`CREATE TABLE artifact_file_state (
source_file TEXT PRIMARY KEY,
artifact_type TEXT NOT NULL,
file_mtime_utc TEXT NOT NULL,
file_size INTEGER NOT NULL,
file_sha256 TEXT,
artifact_run_id INTEGER,
indexed_at_utc TEXT NOT NULL,
status TEXT NOT NULL DEFAULT 'indexed'
) STRICT;`)
	if err != nil {
		t.Fatal(err)
	}
	_, err = db.Exec(`INSERT INTO artifact_file_state(source_file, artifact_type, file_mtime_utc, file_size, file_sha256, indexed_at_utc, status) VALUES (?, 'test', '2026-06-22T00:00:00Z', 1, '', '2026-06-22T00:00:00Z', 'indexed')`, relPath)
	if err != nil {
		t.Fatal(err)
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
