package consumerregistry

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestRunAcceptsCleanRegistry(t *testing.T) {
	root := t.TempDir()
	backlog := writeBacklog(t, root, []string{"scripts/a.py", "scripts/b.py"})
	createRegistryDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), []testRow{
		{path: "scripts/a.py", consumerType: "production_or_answer_path_consumer", priority: "P0", lane: "answer_path_parity_lane", cutover: "sql_primary_guarded", parity: 1, sha: sha256Text(backlog)},
		{path: "scripts/b.py", consumerType: "source_producer_or_loader", priority: "P1", lane: "source_loader_lane", cutover: "source_producer", parity: 0, sha: sha256Text(backlog)},
	})
	writeInventory(t, root, 2, 2)
	writeGuard(t, root, 2)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "ok" {
		t.Fatalf("status=%s critical=%d warnings=%d findings=%#v", report.Status, report.Summary.Critical, report.Summary.Warnings, report.Findings)
	}
	if report.Summary.RegistryCount != 2 || report.Summary.SourceHashMismatchCount != 0 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestRunBlocksFieldDrift(t *testing.T) {
	root := t.TempDir()
	backlog := writeBacklog(t, root, []string{"scripts/a.py"})
	createRegistryDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), []testRow{
		{path: "scripts/a.py", consumerType: "source_producer_or_loader", priority: "P0", lane: "source_loader_lane", cutover: "sql_primary_guarded", parity: 1, sha: sha256Text(backlog)},
	})
	writeInventory(t, root, 1, 1)
	writeGuard(t, root, 1)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "blocked" || report.Summary.FieldMismatchCount == 0 {
		t.Fatalf("expected field drift block, got status=%s summary=%#v", report.Status, report.Summary)
	}
}

func TestRunBlocksStaleBacklogHash(t *testing.T) {
	root := t.TempDir()
	writeBacklog(t, root, []string{"scripts/a.py"})
	createRegistryDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), []testRow{
		{path: "scripts/a.py", consumerType: "production_or_answer_path_consumer", priority: "P0", lane: "answer_path_parity_lane", cutover: "sql_primary_guarded", parity: 1, sha: "old"},
	})
	writeInventory(t, root, 1, 1)
	writeGuard(t, root, 1)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "blocked" || report.Summary.SourceHashMismatchCount == 0 {
		t.Fatalf("expected source hash block, got status=%s summary=%#v", report.Status, report.Summary)
	}
}

func TestRunWarnsForAdvisoryMissingTestConsumer(t *testing.T) {
	root := t.TempDir()
	writeBacklog(t, root, []string{"scripts/a.py", "scripts/test_new_parity_guard.py"})
	createRegistryDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), []testRow{
		{path: "scripts/a.py", consumerType: "production_or_answer_path_consumer", priority: "P0", lane: "answer_path_parity_lane", cutover: "sql_primary_guarded", parity: 1, sha: "old"},
	})
	writeInventory(t, root, 2, 2)
	writeGuard(t, root, 1)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "warning" || report.Summary.Critical != 0 || report.Summary.Warnings == 0 {
		t.Fatalf("expected advisory warning, got status=%s summary=%#v findings=%#v", report.Status, report.Summary, report.Findings)
	}
	if report.Summary.MissingRegistryCount != 1 {
		t.Fatalf("expected summary to retain raw missing count, got %#v", report.Summary)
	}
}

func TestRunAllowsHistoricalExtraRegistryRows(t *testing.T) {
	root := t.TempDir()
	backlog := writeBacklog(t, root, []string{"scripts/a.py", "scripts/b.py"})
	createRegistryDB(t, filepath.Join(root, "state", "finance", "finance-canon.sqlite"), []testRow{
		{path: "scripts/a.py", consumerType: "production_or_answer_path_consumer", priority: "P0", lane: "answer_path_parity_lane", cutover: "sql_primary_guarded", parity: 1, sha: sha256Text(backlog)},
		{path: "scripts/b.py", consumerType: "source_producer_or_loader", priority: "P1", lane: "source_loader_lane", cutover: "source_producer", parity: 0, sha: sha256Text(backlog)},
		{path: "scripts/retired.py", consumerType: "source_producer_or_loader", priority: "P2", lane: "source_loader_lane", cutover: "archived", parity: 0, sha: "old"},
	})
	writeInventory(t, root, 2, 2)
	writeGuard(t, root, 3)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "ok" {
		t.Fatalf("expected retained historical row to pass, got status=%s summary=%#v findings=%#v", report.Status, report.Summary, report.Findings)
	}
	if report.Summary.ExtraRegistryCount != 1 || report.Summary.SourceHashMismatchCount != 0 {
		t.Fatalf("unexpected summary for retained historical row: %#v", report.Summary)
	}
}

type testRow struct {
	path         string
	consumerType string
	priority     string
	lane         string
	cutover      string
	parity       int
	sha          string
}

func createRegistryDB(t *testing.T, path string, rows []testRow) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	exec(t, db, `CREATE TABLE consumer_migration_registry(
consumer_path TEXT PRIMARY KEY,
consumer_type TEXT NOT NULL,
priority TEXT NOT NULL,
migration_lane TEXT NOT NULL,
cutover_state TEXT NOT NULL,
fallback_required INTEGER NOT NULL,
parity_required INTEGER NOT NULL,
raw_sql_needs_review INTEGER NOT NULL,
source_artifact_path TEXT NOT NULL,
source_artifact_sha256 TEXT,
registered_at_utc TEXT NOT NULL
)`)
	for _, row := range rows {
		_, err := db.Exec(`INSERT INTO consumer_migration_registry VALUES (?, ?, ?, ?, ?, 1, ?, 0, 'tmp/sql-canon-consumer-migration-backlog.json', ?, ?)`,
			row.path, row.consumerType, row.priority, row.lane, row.cutover, row.parity, row.sha, time.Now().UTC().Format(time.RFC3339))
		if err != nil {
			t.Fatal(err)
		}
	}
}

func writeBacklog(t *testing.T, root string, paths []string) string {
	t.Helper()
	items := ""
	for idx, path := range paths {
		if idx > 0 {
			items += ","
		}
		consumerType := "source_producer_or_loader"
		priority := "P1"
		parity := "false"
		if path == "scripts/a.py" {
			consumerType = "production_or_answer_path_consumer"
			priority = "P0"
			parity = "true"
		} else if strings.HasPrefix(path, "scripts/test_") {
			consumerType = "test_or_parity_consumer"
			priority = "P2"
			parity = "false"
		}
		items += fmt.Sprintf(`{"path":%q,"priority":%q,"consumer_type":%q,"migration_action":"x","requires_parity_before_cutover":%s,"requires_typed_access_layer":true,"fallback_required":true,"raw_sql_needs_review":false}`, path, priority, consumerType, parity)
	}
	content := fmt.Sprintf(`{"schema_version":"sql_canon_consumer_migration_backlog.v1","generated_at_utc":"2026-06-22T00:00:00Z","status":"ready","summary":{"backlog_count":%d},"items":[%s],"validation":{"status":"ok","errors":[],"warnings":[]}}`, len(paths), items)
	write(t, root, "tmp/sql-canon-consumer-migration-backlog.json", content)
	return content
}

func writeInventory(t *testing.T, root string, consumers, backlog int) {
	t.Helper()
	write(t, root, "tmp/sql-canon-consumer-inventory.json", fmt.Sprintf(`{"schema_version":"sql_canon_consumer_inventory.v1","generated_at_utc":"2026-06-22T00:00:00Z","status":"ok","summary":{"consumer_count":%d,"backlog_count":%d},"validation":{"status":"ok","errors":[],"warnings":[]},"authority_boundary":{"inventory_only":true}}`, consumers, backlog))
}

func writeGuard(t *testing.T, root string, registryCount int) {
	t.Helper()
	write(t, root, "tmp/sql-canon-consumer-registry-guard.json", fmt.Sprintf(`{"schema_version":"sql_canon_consumer_registry_guard.v1","generated_at_utc":"2026-06-22T00:00:00Z","status":"ok","registry_count":%d,"validation":{"status":"ok","errors":[],"warnings":[]},"authority_boundary":{"read_only_validator":true}}`, registryCount))
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

func exec(t *testing.T, db *sql.DB, query string) {
	t.Helper()
	if _, err := db.Exec(query); err != nil {
		t.Fatal(err)
	}
}

func sha256Text(value string) string {
	sum := sha256.Sum256([]byte(value))
	return hex.EncodeToString(sum[:])
}
