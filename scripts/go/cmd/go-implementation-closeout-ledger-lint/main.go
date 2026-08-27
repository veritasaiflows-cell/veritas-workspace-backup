package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/closeoutledger"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	laneRegister := flag.String("lane-register", "tmp/concurrent-lane-register.json", "lane register JSON path")
	changedRouter := flag.String("changed-router", "tmp/changed-file-validator-router.json", "changed-file router JSON path")
	validatorBundle := flag.String("validator-bundle", "tmp/validator-bundle-router.json", "validator bundle router JSON path")
	wrapperProof := flag.String("wrapper-proof", "tmp/go-fast-proof-validators.json", "Go proof wrapper JSON path")
	warningResidue := flag.String("warning-residue", "tmp/go-json-proof-warning-residue-lint.json", "warning residue classifier JSON path")
	releaseContract := flag.String("release-contract", "tmp/implementation-release-contract.json", "implementation release contract JSON path")
	memoryPath := flag.String("memory", "", "daily memory path; defaults to current America/Phoenix memory/YYYY-MM-DD.md")
	allowSingleActiveLane := flag.Bool("allow-single-active-lane", true, "allow the current implementation lane to be running while proof is generated")
	skipWrapperProof := flag.Bool("skip-wrapper-proof", false, "skip wrapper proof checks when this validator is running inside the wrapper itself")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := closeoutledger.Run(closeoutledger.Options{
		Root:                  absRoot,
		LaneRegister:          *laneRegister,
		ChangedRouter:         *changedRouter,
		ValidatorBundle:       *validatorBundle,
		WrapperProof:          *wrapperProof,
		WarningResidue:        *warningResidue,
		ReleaseContract:       *releaseContract,
		MemoryPath:            *memoryPath,
		AllowSingleActiveLane: *allowSingleActiveLane,
		SkipWrapperProof:      *skipWrapperProof,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d active_lanes=%d bundle_failed=%d unclassified_residue=%d release_ready=%t\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.ActiveLaneCount,
		report.Summary.ValidatorBundleFailed,
		report.Summary.UnclassifiedWarningResidue,
		report.Summary.ReleaseContractReady,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
