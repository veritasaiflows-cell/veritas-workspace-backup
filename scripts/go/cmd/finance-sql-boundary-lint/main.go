package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/financesqllint"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	skipDB := flag.Bool("skip-db", false, "skip SQLite DB checks")
	var jsonInputs multiFlag
	var dbInputs multiFlag
	flag.Var(&jsonInputs, "json", "JSON artifact path relative to root; repeatable. Defaults to finance proof set.")
	flag.Var(&dbInputs, "db", "SQLite DB path relative to root; repeatable. Defaults to finance/SQL DB set.")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := financesqllint.Run(financesqllint.Options{
		Root:       absRoot,
		JSONFiles:  []string(jsonInputs),
		DBFiles:    []string(dbInputs),
		SQLitePath: *sqlitePath,
		SkipDB:     *skipDB,
	})
	bytes, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal report: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
			fmt.Fprintf(os.Stderr, "mkdir report dir: %v\n", err)
			os.Exit(2)
		}
		if err := os.WriteFile(*out, append(bytes, '\n'), 0o644); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d\n", report.Status, report.Summary.Checks, report.Summary.Critical, report.Summary.Warnings)
	if report.Status == "blocked" {
		fmt.Println(string(bytes))
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
