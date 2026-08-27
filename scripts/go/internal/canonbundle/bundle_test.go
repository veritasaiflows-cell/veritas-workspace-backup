package canonbundle

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestRunAcceptsCleanBundle(t *testing.T) {
	root := t.TempDir()
	createCanonDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), 2)
	write(t, root, "tmp/sql-canon-consumer-inventory.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "summary": {"backlog_count": 2},
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"inventory_only": true, "sql_writes_performed": false, "owner_approval_inferred": false}
}`)
	write(t, root, "tmp/packet.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"review_only": true, "paper_or_live_execution_allowed": false}
}`)
	report := Run(Options{
		Root:         root,
		Driver:       "inprocess",
		ProofPackets: []string{"tmp/packet.json"},
		Now:          mustTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours:  24,
	})
	if report.Status != "ok" {
		t.Fatalf("status=%s critical=%d warnings=%d findings=%v", report.Status, report.Summary.Critical, report.Summary.Warnings, report.Findings)
	}
}

func TestRunBlocksConsumerRegistryDrift(t *testing.T) {
	root := t.TempDir()
	createCanonDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), 2)
	write(t, root, "tmp/sql-canon-consumer-inventory.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "summary": {"backlog_count": 3},
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"inventory_only": true}
}`)
	write(t, root, "tmp/packet.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"review_only": true}
}`)
	report := Run(Options{
		Root:         root,
		Driver:       "inprocess",
		ProofPackets: []string{"tmp/packet.json"},
		Now:          mustTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours:  24,
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
}

func TestRunAllowsRetainedHistoricalConsumerRegistryRows(t *testing.T) {
	root := t.TempDir()
	createCanonDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), 3)
	write(t, root, "tmp/sql-canon-consumer-inventory.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "summary": {"backlog_count": 2},
  "validation": {"status": "ok", "errors": [], "warnings": []},
  "authority_boundary": {"inventory_only": true}
}`)
	write(t, root, "tmp/packet.json", `{
  "status": "ok",
  "generated_at_utc": "2026-06-22T00:00:00Z",
  "validation": {"status":"ok", "errors": [], "warnings": []},
  "authority_boundary": {"review_only": true}
}`)
	report := Run(Options{
		Root:         root,
		Driver:       "inprocess",
		ProofPackets: []string{"tmp/packet.json"},
		Now:          mustTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours:  24,
	})
	if report.Status != "ok" {
		t.Fatalf("expected retained historical rows to pass, got %s findings=%v", report.Status, report.Findings)
	}
}

func createCanonDB(t *testing.T, path string, consumerRows int) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	exec(t, db, "CREATE TABLE securities(id INTEGER)")
	exec(t, db, "CREATE TABLE reference_levels(id INTEGER)")
	exec(t, db, "CREATE TABLE evidence_freshness(id INTEGER)")
	exec(t, db, "CREATE TABLE evidence_status(id INTEGER)")
	exec(t, db, "CREATE TABLE tier_routing_state(id INTEGER)")
	exec(t, db, "CREATE TABLE universe_membership(id INTEGER)")
	exec(t, db, "CREATE TABLE answer_path_scope(id INTEGER)")
	exec(t, db, "CREATE TABLE source_lineage(id INTEGER)")
	exec(t, db, "CREATE TABLE consumer_migration_registry(id INTEGER)")
	exec(t, db, "CREATE TABLE audit_events(id INTEGER)")
	exec(t, db, "CREATE TABLE authority_events(id INTEGER)")
	exec(t, db, "CREATE TABLE migration_validation_runs(id INTEGER)")
	exec(t, db, "CREATE TABLE validator_runs(id INTEGER)")
	for _, table := range []string{"securities", "reference_levels", "evidence_freshness", "evidence_status", "tier_routing_state", "universe_membership", "answer_path_scope"} {
		insertRows(t, db, table, 200)
	}
	insertRows(t, db, "source_lineage", 1)
	insertRows(t, db, "consumer_migration_registry", consumerRows)
	exec(t, db, "CREATE VIEW current_active_universe AS SELECT * FROM securities")
	exec(t, db, "CREATE VIEW current_sql_canon_routing AS SELECT * FROM securities")
	exec(t, db, "CREATE VIEW current_answer_path AS SELECT * FROM securities LIMIT 0")
	exec(t, db, "CREATE VIEW review_monitor_universe AS SELECT * FROM securities LIMIT 158")
}

func insertRows(t *testing.T, db *sql.DB, table string, count int) {
	t.Helper()
	tx, err := db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < count; i++ {
		if _, err := tx.Exec(fmt.Sprintf("INSERT INTO %s(id) VALUES (?)", table), i); err != nil {
			t.Fatal(err)
		}
	}
	if err := tx.Commit(); err != nil {
		t.Fatal(err)
	}
}

func exec(t *testing.T, db *sql.DB, query string) {
	t.Helper()
	if _, err := db.Exec(query); err != nil {
		t.Fatalf("%s: %v", query, err)
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
