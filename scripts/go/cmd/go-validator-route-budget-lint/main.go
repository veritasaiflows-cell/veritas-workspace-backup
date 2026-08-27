package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/routebudget"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	changedRoute := flag.String("changed-route", "tmp/changed-file-validator-router.json", "changed-file validator route JSON path relative to root")
	bundle := flag.String("bundle", "tmp/validator-bundle-router.json", "validator bundle router JSON path relative to root")
	timing := flag.String("timing", "tmp/validator-timing-ledger.json", "validator timing ledger JSON path relative to root")
	allowTimingWarnings := flag.Bool("allow-timing-warnings", true, "treat measured timing-ledger validator failures as warnings, not critical failures")
	requireExecution := flag.Bool("require-execution", false, "require bundle router mode=execute and at least one executed command")
	requireFullBudget := flag.Bool("require-full-budget", false, "block when selected bundle budget is below changed-file recommended budget")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := routebudget.Run(routebudget.Options{
		Root:              absRoot,
		ChangedRoutePath:  *changedRoute,
		BundlePath:        *bundle,
		TimingPath:        *timing,
		AllowTimingWarns:  *allowTimingWarnings,
		RequireExecution:  *requireExecution,
		RequireFullBudget: *requireFullBudget,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d route_budget=%s selected_budget=%s selected=%d missing_required=%d failed=%d timing_failures=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.RecommendedBudget,
		report.Summary.SelectedBudget,
		report.Summary.SelectedCommandCount,
		report.Summary.MissingRequiredCommandCount,
		report.Summary.FailedCommandCount,
		report.Summary.MeasuredValidatorFailureCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
