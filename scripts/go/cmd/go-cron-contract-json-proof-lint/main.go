package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/cronproof"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	contractsDir := flag.String("contracts-dir", "state/cron-contracts", "cron contract JSON directory relative to root")
	controlPacket := flag.String("control-packet", "tmp/cron-control-packet.json", "cron control packet path relative to root")
	maxAgeHours := flag.Int("max-age-hours", 96, "warning threshold for generated_at_utc age")
	maxPromptChars := flag.Int("max-prompt-chars", 1800, "warning threshold for cron payload message characters")
	maxMessageLines := flag.Int("max-message-lines", 30, "warning threshold for cron payload message lines")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := cronproof.Run(cronproof.Options{
		Root:            absRoot,
		ContractsDir:    *contractsDir,
		ControlPacket:   *controlPacket,
		MaxAgeHours:     *maxAgeHours,
		MaxPromptChars:  *maxPromptChars,
		MaxMessageLines: *maxMessageLines,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d contracts=%d enabled=%d blocked_signals=%d escalation_signals=%d prompt_bloat=%d delivery_mismatch=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.ContractCount,
		report.Summary.EnabledContractCount,
		report.Summary.ControlBlockedSignalCount,
		report.Summary.ControlEscalationSignalCount,
		report.Summary.PromptBloatContractCount,
		report.Summary.DeliveryMismatchCount+report.Summary.ControlDeliveryMismatchCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
