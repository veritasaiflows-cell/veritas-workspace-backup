package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sourceproducer"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	freshnessReport := flag.String("freshness-report", "tmp/go-sql-source-artifact-freshness-lint.json", "source artifact freshness report path relative to root")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := sourceproducer.Run(sourceproducer.Options{
		Root:            absRoot,
		FreshnessReport: *freshnessReport,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d artifacts=%d mapped=%d open_repairs=%d registry_gaps=%d hash_drift=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.ArtifactCount,
		report.Summary.MappedArtifactCount,
		report.Summary.OpenRepairArtifactCount,
		report.Summary.RegistryGapCount,
		report.Summary.SourceArtifactDriftCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
