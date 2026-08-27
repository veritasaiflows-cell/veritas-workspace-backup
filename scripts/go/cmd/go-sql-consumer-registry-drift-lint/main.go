package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/consumerregistry"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	dbPath := flag.String("db", "state/finance/finance-canon.sqlite", "finance canon SQLite DB path relative to root")
	inventoryPath := flag.String("inventory", "tmp/sql-canon-consumer-inventory.json", "consumer inventory JSON path relative to root")
	backlogPath := flag.String("backlog", "tmp/sql-canon-consumer-migration-backlog.json", "consumer migration backlog JSON path relative to root")
	guardPath := flag.String("guard", "tmp/sql-canon-consumer-registry-guard.json", "consumer registry guard JSON path relative to root")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := consumerregistry.Run(consumerregistry.Options{
		Root:          absRoot,
		DBPath:        *dbPath,
		SQLitePath:    *sqlitePath,
		Driver:        *driver,
		InventoryPath: *inventoryPath,
		BacklogPath:   *backlogPath,
		GuardPath:     *guardPath,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d registry=%d backlog=%d missing=%d extra=%d mismatches=%d stale_hash=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.RegistryCount,
		report.Summary.BacklogCount,
		report.Summary.MissingRegistryCount,
		report.Summary.ExtraRegistryCount,
		report.Summary.FieldMismatchCount,
		report.Summary.SourceHashMismatchCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
