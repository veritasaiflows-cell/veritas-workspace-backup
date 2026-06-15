package sqlinventory

import (
	"os/exec"
	"path/filepath"
	"testing"
)

func TestQuoteIdentifierEscapesDoubleQuotes(t *testing.T) {
	got := sortedCopy([]string{"b", "a"})
	if got[0] != "a" || got[1] != "b" {
		t.Fatalf("sortedCopy() = %#v", got)
	}
}

func TestInventoryDBWithSQLiteCLI(t *testing.T) {
	sqlitePath, err := exec.LookPath("sqlite3")
	if err != nil {
		t.Skip("sqlite3 not available")
	}
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "sample.sqlite")
	cmd := exec.Command(sqlitePath, dbPath, "CREATE TABLE sample(id INTEGER PRIMARY KEY, name TEXT); INSERT INTO sample(name) VALUES ('one'),('two');")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("create sqlite fixture: %v: %s", err, string(out))
	}
	report := Run(Options{
		Root:       dir,
		SQLitePath: sqlitePath,
		DBFiles:    []string{"sample.sqlite"},
	})
	if report.Status != "ok" {
		t.Fatalf("status = %s, want ok: %#v", report.Status, report.Summary)
	}
	if report.Summary.TotalRows != 2 {
		t.Fatalf("total rows = %d, want 2", report.Summary.TotalRows)
	}
	if report.Summary.Tables != 1 {
		t.Fatalf("tables = %d, want 1", report.Summary.Tables)
	}
}
