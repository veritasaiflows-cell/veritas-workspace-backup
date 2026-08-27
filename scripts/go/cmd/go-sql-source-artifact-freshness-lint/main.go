package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sourcefreshness"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	dbPath := flag.String("db", "state/finance/finance-canon.sqlite", "finance canon SQLite DB path relative to root")
	maxAgeHours := flag.Int("max-age-hours", 240, "freshness horizon for source artifacts")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := sourcefreshness.Run(sourcefreshness.Options{
		Root:        absRoot,
		DBPath:      *dbPath,
		SQLitePath:  *sqlitePath,
		Driver:      *driver,
		MaxAgeHours: *maxAgeHours,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d lineage_rows=%d paths=%d hash_mismatches=%d stale=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.LineageRowCount,
		report.Summary.LineageArtifactPathCount,
		report.Summary.HashMismatchCount,
		report.Summary.StaleArtifactCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
