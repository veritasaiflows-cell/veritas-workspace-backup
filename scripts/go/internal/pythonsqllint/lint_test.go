package pythonsqllint

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCleanSQLScriptPasses(t *testing.T) {
	root := t.TempDir()
	rel := "scripts/finance_sql_helper.py"
	writeFile(t, root, rel, `
"""Read-only SQL helper. Not canon, no execution, no owner approval."""
import sqlite3

def validate():
    return True
`)
	report := Run(Options{Root: root, Files: []string{rel}})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %+v", report.Status, report.Findings)
	}
}

func TestForbiddenRuntimeLanguageBlocks(t *testing.T) {
	root := t.TempDir()
	rel := "scripts/finance_sql_helper.py"
	writeFile(t, root, rel, `
import sqlite3
claim = "SQL is canon"
def validate():
    return True
`)
	report := Run(Options{Root: root, Files: []string{rel}})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
}

func TestMissingValidationWarns(t *testing.T) {
	root := t.TempDir()
	rel := "scripts/generic_sql_helper.py"
	writeFile(t, root, rel, `
"""Read-only helper. Not canon, no execution."""
import sqlite3
`)
	report := Run(Options{Root: root, Files: []string{rel}})
	if report.Status != "warning" {
		t.Fatalf("expected warning, got %s: %+v", report.Status, report.Findings)
	}
}

func writeFile(t *testing.T, root, rel, content string) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(strings.TrimSpace(content)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}
