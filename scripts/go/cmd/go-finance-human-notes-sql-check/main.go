package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/financehuman"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := financehuman.Run(financehuman.Options{Root: absRoot, Driver: *driver, SQLitePath: *sqlitePath})
	if err := financehuman.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s sql_canon=%s active=%s answer_path=%s review_monitor=%s\n", report.Status, report.SQLCanonCheck.Status, intText(report.SQLCanonCheck.ActiveTickerCount), intText(report.SQLCanonCheck.LegacyAnswerPathCount), intText(report.SQLCanonCheck.ReviewMonitorCount))
}

func intText(value *int64) string {
	if value == nil {
		return "missing"
	}
	return fmt.Sprintf("%d", *value)
}
