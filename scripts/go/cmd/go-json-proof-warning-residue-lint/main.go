package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/warningresidue"
)

type repeatedString []string

func (r *repeatedString) String() string {
	return fmt.Sprint([]string(*r))
}

func (r *repeatedString) Set(value string) error {
	*r = append(*r, value)
	return nil
}

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	maxExamples := flag.Int("max-examples", 50, "maximum classified residue examples to include")
	var reports repeatedString
	flag.Var(&reports, "report", "inner Go validator JSON report path; may be repeated")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := warningresidue.Run(warningresidue.Options{
		Root:        absRoot,
		ReportPaths: reports,
		MaxExamples: *maxExamples,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s reports=%d warnings=%d classified=%d unclassified=%d critical=%d\n",
		report.Status,
		report.Summary.ReportCount,
		report.Summary.WarningFindingCount,
		report.Summary.ClassifiedWarningCount,
		report.Summary.UnclassifiedCount,
		report.Summary.CriticalFindingCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
