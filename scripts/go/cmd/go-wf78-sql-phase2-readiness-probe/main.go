package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/durableoutputs"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	source := flag.String("source", "", "WF78 SQL phase 2 readiness JSON path")
	out := flag.String("out", "", "optional JSON report path")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := durableoutputs.Run(durableoutputs.Options{
		Root:   absRoot,
		Mode:   "wf78_sql_phase2_readiness",
		Source: *source,
	})
	if err := durableoutputs.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s workflow=%v phase=%v surfaces=%v blocked=%v\n",
		report.Status,
		report.SemanticSummary["workflow"],
		report.SemanticSummary["phase"],
		report.SemanticSummary["surface_count"],
		report.SemanticSummary["blocked_surface_count"],
	)
}
