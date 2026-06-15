package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/consumerauthority"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "cli", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	fallbackJSON := flag.String("fallback-json", "", "optional fallback values JSON path")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := consumerauthority.Run(consumerauthority.Options{Root: absRoot, SQLitePath: *sqlitePath, Driver: *driver, FallbackPath: *fallbackJSON})
	if err := consumerauthority.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf(
		"status=%s sql_read_allowed=%v checks=%d failed=%d cache_rows=%d extra=%d fallback_missing=%d stale_or_unsafe=%d\n",
		report.Status,
		report.SQLReadAllowed,
		report.Summary.Checks,
		report.Summary.Failed,
		report.Summary.CacheRows,
		report.Summary.ExtraKeys,
		report.Summary.FallbackMissingKeys,
		report.Summary.CacheStaleOrUnsafeRows,
	)
}
