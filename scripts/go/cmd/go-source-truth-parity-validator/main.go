package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sourcetruthparity"
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
	report, err := sourcetruthparity.Run(sourcetruthparity.Options{
		Root:       absRoot,
		SQLitePath: *sqlitePath,
		Driver:     *driver,
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "run parity validator: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	if err := sourcetruthparity.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	fmt.Printf("status=%s markdown_rows=%d ready_rows=%d mismatches=%d\n", report.Status, report.Summary.MarkdownRows, report.Summary.ReadyRows, report.Summary.MismatchRows)
}
