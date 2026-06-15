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
	source := flag.String("source", "", "finance universe validation JSON path")
	universe := flag.String("universe", "", "finance universe registry JSON path")
	out := flag.String("out", "", "optional JSON report path")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := durableoutputs.Run(durableoutputs.Options{
		Root:   absRoot,
		Mode:   "finance_universe_validation",
		Source: *source,
		Extra:  *universe,
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
	fmt.Printf("status=%s active=%v production=%v review_100=%v failed=%v\n",
		report.Status,
		report.SemanticSummary["active_ticker_count"],
		report.SemanticSummary["production_active_ticker_count"],
		report.SemanticSummary["review_100_monitor_count"],
		report.SemanticSummary["validation_failed"],
	)
}
