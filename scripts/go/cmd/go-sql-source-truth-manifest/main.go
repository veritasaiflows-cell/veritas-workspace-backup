package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sourcetruthmanifest"
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
	report := sourcetruthmanifest.Run(sourcetruthmanifest.Options{
		Root:       absRoot,
		SQLitePath: *sqlitePath,
		Driver:     *driver,
	})
	if err := sourcetruthmanifest.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s dbs=%d notes=%d errors=%d\n", report.Status, report.Summary.DatabaseSurfaces, report.Summary.CanonicalNotes, len(report.Summary.Errors))
	if report.Status == "blocked_for_sql_source_truth_promotion" {
		os.Exit(1)
	}
}
