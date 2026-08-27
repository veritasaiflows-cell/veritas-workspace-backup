package artifactfreshness

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestRunBlocksCriticalStaleFreshnessRow(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/a.json", `{"status":"ok"}`)
	dbPath := filepath.Join(root, "tmp", "veritas-artifact-index.sqlite")
	makeFreshnessIndex(t, dbPath, "tmp/a.json", 30, 24, "critical")

	report := Run(Options{
		Root:        root,
		IndexPath:   "tmp/veritas-artifact-index.sqlite",
		Driver:      "inprocess",
		MaxAgeHours: 168,
		Now:         mustTime(t, "2026-06-22T00:00:00Z"),
	})
	if report.Status != "blocked" || report.Summary.StaleCriticalCount != 1 {
		t.Fatalf("expected blocked stale critical, got status=%s stale=%d", report.Status, report.Summary.StaleCriticalCount)
	}
}

func TestRunAcceptsFreshRows(t *testing.T) {
	root := t.TempDir()
	write(t, root, "tmp/a.json", `{"status":"ok"}`)
	dbPath := filepath.Join(root, "tmp", "veritas-artifact-index.sqlite")
	makeFreshnessIndex(t, dbPath, "tmp/a.json", 1, 24, "critical")

	report := Run(Options{
		Root:        root,
		IndexPath:   "tmp/veritas-artifact-index.sqlite",
		Driver:      "inprocess",
		MaxAgeHours: 168,
		Now:         mustTime(t, "2026-06-22T00:00:00Z"),
	})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got status=%s critical=%d warnings=%d", report.Status, report.Summary.Critical, report.Summary.Warnings)
	}
}

func makeFreshnessIndex(t *testing.T, dbPath, relPath string, age, staleAfter float64, criticality string) {
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
	_, err = db.Exec(`CREATE TABLE source_freshness_rows (
id INTEGER PRIMARY KEY,
artifact_run_id INTEGER,
source_file TEXT NOT NULL,
source_key TEXT NOT NULL,
path TEXT,
classification TEXT,
trust_level TEXT,
criticality TEXT,
owner_layer TEXT,
usable_for_review INTEGER NOT NULL DEFAULT 0,
usable_for_presentation INTEGER NOT NULL DEFAULT 0,
usable_for_canonical_mutation INTEGER NOT NULL DEFAULT 0,
stop_line INTEGER NOT NULL DEFAULT 0,
generated_at_utc TEXT,
age_hours REAL,
stale_after_hours REAL,
confidence_ceiling TEXT,
raw_json TEXT NOT NULL DEFAULT '{}'
) STRICT;`)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`INSERT INTO artifact_file_state(source_file, artifact_type, file_mtime_utc, file_size, file_sha256, indexed_at_utc, status) VALUES (?, 'test', '2026-06-22T00:00:00Z', 1, '', '2026-06-22T00:00:00Z', 'indexed')`, relPath); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`INSERT INTO source_freshness_rows(source_file, source_key, path, classification, criticality, generated_at_utc, age_hours, stale_after_hours, stop_line) VALUES (?, 'fixture', ?, 'fresh', ?, '2026-06-22T00:00:00Z', ?, ?, 0)`, relPath, relPath, criticality, age, staleAfter); err != nil {
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
