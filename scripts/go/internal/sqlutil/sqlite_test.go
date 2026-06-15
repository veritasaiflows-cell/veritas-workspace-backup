package sqlutil

import (
	"database/sql"
	"path/filepath"
	"strings"
	"testing"
)

func TestQuoteIdentifierEscapesDoubleQuotes(t *testing.T) {
	got := QuoteIdentifier(`bad"name`)
	want := `"bad""name"`
	if got != want {
		t.Fatalf("QuoteIdentifier() = %q, want %q", got, want)
	}
}

func TestInProcessReadOnlyDriverReadsAndRejectsWrites(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.sqlite")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT); INSERT INTO items(name) VALUES ('alpha'), ('beta');"); err != nil {
		db.Close()
		t.Fatal(err)
	}
	db.Close()

	value, err := ScalarInProcess(dbPath, "SELECT COUNT(*) FROM items")
	if err != nil {
		t.Fatalf("ScalarInProcess() error = %v", err)
	}
	if value != "2" {
		t.Fatalf("ScalarInProcess() = %q, want 2", value)
	}

	rows, err := JSONRowsInProcess(dbPath, "SELECT id, name FROM items ORDER BY id")
	if err != nil {
		t.Fatalf("JSONRowsInProcess() error = %v", err)
	}
	if len(rows) != 2 || rows[0]["name"] != "alpha" || rows[1]["name"] != "beta" {
		t.Fatalf("JSONRowsInProcess() rows = %#v", rows)
	}

	count, err := TextRowCountInProcess(dbPath, "SELECT name FROM items")
	if err != nil {
		t.Fatalf("TextRowCountInProcess() error = %v", err)
	}
	if count != 2 {
		t.Fatalf("TextRowCountInProcess() = %d, want 2", count)
	}

	tableCount, err := TableRowCountInProcess(dbPath, "items")
	if err != nil {
		t.Fatalf("TableRowCountInProcess() error = %v", err)
	}
	if tableCount != 2 {
		t.Fatalf("TableRowCountInProcess() = %d, want 2", tableCount)
	}

	err = WriteProbeInProcess(dbPath)
	if err == nil {
		t.Fatal("WriteProbeInProcess() unexpectedly allowed write")
	}
}

func TestInProcessDriverErrorsAreSurfaced(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "test.sqlite")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("CREATE TABLE items(id INTEGER PRIMARY KEY);"); err != nil {
		db.Close()
		t.Fatal(err)
	}
	db.Close()

	if _, err := ScalarInProcess(dbPath, "SELECT * FROM missing_table"); err == nil {
		t.Fatal("ScalarInProcess() expected missing-table error")
	}
	if _, err := ScalarInProcess(filepath.Join(t.TempDir(), "missing.sqlite"), "SELECT 1"); err == nil {
		t.Fatal("ScalarInProcess() expected missing-db error")
	}
}

func TestDriverDispatchRejectsUnknownDriver(t *testing.T) {
	if err := ValidateDriver("bogus"); err == nil {
		t.Fatal("ValidateDriver() expected error")
	}
	_, err := ScalarWithDriver("bogus", "sqlite3", "db.sqlite", "SELECT 1")
	if err == nil || !strings.Contains(err.Error(), "unsupported sqlite driver") {
		t.Fatalf("ScalarWithDriver() error = %v, want unsupported driver", err)
	}
}
