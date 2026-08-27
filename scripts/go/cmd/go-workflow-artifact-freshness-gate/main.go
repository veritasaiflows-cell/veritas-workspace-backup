package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/artifactfreshness"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	index := flag.String("index", "tmp/veritas-artifact-index.sqlite", "artifact index SQLite path relative to root")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	maxAgeHours := flag.Int("max-age-hours", 168, "fallback freshness horizon for indexed artifact file mtimes")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := artifactfreshness.Run(artifactfreshness.Options{
		Root:        absRoot,
		IndexPath:   *index,
		Driver:      *driver,
		SQLitePath:  *sqlitePath,
		MaxAgeHours: *maxAgeHours,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s artifact_rows=%d freshness_rows=%d checks=%d critical=%d warnings=%d stale_critical=%d stale_warning=%d stop_lines=%d\n",
		report.Status,
		report.Summary.ArtifactFileRows,
		report.Summary.SourceFreshnessRows,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.StaleCriticalCount,
		report.Summary.StaleWarningCount,
		report.Summary.StopLineCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
