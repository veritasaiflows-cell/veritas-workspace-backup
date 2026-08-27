package bandfreshness

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestBandFreshnessCleanFixture(t *testing.T) {
	root := t.TempDir()
	hash := writeSourceArtifact(t, root, "tmp/source.json", `{"status":"ok"}`)
	writeBoard(t, root)
	createBandCanonDB(t, root, hash, true)
	createFinanceStateDB(t, root, hash)
	createCanonCacheDB(t, root, hash)

	report := Run(Options{
		Root:        root,
		Driver:      "inprocess",
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours: 48,
	})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s critical=%d warnings=%d findings=%+v", report.Status, report.Summary.Critical, report.Summary.Warnings, report.Findings)
	}
	if report.Summary.HashMismatchCount != 0 || report.Summary.MissingLineageTickerCount != 0 {
		t.Fatalf("unexpected summary: %+v", report.Summary)
	}
}

func TestBandFreshnessBlocksMissingLineage(t *testing.T) {
	root := t.TempDir()
	hash := writeSourceArtifact(t, root, "tmp/source.json", `{"status":"ok"}`)
	writeBoard(t, root)
	createBandCanonDB(t, root, hash, false)

	report := Run(Options{
		Root:        root,
		Driver:      "inprocess",
		Now:         mustTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours: 48,
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.MissingLineageTickerCount == 0 {
		t.Fatalf("expected missing lineage, got %+v", report.Summary)
	}
}

func writeBoard(t *testing.T, root string) {
	t.Helper()
	path := filepath.Join(root, "03. Portfolio", "Execution Board.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("# Execution Board\n\nReview-only fixture.\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeSourceArtifact(t *testing.T, root, rel, content string) string {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(content))
	return hex.EncodeToString(sum[:])
}

func createBandCanonDB(t *testing.T, root, hash string, withLineage bool) {
	t.Helper()
	path := filepath.Join(root, "state", "finance", "finance-canon.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openFixtureDB(t, path)
	defer db.Close()
	statements := []string{
		`CREATE TABLE reference_levels(ticker TEXT PRIMARY KEY, reference_price_low REAL, reference_price_high REAL, reference_invalidation_level REAL, source_artifact_path TEXT, source_artifact_sha256 TEXT, source_generated_at_utc TEXT, authority_class TEXT, fallback_rule TEXT);`,
		`CREATE TABLE source_lineage(lineage_id TEXT PRIMARY KEY, scope TEXT, scope_key TEXT, field_family TEXT, field_name TEXT, source_artifact_path TEXT, source_artifact_sha256 TEXT, source_generated_at_utc TEXT, source_status TEXT, validator_status TEXT, authority_class TEXT, fallback_rule TEXT, inserted_at_utc TEXT);`,
		`INSERT INTO reference_levels VALUES ('AAA', 1.0, 2.0, 0.5, 'tmp/source.json', ?, '2026-06-22T00:00:00Z', 'reference_metadata_review_only_no_deployment_authority', 'fixture');`,
	}
	for _, statement := range statements[:2] {
		if _, err := db.Exec(statement); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := db.Exec(statements[2], hash); err != nil {
		t.Fatal(err)
	}
	if withLineage {
		for _, field := range referenceFieldNames {
			if _, err := db.Exec(`INSERT INTO source_lineage VALUES (?, 'ticker', 'AAA', 'reference_levels', ?, 'tmp/source.json', ?, '2026-06-22T00:00:00Z', 'ok', 'ok', 'reference_metadata_review_only_no_deployment_authority', 'fixture', '2026-06-22T00:00:00Z');`, "AAA-"+field, field, hash); err != nil {
				t.Fatal(err)
			}
		}
	}
}

func createFinanceStateDB(t *testing.T, root, hash string) {
	t.Helper()
	path := filepath.Join(root, "tmp", "finance-intelligence-state.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openFixtureDB(t, path)
	defer db.Close()
	if _, err := db.Exec(`CREATE TABLE entry_stop_reference(ticker TEXT PRIMARY KEY, entry_band_low REAL, entry_band_high REAL, stop_or_invalidation REAL, freshness_status TEXT, validation_status TEXT, source_artifact_path TEXT, source_artifact_hash TEXT, source_timestamp TEXT);
CREATE VIEW latest_valid_entry_stop_refs AS SELECT ticker, entry_band_low, entry_band_high, stop_or_invalidation, freshness_status, validation_status, source_artifact_path, source_artifact_hash, source_timestamp FROM entry_stop_reference WHERE validation_status='ok' AND freshness_status IN ('fresh','current');
INSERT INTO entry_stop_reference VALUES ('AAA', 1.0, 2.0, 0.5, 'fresh', 'ok', 'tmp/source.json', ?, '2026-06-22T00:00:00Z');`, hash); err != nil {
		t.Fatal(err)
	}
}

func createCanonCacheDB(t *testing.T, root, hash string) {
	t.Helper()
	path := filepath.Join(root, "tmp", "veritas-canon-cache.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db := openFixtureDB(t, path)
	defer db.Close()
	if _, err := db.Exec(`CREATE TABLE canon_cache_fields(scope TEXT, field_name TEXT, field_value TEXT, source_artifact_path TEXT, source_artifact_hash TEXT, sql_generated_at_utc TEXT, freshness_status TEXT, validator_status TEXT);
INSERT INTO canon_cache_fields VALUES ('AAA', 'reference_price_low', '1.0', 'tmp/source.json', ?, '2026-06-22T00:00:00Z', 'fresh', 'ok');
INSERT INTO canon_cache_fields VALUES ('AAA', 'reference_price_high', '2.0', 'tmp/source.json', ?, '2026-06-22T00:00:00Z', 'fresh', 'ok');
INSERT INTO canon_cache_fields VALUES ('AAA', 'reference_invalidation_level', '0.5', 'tmp/source.json', ?, '2026-06-22T00:00:00Z', 'fresh', 'ok');`, hash, hash, hash); err != nil {
		t.Fatal(err)
	}
}

func openFixtureDB(t *testing.T, path string) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	return db
}

func mustTime(t *testing.T, value string) time.Time {
	t.Helper()
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		t.Fatal(err)
	}
	return parsed
}
