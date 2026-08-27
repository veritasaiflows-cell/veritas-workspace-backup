package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/authorityevent"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	dbPath := flag.String("db", "state/finance/finance-canon.sqlite", "finance canon SQLite DB path relative to root")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := authorityevent.Run(authorityevent.Options{
		Root:       absRoot,
		DBPath:     *dbPath,
		SQLitePath: *sqlitePath,
		Driver:     *driver,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d authority_events=%d audit_events=%d validator_runs=%d migration_runs=%d authority_violations=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.AuthorityEventCount,
		report.Summary.AuditEventCount,
		report.Summary.ValidatorRunCount,
		report.Summary.MigrationValidationRunCount,
		report.Summary.ForbiddenAuthorityFlagCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
