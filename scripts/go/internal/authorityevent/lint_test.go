package authorityevent

import (
	"database/sql"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestRunValidatesAuthorityEvents(t *testing.T) {
	root := t.TempDir()
	dbPath := root + "/finance-canon.sqlite"
	db := createAuthorityTestDB(t, dbPath)
	defer db.Close()

	report := Run(Options{
		Root:   root,
		DBPath: dbPath,
		Driver: "inprocess",
		Now:    time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "warning" {
		t.Fatalf("expected warning for missing legacy artifact only, got %s: %#v", report.Status, report.Summary)
	}
	if report.Summary.AuthorityEventCount != 1 || report.Summary.ForbiddenAuthorityFlagCount != 0 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestRunBlocksFalseCapitalAuthority(t *testing.T) {
	root := t.TempDir()
	dbPath := root + "/finance-canon.sqlite"
	db := createAuthorityTestDB(t, dbPath)
	defer db.Close()
	if _, err := db.Exec(`UPDATE authority_events SET authority_boundary_json = '{"capital_deployment_allowed": true}'`); err != nil {
		t.Fatal(err)
	}

	report := Run(Options{
		Root:   root,
		DBPath: dbPath,
		Driver: "inprocess",
		Now:    time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
}

func TestRunAcceptsSupersededLegacyValidatorArtifact(t *testing.T) {
	root := t.TempDir()
	dbPath := root + "/finance-canon.sqlite"
	db := createAuthorityTestDB(t, dbPath)
	defer db.Close()
	if _, err := db.Exec(`
		UPDATE validator_runs
		SET name = 'ticker_card_100_validate_only',
			artifact_path = 'tmp/ticker-card-wf78-100-import-production42-validate-summary.json',
			status = 'not_required_superseded_by_ticker_card_refresh_gate'
		WHERE name = 'validator-1'
	`); err != nil {
		t.Fatal(err)
	}

	report := Run(Options{
		Root:   root,
		DBPath: dbPath,
		Driver: "inprocess",
		Now:    time.Date(2026, 6, 22, 3, 0, 0, 0, time.UTC),
	})
	if report.Status != "ok" {
		t.Fatalf("expected ok for superseded legacy validator row, got %s: %#v", report.Status, report.Summary)
	}
}

func createAuthorityTestDB(t *testing.T, dbPath string) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	stmts := []string{
		`CREATE TABLE authority_events (
			event_id TEXT PRIMARY KEY,
			event_time_utc TEXT NOT NULL,
			event_type TEXT NOT NULL,
			approval_source TEXT,
			approval_message_id TEXT,
			authority_boundary_json TEXT NOT NULL,
			detail_json TEXT NOT NULL
		);`,
		`CREATE TABLE audit_events (
			event_id TEXT PRIMARY KEY,
			event_time_utc TEXT NOT NULL,
			event_type TEXT NOT NULL,
			detail_json TEXT NOT NULL
		);`,
		`CREATE TABLE validator_runs (
			name TEXT PRIMARY KEY,
			artifact_path TEXT NOT NULL,
			status TEXT,
			generated_at_utc TEXT,
			summary_json TEXT NOT NULL
		);`,
		`CREATE TABLE migration_validation_runs (
			run_id TEXT PRIMARY KEY,
			run_time_utc TEXT NOT NULL,
			validator_name TEXT NOT NULL,
			status TEXT NOT NULL,
			artifact_path TEXT NOT NULL,
			detail_json TEXT NOT NULL
		);`,
		`INSERT INTO authority_events VALUES (
			'auth-1',
			'2026-06-22T02:00:00Z',
			'owner_approved_sql_field_family_canon_owner_promotion',
			'webchat',
			'msg-1',
			'{"capital_deployment_allowed": false, "paper_or_live_execution_allowed": false, "owner_approval_inferred": false}',
			'{"approval_reference": "test"}'
		);`,
		`INSERT INTO audit_events VALUES (
			'audit-1',
			'2026-06-22T02:01:00Z',
			'sql_field_family_canon_owner_promotion_applied',
			'{"approval_reference": "test", "fallback_retained": true}'
		);`,
		`INSERT INTO validator_runs VALUES (
			'validator-1',
			'tmp/missing-legacy-validator.json',
			'ok',
			'2026-06-22T02:02:00Z',
			'{"checks": 1}'
		);`,
		`INSERT INTO migration_validation_runs VALUES (
			'run-1',
			'2026-06-22T02:03:00Z',
			'validator-1',
			'ok',
			'tmp/missing-legacy-validator.json',
			'{"checks": 1}'
		);`,
	}
	for _, stmt := range stmts {
		if _, err := db.Exec(stmt); err != nil {
			t.Fatal(err)
		}
	}
	return db
}
