package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/jsonproof"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	maxAgeHours := flag.Int("max-age-hours", 96, "warning threshold for generated_at_utc age")
	var packets multiFlag
	flag.Var(&packets, "packet", "proof packet path relative to root; repeatable. Defaults to SQL/canon proof packet bundle.")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := jsonproof.Run(jsonproof.Options{
		Root:        absRoot,
		Packets:     []string(packets),
		MaxAgeHours: *maxAgeHours,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s packets=%d checks=%d critical=%d warnings=%d stale=%d\n", report.Status, report.Summary.Packets, report.Summary.Checks, report.Summary.Critical, report.Summary.Warnings, report.Summary.StalePackets)
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
