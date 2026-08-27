package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/fieldfamilyparity"
	"veritas.local/wf74/internal/reporting"
)

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	driver := flag.String("driver", "inprocess", "SQLite driver: cli or inprocess")
	sqlitePath := flag.String("sqlite3", "sqlite3", "sqlite3 binary path")
	dbPath := flag.String("db", "state/finance/finance-canon.sqlite", "finance canon SQLite DB path relative to root")
	financeAccess := flag.String("finance-access", "tmp/finance-sql-canon-access-validation.json", "finance SQL canon access validation JSON path relative to root")
	referenceProof := flag.String("reference-proof", "tmp/reference-levels-sql-native-source-family-proof.json", "reference levels source-family proof JSON path relative to root")
	answerHarness := flag.String("answer-harness", "tmp/sql-canon-answer-path-ab-harness.json", "answer path A/B harness JSON path relative to root")
	wf78Routing := flag.String("wf78-routing", "tmp/sql-canon-wf78-routing-parity.json", "WF78 routing parity JSON path relative to root")
	consumerRegistry := flag.String("consumer-registry", "tmp/go-sql-consumer-registry-drift-lint.json", "consumer registry Go lint JSON path relative to root")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	report := fieldfamilyparity.Run(fieldfamilyparity.Options{
		Root:                 absRoot,
		DBPath:               *dbPath,
		SQLitePath:           *sqlitePath,
		Driver:               *driver,
		FinanceAccessPath:    *financeAccess,
		ReferenceProofPath:   *referenceProof,
		AnswerHarnessPath:    *answerHarness,
		WF78RoutingPath:      *wf78Routing,
		ConsumerRegistryPath: *consumerRegistry,
	})
	if *out != "" {
		if err := reporting.WriteJSON(*out, report); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d critical=%d warnings=%d json_count_mismatches=%d source_hash_nulls=%d parity_diffs=%d authority_violations=%d\n",
		report.Status,
		report.Summary.Checks,
		report.Summary.Critical,
		report.Summary.Warnings,
		report.Summary.JSONCountMismatches,
		report.Summary.SourceHashNullCount,
		report.Summary.ParityDiffCount,
		report.Summary.AuthorityViolationCount,
	)
	if report.Status == "blocked" {
		os.Exit(1)
	}
}
