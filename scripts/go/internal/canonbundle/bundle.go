package canonbundle

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"veritas.local/wf74/internal/jsonproof"
	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const SchemaVersion = "go_sql_canon_proof_bundle_lint.v1"

var coreExactCounts = map[string]int{
	"evidence_freshness":  200,
	"reference_levels":    200,
	"current_answer_path": 0,
}

var supportedScaleoutCounts = map[string][]int{
	"answer_path_scope":         {100, 200, 300, 400, 500},
	"evidence_status":           {100, 200, 300, 400, 500},
	"securities":                {100, 200, 300, 400, 500},
	"tier_routing_state":        {100, 200, 300, 400, 500},
	"universe_membership":       {100, 200, 300, 400, 500},
	"current_active_universe":   {100, 200, 300, 400, 500},
	"current_sql_canon_routing": {100, 200, 300, 400, 500},
}

var requiredTables = []string{
	"answer_path_scope",
	"audit_events",
	"authority_events",
	"consumer_migration_registry",
	"evidence_freshness",
	"evidence_status",
	"migration_validation_runs",
	"reference_levels",
	"securities",
	"source_lineage",
	"tier_routing_state",
	"universe_membership",
	"validator_runs",
}

var requiredViews = []string{
	"current_active_universe",
	"current_answer_path",
	"current_sql_canon_routing",
	"review_monitor_universe",
}

type Options struct {
	Root         string
	DBPath       string
	SQLitePath   string
	Driver       string
	ProofPackets []string
	MaxAgeHours  int
	Now          time.Time
}

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   string `json:"detail,omitempty"`
}

func (f Finding) IsOK() bool {
	return f.OK
}

func (f Finding) FindingSeverity() string {
	return f.Severity
}

type Summary struct {
	Checks                int `json:"checks"`
	Critical              int `json:"critical"`
	Warnings              int `json:"warnings"`
	SQLObjectsChecked     int `json:"sql_objects_checked"`
	RowCountChecks        int `json:"row_count_checks"`
	ProofContractCritical int `json:"proof_contract_critical"`
	ProofContractWarnings int `json:"proof_contract_warnings"`
}

type Report struct {
	SchemaVersion       string           `json:"schema_version"`
	GeneratedAtUTC      string           `json:"generated_at_utc"`
	Status              string           `json:"status"`
	Root                string           `json:"root"`
	DBPath              string           `json:"db_path"`
	SQLiteDriver        string           `json:"sqlite_driver"`
	AuthorityBoundary   map[string]bool  `json:"authority_boundary"`
	RowCounts           map[string]int   `json:"row_counts"`
	Findings            []Finding        `json:"findings"`
	ProofContractReport jsonproof.Report `json:"proof_contract_report"`
	Summary             Summary          `json:"summary"`
	NextSafeAction      string           `json:"next_safe_action"`
}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	dbRel := opts.DBPath
	if dbRel == "" {
		dbRel = "state/finance/finance-canon.sqlite"
	}
	driver := opts.Driver
	if driver == "" {
		driver = sqlutil.DriverCLI
	}
	sqlitePath := opts.SQLitePath
	if sqlitePath == "" {
		sqlitePath = "sqlite3"
	}
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 96
	}
	now := opts.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	dbPath := dbRel
	if !filepath.IsAbs(dbPath) {
		dbPath = filepath.Join(root, filepath.FromSlash(dbRel))
	}

	findings := []Finding{}
	rowCounts := map[string]int{}
	sqlObjectsChecked := 0
	rowCountChecks := 0
	add := func(path, check, severity string, ok bool, detail string) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	if _, err := os.Stat(dbPath); err != nil {
		add(dbRel, "db_exists", "critical", false, err.Error())
	} else {
		add(dbRel, "db_exists", "info", true, "")
		if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
			add(dbRel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
		} else {
			add(dbRel, "sqlite_integrity_check", "info", true, "ok")
		}
		for _, table := range requiredTables {
			sqlObjectsChecked++
			expectObject(driver, sqlitePath, dbPath, dbRel, "table", table, add)
		}
		for _, view := range requiredViews {
			sqlObjectsChecked++
			expectObject(driver, sqlitePath, dbPath, dbRel, "view", view, add)
		}
		for _, target := range sortedCounts(coreExactCounts) {
			rowCountChecks++
			rowCounts[target.Name] = expectExactCount(driver, sqlitePath, dbPath, dbRel, target.Name, target.Expected, add)
		}
		for _, target := range sortedSupportedCounts(supportedScaleoutCounts) {
			rowCountChecks++
			rowCounts[target.Name] = expectSupportedCount(driver, sqlitePath, dbPath, dbRel, target.Name, target.Supported, add)
		}
		rowCountChecks++
		rowCounts["source_lineage"] = expectMinCount(driver, sqlitePath, dbPath, dbRel, "source_lineage", 1, add)
		rowCountChecks++
		consumerRows := expectMinCount(driver, sqlitePath, dbPath, dbRel, "consumer_migration_registry", 1, add)
		rowCounts["consumer_migration_registry"] = consumerRows
		if backlog, ok := consumerInventoryBacklog(root); ok {
			advisoryMissing := consumerRegistryAdvisoryMissingCount(root)
			add(
				dbRel,
				"consumer_registry_matches_inventory_backlog",
				"critical",
				consumerRows+advisoryMissing >= backlog,
				fmt.Sprintf("registry_rows=%d advisory_missing=%d inventory_backlog=%d", consumerRows, advisoryMissing, backlog),
			)
		} else {
			add(dbRel, "consumer_inventory_backlog_available", "warning", false, "missing tmp/sql-canon-consumer-inventory.json summary.backlog_count")
		}
	}

	proofReport := jsonproof.Run(jsonproof.Options{
		Root:        root,
		Packets:     opts.ProofPackets,
		MaxAgeHours: maxAgeHours,
		Now:         now,
	})
	if proofReport.Summary.Critical > 0 {
		add("tmp", "json_proof_contract_critical_zero", "critical", false, fmt.Sprintf("critical=%d", proofReport.Summary.Critical))
	} else {
		add("tmp", "json_proof_contract_critical_zero", "info", true, "")
	}
	if proofReport.Summary.Warnings > 0 {
		add("tmp", "json_proof_contract_warnings_zero", "warning", false, fmt.Sprintf("warnings=%d", proofReport.Summary.Warnings))
	} else {
		add("tmp", "json_proof_contract_warnings_zero", "info", true, "")
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:       SchemaVersion,
		GeneratedAtUTC:      reporting.UTCNow(),
		Status:              reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:                filepath.ToSlash(root),
		DBPath:              filepath.ToSlash(dbRel),
		SQLiteDriver:        driver,
		AuthorityBoundary:   reporting.ReadOnlyAuthorityBoundary(),
		RowCounts:           rowCounts,
		Findings:            findings,
		ProofContractReport: proofReport,
		Summary: Summary{
			Checks:                base.Checks,
			Critical:              base.Critical,
			Warnings:              base.Warnings,
			SQLObjectsChecked:     sqlObjectsChecked,
			RowCountChecks:        rowCountChecks,
			ProofContractCritical: proofReport.Summary.Critical,
			ProofContractWarnings: proofReport.Summary.Warnings,
		},
		NextSafeAction: "Use as an advisory read-only SQL canon plus JSON proof bundle lint. Keep Python as generator/orchestrator and do not infer owner approval.",
	}
}

type countTarget struct {
	Name string
}

func sortedCounts(values map[string]int) []struct {
	countTarget
	Expected int
} {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	out := make([]struct {
		countTarget
		Expected int
	}, 0, len(names))
	for _, name := range names {
		out = append(out, struct {
			countTarget
			Expected int
		}{countTarget: countTarget{Name: name}, Expected: values[name]})
	}
	return out
}

func sortedSupportedCounts(values map[string][]int) []struct {
	countTarget
	Supported []int
} {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	out := make([]struct {
		countTarget
		Supported []int
	}, 0, len(names))
	for _, name := range names {
		supported := append([]int(nil), values[name]...)
		sort.Ints(supported)
		out = append(out, struct {
			countTarget
			Supported []int
		}{countTarget: countTarget{Name: name}, Supported: supported})
	}
	return out
}

func expectObject(driver, sqlitePath, dbPath, rel, objectType, name string, add func(string, string, string, bool, string)) {
	query := fmt.Sprintf("SELECT COUNT(*) FROM sqlite_master WHERE type='%s' AND name='%s';", objectType, escapeSQL(name))
	count, err := scalarInt(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(rel, objectType+"_exists:"+name, "critical", false, err.Error())
		return
	}
	add(rel, objectType+"_exists:"+name, "critical", count == 1, fmt.Sprintf("observed=%d", count))
}

func expectExactCount(driver, sqlitePath, dbPath, rel, object string, expected int, add func(string, string, string, bool, string)) int {
	count, err := scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM "+sqlutil.QuoteIdentifier(object)+";")
	if err != nil {
		add(rel, "exact_rows:"+object, "critical", false, err.Error())
		return -1
	}
	add(rel, "exact_rows:"+object, "critical", count == expected, fmt.Sprintf("expected=%d observed=%d", expected, count))
	return count
}

func expectSupportedCount(driver, sqlitePath, dbPath, rel, object string, supported []int, add func(string, string, string, bool, string)) int {
	count, err := scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM "+sqlutil.QuoteIdentifier(object)+";")
	if err != nil {
		add(rel, "supported_rows:"+object, "critical", false, err.Error())
		return -1
	}
	ok := false
	for _, expected := range supported {
		if count == expected {
			ok = true
			break
		}
	}
	add(rel, "supported_rows:"+object, "critical", ok, fmt.Sprintf("supported=%v observed=%d", supported, count))
	return count
}

func expectMinCount(driver, sqlitePath, dbPath, rel, object string, minimum int, add func(string, string, string, bool, string)) int {
	count, err := scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM "+sqlutil.QuoteIdentifier(object)+";")
	if err != nil {
		add(rel, "min_rows:"+object, "critical", false, err.Error())
		return -1
	}
	add(rel, "min_rows:"+object, "critical", count >= minimum, fmt.Sprintf("expected_min=%d observed=%d", minimum, count))
	return count
}

func consumerInventoryBacklog(root string) (int, bool) {
	path := filepath.Join(root, filepath.FromSlash("tmp/sql-canon-consumer-inventory.json"))
	bytes, err := os.ReadFile(path)
	if err != nil {
		return 0, false
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		return 0, false
	}
	summary, ok := payload["summary"].(map[string]any)
	if !ok {
		return 0, false
	}
	return numeric(summary["backlog_count"])
}

func consumerRegistryAdvisoryMissingCount(root string) int {
	path := filepath.Join(root, "tmp", "sql-canon-consumer-registry-guard.json")
	bytes, err := os.ReadFile(path)
	if err != nil {
		return 0
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		return 0
	}
	validation, _ := payload["validation"].(map[string]any)
	warnings, _ := validation["warnings"].([]any)
	count := 0
	for _, raw := range warnings {
		text := fmt.Sprint(raw)
		const prefix = "advisory_missing_test_or_parity_registry_rows:"
		if !strings.HasPrefix(text, prefix) {
			continue
		}
		for _, item := range strings.Split(strings.TrimPrefix(text, prefix), ",") {
			if strings.TrimSpace(item) != "" {
				count++
			}
		}
	}
	return count
}

func scalarInt(driver, sqlitePath, dbPath, query string) (int, error) {
	value, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		return 0, err
	}
	return strconv.Atoi(strings.TrimSpace(value))
}

func numeric(value any) (int, bool) {
	switch typed := value.(type) {
	case float64:
		return int(typed), true
	case int:
		return typed, true
	case int64:
		return int(typed), true
	case string:
		parsed, err := strconv.Atoi(strings.TrimSpace(typed))
		return parsed, err == nil
	default:
		return 0, false
	}
}

func escapeSQL(value string) string {
	return strings.ReplaceAll(value, "'", "''")
}
