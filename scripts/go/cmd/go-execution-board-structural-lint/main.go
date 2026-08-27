package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/boardlint"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	boardPath := flag.String("board", "03. Portfolio/Execution Board.md", "Execution Board path relative to root")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := boardlint.Run(boardlint.Options{
		Root:      absRoot,
		BoardPath: *boardPath,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d tables=%d ticker_rows=%d thin_surface=%v\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.TableCount,
		report.Summary.TickerRowCount,
		report.Summary.ThinSurface,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
