package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

type check struct {
	Name   string `json:"name"`
	OK     bool   `json:"ok"`
	Detail string `json:"detail"`
}

type report struct {
	SchemaVersion       string          `json:"schema_version"`
	GeneratedAtUTC      string          `json:"generated_at_utc"`
	Status              string          `json:"status"`
	SQLiteDriver        string          `json:"sqlite_driver"`
	ProbeDB             string          `json:"probe_db"`
	Summary             map[string]int  `json:"summary"`
	Checks              []check         `json:"checks"`
	AuthorityBoundary   map[string]bool `json:"authority_boundary"`
	DriverPilotPosture  string          `json:"driver_pilot_posture"`
	ProductionRouteNote string          `json:"production_route_note"`
}

func main() {
	root := flag.String("root", ".", "workspace root")
	out := flag.String("out", "", "optional JSON report path")
	dbRel := flag.String("db", "tmp/veritas-artifact-index.sqlite", "SQLite DB path relative to root for read-only probe")
	flag.Parse()

	absRoot, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "resolve root: %v\n", err)
		os.Exit(2)
	}
	dbPath := filepath.Join(absRoot, filepath.FromSlash(*dbRel))
	checks := []check{
		readProbe(dbPath),
		writeProbe(dbPath),
		errorProbe(dbPath),
		missingDBProbe(filepath.Join(absRoot, "tmp", "missing-inprocess-driver-pilot.sqlite")),
	}
	failed := 0
	for _, row := range checks {
		if !row.OK {
			failed++
		}
	}
	status := "ok"
	if failed > 0 {
		status = "blocked"
	}
	payload := report{
		SchemaVersion:  "go_sql_inprocess_readonly_probe.v1",
		GeneratedAtUTC: reporting.UTCNow(),
		Status:         status,
		SQLiteDriver:   "inprocess",
		ProbeDB:        filepath.ToSlash(*dbRel),
		Summary: map[string]int{
			"checks": len(checks),
			"failed": failed,
		},
		Checks:              checks,
		AuthorityBoundary:   reporting.ReadOnlyAuthorityBoundary(),
		DriverPilotPosture:  "In-process SQLite driver proof only. It validates read-only enforcement and error surfacing before any binary routing decision.",
		ProductionRouteNote: "Existing CLI-backed Go helpers remain the default route unless a separate gate and approval promote compiled in-process binaries.",
	}
	if *out != "" {
		if err := reporting.WriteJSON(*out, payload); err != nil {
			fmt.Fprintf(os.Stderr, "write report: %v\n", err)
			os.Exit(2)
		}
	}
	fmt.Printf("status=%s checks=%d failed=%d\n", payload.Status, len(checks), failed)
	if failed > 0 {
		os.Exit(1)
	}
}

func readProbe(dbPath string) check {
	value, err := sqlutil.ScalarInProcess(dbPath, "PRAGMA integrity_check")
	return check{Name: "read_query_integrity_check", OK: err == nil && value == "ok", Detail: detail(value, err)}
}

func writeProbe(dbPath string) check {
	err := sqlutil.WriteProbeInProcess(dbPath)
	return check{Name: "write_rejected_by_read_only_driver", OK: err != nil, Detail: detail("", err)}
}

func errorProbe(dbPath string) check {
	_, err := sqlutil.ScalarInProcess(dbPath, "SELECT * FROM definitely_missing_table_for_driver_pilot")
	return check{Name: "query_error_surfaces", OK: err != nil && strings.Contains(strings.ToLower(err.Error()), "missing"), Detail: detail("", err)}
}

func missingDBProbe(dbPath string) check {
	_, err := sqlutil.ScalarInProcess(dbPath, "PRAGMA integrity_check")
	return check{Name: "missing_database_error_surfaces", OK: err != nil, Detail: detail("", err)}
}

func detail(value string, err error) string {
	if err != nil {
		return err.Error()
	}
	return value
}
