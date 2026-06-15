package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlinventory"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	var dbInputs multiFlag
	flag.Var(&dbInputs, "db", "SQLite DB path relative to root; repeatable. Defaults to core SQL surfaces.")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := sqlinventory.Run(sqlinventory.Options{
		Root:       absRoot,
		Driver:     *driver,
		SQLitePath: *sqlitePath,
		DBFiles:    []string(dbInputs),
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s dbs=%d present=%d tables=%d views=%d rows=%d warnings=%d blocked=%d\n", report.Status, report.Summary.Databases, report.Summary.Present, report.Summary.Tables, report.Summary.Views, report.Summary.TotalRows, report.Summary.WarningDBs, report.Summary.BlockedDBs)
	if report.Status == "blocked" {
		fmt.Println("blocked report written to", *out)
		os.Exit(1)
	}
}

type multiFlag []string

func (m *multiFlag) String() string {
	return fmt.Sprint([]string(*m))
}

func (m *multiFlag) Set(value string) error {
	*m = append(*m, value)
	return nil
}
