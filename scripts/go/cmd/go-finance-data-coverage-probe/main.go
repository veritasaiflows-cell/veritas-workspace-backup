package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/financecoverage"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	source := flag.String("source", "", "finance data coverage JSON path")
	out := flag.String("out", "", "optional JSON report path")
	_ = flag.String("driver", "inprocess", "route driver label accepted for compiled-helper routing compatibility")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := financecoverage.Run(financecoverage.Options{Root: absRoot, Source: *source})
	if err := financecoverage.Validate(report); err != nil {
		fmt.Fprintf(os.Stderr, "validate report: %v\n", err)
		os.Exit(2)
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s source_status=%s families=%d tickers=%d sources=%d\n", report.Status, report.SourceStatus, report.Summary.DataFamilyCount, report.Summary.TickerCountIndexed, report.Summary.SourceArtifactCount)
}
