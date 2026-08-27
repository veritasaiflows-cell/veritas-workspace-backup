package fieldfamilyparity

import (
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func TestFieldFamilyParityCleanFixture(t *testing.T) {
	root := t.TempDir()
	createFixtureDB(t, root)
	writeFixturePackets(t, root, 2, 4)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "ok" {
		t.Fatalf("expected ok report, got %s critical=%d warnings=%d findings=%+v", report.Status, report.Summary.Critical, report.Summary.Warnings, report.Findings)
	}
	if report.Summary.JSONCountMismatches != 0 {
		t.Fatalf("unexpected count mismatch: %+v", report.Summary)
	}
	if report.Summary.SourceHashNullCount != 0 {
		t.Fatalf("unexpected source hash null count: %+v", report.Summary)
	}
}

func TestFieldFamilyParityBlocksJSONCountDrift(t *testing.T) {
	root := t.TempDir()
	createFixtureDB(t, root)
	writeFixturePackets(t, root, 3, 4)

	report := Run(Options{Root: root, Driver: "inprocess"})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked report, got %s", report.Status)
	}
	if report.Summary.JSONCountMismatches == 0 {
		t.Fatalf("expected JSON count mismatch, got %+v", report.Summary)
	}
}

func createFixtureDB(t *testing.T, root string) {
	t.Helper()
	path := filepath.Join(root, "state", "finance", "finance-canon.sqlite")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	statements := []string{
		`CREATE TABLE securities(ticker TEXT PRIMARY KEY, name TEXT, instrument_type TEXT, active INTEGER);`,
		`CREATE TABLE universe_membership(ticker TEXT PRIMARY KEY, universe_scope TEXT, tier TEXT, monitoring_role TEXT, legacy_production_42 INTEGER, review_100_monitor INTEGER, decision_grade_eligible INTEGER, source_open_required INTEGER, promotion_required_before_action INTEGER, raw_json TEXT);`,
		`CREATE TABLE answer_path_scope(ticker TEXT PRIMARY KEY, answer_scope TEXT, production_card_generation_allowed INTEGER, source_open_required_before_claim INTEGER);`,
		`CREATE TABLE evidence_status(ticker TEXT PRIMARY KEY, has_production_card INTEGER, card_path TEXT, coverage_registry_member INTEGER, provider_status TEXT, recommendation_fields_allowed INTEGER, customer_output_allowed INTEGER, paper_or_live_execution_allowed INTEGER);`,
		`CREATE TABLE evidence_freshness(ticker TEXT PRIMARY KEY, source_artifact_path TEXT, source_artifact_sha256 TEXT);`,
		`CREATE TABLE reference_levels(ticker TEXT PRIMARY KEY, reference_price_low REAL, reference_price_high REAL, reference_invalidation_level REAL, source_artifact_path TEXT, source_artifact_sha256 TEXT);`,
		`CREATE TABLE tier_routing_state(ticker TEXT PRIMARY KEY, capital_deployment_approved INTEGER, trade_or_execution_approved INTEGER, source_artifact_path TEXT, source_artifact_sha256 TEXT);`,
		`CREATE TABLE source_lineage(lineage_id TEXT PRIMARY KEY, scope TEXT, scope_key TEXT, field_family TEXT, field_name TEXT, source_artifact_path TEXT, source_artifact_sha256 TEXT);`,
		`CREATE TABLE consumer_migration_registry(consumer_path TEXT PRIMARY KEY);`,
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			t.Fatal(err)
		}
	}
	for _, ticker := range []string{"AAA", "BBB"} {
		if _, err := db.Exec(`INSERT INTO securities VALUES (?, ?, 'operating_company', 1);`, ticker, ticker+" Inc."); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(`INSERT INTO universe_membership VALUES (?, 'test_scope', 'B', 'watch', 1, 0, 1, 1, 1, '{}');`, ticker); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(`INSERT INTO answer_path_scope VALUES (?, 'legacy_production_42', 1, 1);`, ticker); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(`INSERT INTO evidence_status VALUES (?, 1, 'card.json', 1, NULL, 1, 0, 0);`, ticker); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(`INSERT INTO evidence_freshness VALUES (?, 'tmp/evidence.json', 'hash-evidence');`, ticker); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(`INSERT INTO reference_levels VALUES (?, 1.0, 2.0, 0.5, 'tmp/reference.json', 'hash-reference');`, ticker); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(`INSERT INTO tier_routing_state VALUES (?, 0, 0, 'tmp/routing.json', 'hash-routing');`, ticker); err != nil {
			t.Fatal(err)
		}
		for _, family := range []string{"evidence_freshness", "reference_levels"} {
			if _, err := db.Exec(`INSERT INTO source_lineage VALUES (?, 'ticker', ?, ?, 'field', 'tmp/source.json', 'hash-source');`, ticker+"-"+family, ticker, family); err != nil {
				t.Fatal(err)
			}
		}
		if _, err := db.Exec(`INSERT INTO consumer_migration_registry VALUES (?);`, "scripts/"+ticker+".py"); err != nil {
			t.Fatal(err)
		}
	}
}

func writeFixturePackets(t *testing.T, root string, financeCount int, sourceLineageCount int) {
	t.Helper()
	fieldFamilies := map[string]any{}
	for _, family := range promotedFamilies {
		fieldFamilies[family] = map[string]any{
			"sql_primary_current_state": true,
			"canon_owner":               true,
		}
	}
	fieldFamilies["source_lineage"] = map[string]any{
		"sql_primary_current_state": true,
		"canon_owner":               true,
		"rows_by_field_family": map[string]any{
			"evidence_freshness": 2,
			"reference_levels":   2,
		},
	}
	writeJSON(t, root, "tmp/finance-sql-canon-access-validation.json", map[string]any{
		"status": "ok",
		"validation": map[string]any{
			"status":   "ok",
			"errors":   []any{},
			"warnings": []any{},
		},
		"counts": map[string]any{
			"answer_path_scope":           financeCount,
			"consumer_migration_registry": financeCount,
			"evidence_freshness":          financeCount,
			"evidence_status":             financeCount,
			"reference_levels":            financeCount,
			"securities":                  financeCount,
			"source_lineage":              sourceLineageCount,
			"tier_routing_state":          financeCount,
			"universe_membership":         financeCount,
		},
		"field_family_summary": map[string]any{
			"review_only_sql_json_canon_owner":            true,
			"source_open_required_before_material_claims": true,
			"canon_owner_metadata": map[string]any{
				"promoted_field_families": promotedFamilies,
			},
			"field_families": fieldFamilies,
		},
		"authority_boundary": map[string]any{
			"capital_deployment_allowed":            false,
			"paper_or_live_execution_allowed":       false,
			"brokerage_or_account_action_allowed":   false,
			"customer_or_external_delivery_allowed": false,
			"owner_approval_inferred":               false,
		},
	})
	writeJSON(t, root, "tmp/reference-levels-sql-native-source-family-proof.json", map[string]any{
		"status": "ok",
		"summary": map[string]any{
			"sql_first_reference_provenance_clean": true,
			"dry_run_sql_update_count":             0,
			"row_proof_count":                      2,
		},
		"validation": map[string]any{"status": "ok", "errors": []any{}, "warnings": []any{}},
		"authority":  map[string]any{"capital_deployment_allowed": false, "paper_or_live_execution_allowed": false, "owner_approval_inferred": false},
	})
	writeJSON(t, root, "tmp/sql-canon-answer-path-ab-harness.json", map[string]any{
		"status": "ok", "sql_count": 2, "current_count": 2, "diffs": []any{},
		"validation":         map[string]any{"status": "ok", "errors": []any{}, "warnings": []any{}},
		"authority_boundary": map[string]any{"capital_or_execution_authority": false},
	})
	writeJSON(t, root, "tmp/sql-canon-wf78-routing-parity.json", map[string]any{
		"status": "ok", "sql_count": 2, "source_count": 2, "diff_count": 0,
		"validation":         map[string]any{"status": "ok", "errors": []any{}, "warnings": []any{}},
		"authority_boundary": map[string]any{"capital_or_execution_authority": false},
	})
	writeJSON(t, root, "tmp/go-sql-consumer-registry-drift-lint.json", map[string]any{
		"status":             "ok",
		"summary":            map[string]any{"source_hash_mismatch_count": 0},
		"authority_boundary": map[string]any{"db_mutation": false},
	})
}

func writeJSON(t *testing.T, root, rel string, value any) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, append(bytes, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}
