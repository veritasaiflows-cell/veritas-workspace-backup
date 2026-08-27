package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/expansiongate"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "cli", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := expansiongate.Run(expansiongate.Options{Root: absRoot, SQLitePath: *sqlitePath, Driver: *driver})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	if err := expansiongate.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	fmt.Printf("status=%s validation=%s production=%s pilot=%s overlap=%s\n", report.Status, report.Validation.Status, intText(report.CurrentState.ProductionCurrentCards), intText(report.CurrentState.LivePilotCandidates), intText(report.CurrentState.PilotProductionOverlap))
}

func intText(value *int64) string {
	if value == nil {
		return "missing"
	}
	return fmt.Sprintf("%d", *value)
}
