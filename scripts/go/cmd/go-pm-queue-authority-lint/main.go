package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/pmlint"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	packet := flag.String("packet", "tmp/pm-control-packet.json", "PM control packet path relative to root")
	maxAgeHours := flag.Int("max-age-hours", 6, "warning threshold for generated_at_utc age")
	requirePacket := flag.Bool("require-packet", false, "treat a missing PM packet as blocking instead of advisory warning")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := pmlint.Run(pmlint.Options{
		Root:        absRoot,
		PacketPath:  *packet,
		MaxAgeHours: *maxAgeHours,
		Require:     *requirePacket,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d stale_lanes=%d blocked_jobs=%d owner_gate_auto=%d unsafe_auto_jobs=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.StaleLaneCount,
		report.Summary.BlockedJobCount,
		report.Summary.OwnerGateAutoExecutionCount,
		report.Summary.UnsafeAutoJobCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
