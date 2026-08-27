package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/answercheck"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "tmp/go-finance-answer-completeness-validator.json", "JSON report path")
	assemblerDir := flag.String("assembler-dir", "tmp/trade-grade-full-answer", "WF85 full-answer assembler packet directory")
	legacyDir := flag.String("legacy-dir", "tmp/ticker-answer-packets", "legacy answer packet directory")
	rollup := flag.String("rollup", "tmp/full-answer-parity/full-answer-parity-rollup.json", "full-answer parity/assembler rollup path")
	maxPackets := flag.Int("max-packets", 0, "maximum assembler packets to check; 0 checks all")
	maxAgeHours := flag.Int("max-age-hours", 168, "warning threshold for packet age")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := answercheck.Run(answercheck.Options{
		Root:             absRoot,
		AssemblerDir:     *assemblerDir,
		LegacyPacketDir:  *legacyDir,
		ParityRollupPath: *rollup,
		MaxPackets:       *maxPackets,
		MaxAgeHours:      *maxAgeHours,
	})
	if *out != "" {
		if err := reporting.WriteJSON(resolveOut(absRoot, *out), report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d assembler_packets=%d checked=%d missing_section_packets=%d forbidden_authority_packets=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.AssemblerPacketCount,
		report.Summary.CheckedAssemblerPacketCount,
		report.Summary.MissingSectionPacketCount,
		report.Summary.ForbiddenAuthorityPacketCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}

func resolveOut(root, out string) string {
	if filepath.IsAbs(out) {
		return out
	}
	return filepath.Join(root, filepath.FromSlash(out))
}
