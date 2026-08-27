package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/bandfreshness"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "tmp/go-entry-stop-band-freshness-validator.json", "JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	canonDB := flag.String("canon-db", "state/finance/finance-canon.sqlite", "finance canon SQLite DB path relative to root")
	financeStateDB := flag.String("finance-state-db", "tmp/finance-intelligence-state.sqlite", "finance intelligence SQLite DB path relative to root")
	canonCacheDB := flag.String("canon-cache-db", "tmp/veritas-canon-cache.sqlite", "canon cache SQLite DB path relative to root")
	maxAgeHours := flag.Int("max-age-hours", 168, "warning threshold for source artifact age")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := bandfreshness.Run(bandfreshness.Options{
		Root:               absRoot,
		CanonDBPath:        *canonDB,
		FinanceStateDBPath: *financeStateDB,
		CanonCacheDBPath:   *canonCacheDB,
		SQLitePath:         *sqlitePath,
		Driver:             *driver,
		MaxAgeHours:        *maxAgeHours,
	})
	if *out != "" {
		if err := reporting.WriteJSON(resolveOut(absRoot, *out), report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d canon_refs=%d valid_mirror_rows=%d hash_mismatches=%d missing_lineage=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.CanonReferenceRows,
		report.Summary.FinanceStateValidMirrorRows,
		report.Summary.HashMismatchCount,
		report.Summary.MissingLineageTickerCount,
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
