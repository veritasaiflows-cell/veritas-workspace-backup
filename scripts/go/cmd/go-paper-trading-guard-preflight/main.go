package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/paperguard"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	requireReady := flag.Bool("require-ready", false, "treat missing, blocked, or stale guard readiness as critical")
	var guardPaths multiFlag
	var killSwitchPaths multiFlag
	flag.Var(&guardPaths, "guard", "guard proof JSON path relative to root; repeatable")
	flag.Var(&killSwitchPaths, "kill-switch", "kill-switch JSON path relative to root; repeatable")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := paperguard.Run(paperguard.Options{
		Root:            absRoot,
		GuardPaths:      []string(guardPaths),
		KillSwitchPaths: []string(killSwitchPaths),
		RequireReady:    *requireReady,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d missing_guards=%d fresh_kill_switches=%d unsafe_flags=%d live_endpoint_hits=%d require_ready=%v\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.GuardArtifactMissing,
		report.Summary.FreshKillSwitchCount,
		report.Summary.UnsafeTrueFlagCount,
		report.Summary.LiveEndpointHitCount,
		report.Summary.RequireReady,
	)
	if report.Status == "blocked" {
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
