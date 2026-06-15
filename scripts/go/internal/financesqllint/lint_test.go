package financesqllint

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCleanFinanceJSONPassesWithoutSQLite(t *testing.T) {
	root := t.TempDir()
	files := []string{"tmp/finance-data-coverage-current.json"}
	writeJSON(t, root, files[0], `{
	  "status": "ok",
	  "authority_boundary": {
	    "owner_approval_inferred": false,
	    "trade_execution_allowed": false,
	    "paper_or_live_execution_allowed": false,
	    "sql_canon_migration_allowed": false
	  },
	  "posture": "review-only, not canon, not approval, not execution"
	}`)
	report := Run(Options{Root: root, JSONFiles: files, SkipDB: true})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %+v", report.Status, report.Findings)
	}
}

func TestProposalApplyAllowedBlocks(t *testing.T) {
	root := t.TempDir()
	files := []string{"tmp/capital-deployment-recommendation-validation.json"}
	writeJSON(t, root, files[0], `{"status":"bad","authority":{"proposal_apply_allowed":true}}`)
	report := Run(Options{Root: root, JSONFiles: files, SkipDB: true})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "forbidden_truthy_finance_authority_flag") {
		t.Fatalf("expected authority flag finding: %+v", report.Findings)
	}
}

func TestNegativeSQLCanonLanguageDoesNotBlock(t *testing.T) {
	root := t.TempDir()
	files := []string{"tmp/sql-coverage-guard.json"}
	writeJSON(t, root, files[0], `{"status":"ok","boundary":"SQLite is not canon and not approval authority."}`)
	report := Run(Options{Root: root, JSONFiles: files, SkipDB: true})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %+v", report.Status, report.Findings)
	}
}

func TestPositiveExecutionLanguageBlocks(t *testing.T) {
	root := t.TempDir()
	files := []string{"tmp/finance-data-coverage-current.json"}
	writeJSON(t, root, files[0], `{"status":"bad","claim":"Approved for trade execution."}`)
	report := Run(Options{Root: root, JSONFiles: files, SkipDB: true})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "execution_language") {
		t.Fatalf("expected execution language finding: %+v", report.Findings)
	}
}

func writeJSON(t *testing.T, root, rel, content string) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(strings.TrimSpace(content)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}

func hasCheck(report Report, check string) bool {
	for _, finding := range report.Findings {
		if finding.Check == check && !finding.OK {
			return true
		}
	}
	return false
}
