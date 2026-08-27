package crossdb

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func TestCrossDBCleanFixture(t *testing.T) {
	root := t.TempDir()
	createCrossCanonDB(t, root, []string{"AAA", "BBB"}, []string{"AAA", "BBB"})
	createCrossFinanceStateDB(t, root, []string{"AAA", "BBB"})
	createCrossCanonCacheDB(t, root, []string{"AAA", "BBB"})
	createCrossWF84DB(t, root, []string{"AAA", "BBB"})

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s critical=%d warnings=%d findings=%+v", report.Status, report.Summary.Critical, report.Summary.Warnings, report.Findings)
	}
}

func TestCrossDBBlocksRequiredTickerDrift(t *testing.T) {
	root := t.TempDir()
	createCrossCanonDB(t, root, []string{"AAA", "BBB"}, []string{"AAA"})

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.RequiredSourceDriftCount == 0 {
		t.Fatalf("expected required drift, got %+v", report.Summary)
	}
}

func createCrossCanonDB(t *testing.T, root string, baseTickers, referenceTickers []string) {
	t.Helper()
	path := filepath.Join(root, "state", "finance", "finance-canon.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openCrossDB(t, path)
	defer db.Close()
	statements := []string{
		`CREATE TABLE securities(ticker TEXT PRIMARY KEY, active INTEGER);`,
		`CREATE TABLE universe_membership(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE answer_path_scope(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE reference_levels(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE tier_routing_state(ticker TEXT PRIMARY KEY);`,
		`CREATE VIEW current_sql_canon_routing AS SELECT ticker FROM securities WHERE active=1;`,
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			t.Fatal(err)
		}
	}
	for _, ticker := range baseTickers {
		if _, err := db.Exec(`INSERT INTO securities VALUES (?, 1);`, ticker); err != nil {
			t.Fatal(err)
		}
		for _, table := range []string{"universe_membership", "answer_path_scope", "tier_routing_state"} {
			if _, err := db.Exec(`INSERT INTO `+table+` VALUES (?);`, ticker); err != nil {
				t.Fatal(err)
			}
		}
	}
	for _, ticker := range referenceTickers {
		if _, err := db.Exec(`INSERT INTO reference_levels VALUES (?);`, ticker); err != nil {
			t.Fatal(err)
		}
	}
}

func createCrossFinanceStateDB(t *testing.T, root string, tickers []string) {
	t.Helper()
	path := filepath.Join(root, "tmp", "finance-intelligence-state.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openCrossDB(t, path)
	defer db.Close()
	statements := []string{
		`CREATE TABLE universe(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE entry_stop_reference(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE card_registry(ticker TEXT PRIMARY KEY);`,
		`CREATE VIEW latest_valid_entry_stop_refs AS SELECT ticker FROM entry_stop_reference;`,
		`CREATE VIEW current_ticker_cards AS SELECT ticker FROM card_registry;`,
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			t.Fatal(err)
		}
	}
	for _, ticker := range tickers {
		for _, table := range []string{"universe", "entry_stop_reference", "card_registry"} {
			if _, err := db.Exec(`INSERT INTO `+table+` VALUES (?);`, ticker); err != nil {
				t.Fatal(err)
			}
		}
	}
}

func createCrossCanonCacheDB(t *testing.T, root string, tickers []string) {
	t.Helper()
	path := filepath.Join(root, "tmp", "veritas-canon-cache.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openCrossDB(t, path)
	defer db.Close()
	if _, err := db.Exec(`CREATE TABLE canon_cache_fields(scope TEXT, field_name TEXT);`); err != nil {
		t.Fatal(err)
	}
	for _, ticker := range tickers {
		for _, field := range []string{"reference_price_low", "reference_price_high", "reference_invalidation_level"} {
			if _, err := db.Exec(`INSERT INTO canon_cache_fields VALUES (?, ?);`, ticker, field); err != nil {
				t.Fatal(err)
			}
		}
	}
}

func createCrossWF84DB(t *testing.T, root string, tickers []string) {
	t.Helper()
	path := filepath.Join(root, "tmp", "canonical-finance-data-plane.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openCrossDB(t, path)
	defer db.Close()
	statements := []string{
		`CREATE TABLE security_master(ticker TEXT PRIMARY KEY, active INTEGER);`,
		`CREATE TABLE universe_membership(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE entry_stop_reference(ticker TEXT PRIMARY KEY);`,
		`CREATE TABLE full_answer_section_context(ticker TEXT, section_id TEXT);`,
		`CREATE VIEW v_current_decision_overview AS SELECT ticker FROM security_master WHERE active=1;`,
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			t.Fatal(err)
		}
	}
	for _, ticker := range tickers {
		if _, err := db.Exec(`INSERT INTO security_master VALUES (?, 1);`, ticker); err != nil {
			t.Fatal(err)
		}
		for _, table := range []string{"universe_membership", "entry_stop_reference"} {
			if _, err := db.Exec(`INSERT INTO `+table+` VALUES (?);`, ticker); err != nil {
				t.Fatal(err)
			}
		}
		if _, err := db.Exec(`INSERT INTO full_answer_section_context VALUES (?, 'thesis');`, ticker); err != nil {
			t.Fatal(err)
		}
	}
}

func openCrossDB(t *testing.T, path string) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	return db
}
