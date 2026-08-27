package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/jsonstruct"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	index := flag.String("index", "tmp/veritas-artifact-index.sqlite", "artifact index SQLite path relative to root")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	maxAgeHours := flag.Int("max-age-hours", 168, "warning threshold for generated_at_utc age")
	limit := flag.Int("limit", 0, "optional max JSON artifacts to inspect")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := jsonstruct.Run(jsonstruct.Options{
		Root:        absRoot,
		IndexPath:   *index,
		Driver:      *driver,
		SQLitePath:  *sqlitePath,
		MaxAgeHours: *maxAgeHours,
		Limit:       *limit,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s artifacts=%d parsed=%d checks=%d critical=%d warnings=%d stale=%d authority_violations=%d\n",
		report.Status,
		report.Summary.IndexedJSONArtifacts,
		report.Summary.ParsedJSONArtifacts,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.StaleArtifactCount,
		report.Summary.AuthorityViolationCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
