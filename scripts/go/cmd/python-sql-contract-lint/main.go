package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/pythonsqllint"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	var inputs multiFlag
	flag.Var(&inputs, "file", "Python file path relative to root; repeatable. Defaults to SQL/finance/canon target scripts.")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := pythonsqllint.Run(pythonsqllint.Options{
		Root:  absRoot,
		Files: []string(inputs),
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
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d files=%d\n", report.Status, report.Summary.Checks, report.Summary.Critical, report.Summary.Warnings, len(report.CheckedFiles))
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
