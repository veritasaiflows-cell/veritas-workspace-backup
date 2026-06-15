package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/sqllatency"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON output path")
	iterations := flag.Int("iterations", 20, "warm iterations per benchmark")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite", "sqlite3", "sqlite3 executable path")
	flag.Parse()

	report := sqllatency.Run(sqllatency.Options{
		Root:       *root,
		Iterations: *iterations,
		Driver:     *driver,
		SQLitePath: *sqlitePath,
	})
	if *out != "" {
		if err := writeJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf(
		"status=%s benchmarks=%d successful=%d failed_or_missing=%d\n",
		report.Status,
		report.Summary.Benchmarks,
		report.Summary.Successful,
		report.Summary.FailedOrMissing,
	)
	if report.Status == "critical" {
		os.Exit(1)
	}
}

func writeJSON(path string, value any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0o644)
}
