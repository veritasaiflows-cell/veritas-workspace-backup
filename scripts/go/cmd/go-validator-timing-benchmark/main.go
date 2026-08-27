package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/timingbench"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	inspectOnly := flag.Bool("inspect-only", false, "inspect allowlisted binaries without executing them")
	timeoutMS := flag.Int("timeout-ms", 30000, "per-validator timeout in milliseconds")
	var validators multiFlag
	flag.Var(&validators, "validator", "allowlisted Go validator binary name; repeatable")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := timingbench.Run(timingbench.Options{
		Root:        absRoot,
		Validators:  []string(validators),
		InspectOnly: *inspectOnly,
		Timeout:     time.Duration(*timeoutMS) * time.Millisecond,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s validators=%d executed=%d inspected=%d missing=%d failed=%d max_elapsed_ms=%s\n",
		report.Status,
		report.Summary.ValidatorCount,
		report.Summary.ExecutedCount,
		report.Summary.InspectedCount,
		report.Summary.MissingCount,
		report.Summary.FailedCount,
		floatText(report.Summary.MaxElapsedMS),
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

func floatText(value *float64) string {
	if value == nil {
		return "null"
	}
	return fmt.Sprintf("%.3f", *value)
}
