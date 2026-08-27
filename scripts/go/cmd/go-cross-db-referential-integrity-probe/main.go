package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/crossdb"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "tmp/go-cross-db-referential-integrity-probe.json", "JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := crossdb.Run(crossdb.Options{
		Root:       absRoot,
		SQLitePath: *sqlitePath,
		Driver:     *driver,
	})
	if *out != "" {
		if err := reporting.WriteJSON(resolveOut(absRoot, *out), report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d present_dbs=%d compared_sources=%d required_drift=%d optional_drift=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.PresentDBCount,
		report.Summary.ComparedSourceCount,
		report.Summary.RequiredSourceDriftCount,
		report.Summary.OptionalSourceDriftCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}

func resolveOut(root, out string) string {
	if filepath.IsAbs(out) {
		return out
	}
	return filepath.Join(root, filepath.FromSlash(out))
}
