package schemalint

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

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
	Checks   int `json:"checks"`
	Critical int `json:"critical"`
	Warnings int `json:"warnings"`
	DBs      int `json:"dbs"`
}

type Report struct {
	SchemaVersion  string    `json:"schema_version"`
	GeneratedAtUTC string    `json:"generated_at_utc"`
	Status         string    `json:"status"`
	SQLiteDriver   string    `json:"sqlite_driver"`
	Root           string    `json:"root"`
	CheckedDBs     []string  `json:"checked_dbs"`
	Findings       []Finding `json:"findings"`
	Summary        Summary   `json:"summary"`
	Boundary       string    `json:"boundary"`
}

type Options struct {
	Root       string
	DBFiles    []string
	SQLitePath string
	Driver     string
}

type DBContract struct {
	Path          string
	Tables        []string
	Views         []string
	Columns       map[string][]string
	MinRows       map[string]int
	ExactRows     map[string]int
	SupportedRows map[string][]int
	ZeroCounts    map[string]string
	// Retired marks a path deliberately archived by the 2026-08-29 alerts-OS
	// pivot. For these, absence is the expected state; recreation is the defect.
	Retired bool
}

var defaultContracts = []DBContract{
	{
		Path:      "state/finance/finance-canon.sqlite",
		Tables:    []string{"securities", "universe_membership", "evidence_status", "validator_runs", "audit_events"},
		Views:     []string{"current_active_universe", "current_answer_path", "review_monitor_universe"},
		ExactRows: map[string]int{"current_answer_path": 0},
		SupportedRows: map[string][]int{
			"current_active_universe": {100, 200, 300, 400, 500},
			"review_monitor_universe": {58, 158, 258, 358, 458},
		},
		ZeroCounts: map[string]string{
			"finance_execution_flags_zero": "SELECT COUNT(*) FROM evidence_status WHERE paper_or_live_execution_allowed != 0 OR customer_output_allowed != 0;",
		},
	},
	{
		Path:    "tmp/finance-intelligence-state.sqlite",
		Tables:  []string{"universe", "latest_price_technical", "entry_stop_reference", "fundamental_snapshot", "official_evidence_index", "ticker_family_status", "validation_results"},
		Views:   []string{"current_ticker_cards", "latest_valid_entry_stop_refs", "latest_validator_status"},
		MinRows: map[string]int{"universe": 42, "official_evidence_index": 1},
		Retired: true,
	},
	{
		Path:   "tmp/veritas-artifact-index.sqlite",
		Tables: []string{"artifact_runs", "authority_flags", "source_artifacts", "validator_runs", "daily_review_objects", "official_ir_capture_fields"},
		Views:  []string{"v_cockpit_action_queue", "v_cockpit_ticker_timeline", "v_cockpit_trust_boundary", "v_cockpit_source_freshness", "v_cockpit_deployment_readiness"},
		ZeroCounts: map[string]string{
			"artifact_index_forbidden_authority_zero": "SELECT COUNT(*) FROM authority_flags WHERE flag_value != 0 AND flag_name IN ('proposal_apply_allowed','per_packet_owner_approval_inferred','owner_approval_inferred','owner_approval_inference_allowed','trade_execution_allowed','trade_or_account_action_allowed','live_brokerage_or_account_action_allowed','brokerage_or_account_action_allowed','paper_order_submit_allowed_by_this_registry','paper_order_cancel_allowed_by_this_registry','paper_or_live_execution_allowed','sql_as_canon_promotion_allowed','sql_canon_migration_allowed','full_sql_canon_migration_allowed','tmp_artifact_promotion_allowed','db_path_migration_allowed','customer_output_allowed');",
		},
	},
	{
		Path:      "tmp/veritas-canon-cache.sqlite",
		Tables:    []string{"canon_cache_fields", "canon_cache_change_ledger", "canon_cache_meta"},
		ExactRows: map[string]int{"canon_cache_fields": 265},
		ZeroCounts: map[string]string{
			"canon_cache_validator_not_ok_zero": "SELECT COUNT(*) FROM canon_cache_fields WHERE validator_status != 'ok' OR reconciliation_status != 'match';",
		},
		Retired: true,
	},
	{
		Path:    "tmp/json-sql-promotion-index.sqlite",
		Tables:  []string{"json_documents", "promotion_registry", "metadata"},
		MinRows: map[string]int{"json_documents": 1},
	},
	{
		Path:    "tmp/pm-program-state.sqlite",
		Tables:  []string{"pm_runs", "pm_lanes", "pm_blockers", "pm_next_actions", "pm_artifacts", "pm_authority_flags"},
		MinRows: map[string]int{"pm_lanes": 1, "pm_next_actions": 1},
	},
	{
		Path:    "tmp/generic-service-state.sqlite",
		Tables:  []string{"service_runs", "authority_events", "artifact_refs", "operator_queue", "qa_events"},
		MinRows: map[string]int{"service_runs": 1},
	},
	{
		Path:    "tmp/wf75-service-state.sqlite",
		Tables:  []string{"metadata", "service_requests", "queue_items", "events", "artifact_refs", "claim_log"},
		MinRows: map[string]int{"service_requests": 1},
	},
}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	sqlitePath := opts.SQLitePath
	if sqlitePath == "" {
		sqlitePath = "sqlite3"
	}
	driver := opts.Driver
	if driver == "" {
		driver = sqlutil.DriverCLI
	}
	contracts := filterContracts(opts.DBFiles)
	var findings []Finding
	var checked []string
	add := func(path, check, severity string, ok bool, detail string) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}
	for _, contract := range contracts {
		rel := filepath.ToSlash(contract.Path)
		dbPath := filepath.Join(root, filepath.FromSlash(rel))
		if _, err := os.Stat(dbPath); err != nil {
			if contract.Retired {
				// Retired by the 2026-08-29 alerts-OS pivot and archived with rollback
				// proof. Absence is the correct state, so it is not a defect.
				add(rel, "retired_db_absent", "info", true, "retired path; absence is the expected state")
				continue
			}
			add(rel, "db_exists", "critical", false, err.Error())
			continue
		}
		if contract.Retired {
			// Recreation is the real drift: the alerts-OS pivot validator rejects
			// these paths on active tmp surfaces, and they must be archived out.
			checked = append(checked, rel)
			add(rel, "retired_db_recreated", "critical", false, "retired current-state path present on an active surface; archive it and remove it from tmp")
			continue
		}
		checked = append(checked, rel)
		add(rel, "db_exists", "info", true, "")
		checkContract(driver, sqlitePath, dbPath, contract, add)
	}
	baseSummary := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:  "sql_schema_drift_lint.v1",
		GeneratedAtUTC: reporting.UTCNow(),
		Status:         reporting.StatusFromCounts(baseSummary.Critical, baseSummary.Warnings),
		SQLiteDriver:   driver,
		Root:           filepath.ToSlash(root),
		CheckedDBs:     checked,
		Findings:       findings,
		Summary:        Summary{Checks: baseSummary.Checks, Critical: baseSummary.Critical, Warnings: baseSummary.Warnings, DBs: len(checked)},
		Boundary:       "Read-only Go SQLite schema drift validator. No SQL writes, canon/portfolio mutation, customer/external delivery, paper/live/account action, config/runtime mutation, or owner approval inference.",
	}
}

func filterContracts(files []string) []DBContract {
	if len(files) == 0 {
		return defaultContracts
	}
	want := map[string]bool{}
	for _, file := range files {
		want[filepath.ToSlash(file)] = true
	}
	var out []DBContract
	for _, contract := range defaultContracts {
		if want[filepath.ToSlash(contract.Path)] {
			out = append(out, contract)
		}
	}
	return out
}

func checkContract(driver, sqlitePath, dbPath string, contract DBContract, add func(string, string, string, bool, string)) {
	rel := filepath.ToSlash(contract.Path)
	if out, err := sqliteScalar(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
		add(rel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
	} else {
		add(rel, "sqlite_integrity_check", "info", true, "ok")
	}
	for _, table := range contract.Tables {
		expectObject(driver, sqlitePath, dbPath, rel, "table_exists:"+table, "table", table, add)
	}
	for _, view := range contract.Views {
		expectObject(driver, sqlitePath, dbPath, rel, "view_exists:"+view, "view", view, add)
	}
	for table, columns := range contract.Columns {
		for _, column := range columns {
			expectColumn(driver, sqlitePath, dbPath, rel, table, column, add)
		}
	}
	for table, count := range contract.MinRows {
		expectCount(driver, sqlitePath, dbPath, rel, "min_rows:"+table, "SELECT COUNT(*) FROM "+table+";", count, false, add)
	}
	for table, count := range contract.ExactRows {
		expectCount(driver, sqlitePath, dbPath, rel, "exact_rows:"+table, "SELECT COUNT(*) FROM "+table+";", count, true, add)
	}
	for table, counts := range contract.SupportedRows {
		expectCountInSet(driver, sqlitePath, dbPath, rel, "supported_rows:"+table, "SELECT COUNT(*) FROM "+table+";", counts, add)
	}
	for check, sql := range contract.ZeroCounts {
		expectCount(driver, sqlitePath, dbPath, rel, check, sql, 0, true, add)
	}
}

func expectCountInSet(driver, sqlitePath, dbPath, rel, check, sql string, expected []int, add func(string, string, string, bool, string)) {
	out, err := sqliteScalar(driver, sqlitePath, dbPath, sql)
	if err != nil {
		add(rel, check, "critical", false, err.Error())
		return
	}
	count, err := strconv.Atoi(strings.TrimSpace(out))
	if err != nil {
		add(rel, check, "critical", false, "non-integer result: "+strings.TrimSpace(out))
		return
	}
	for _, allowed := range expected {
		if count == allowed {
			add(rel, check, "info", true, fmt.Sprintf("observed=%d supported=%v", count, expected))
			return
		}
	}
	add(rel, check, "critical", false, fmt.Sprintf("supported=%v observed=%d", expected, count))
}

func expectObject(driver, sqlitePath, dbPath, rel, check, objectType, name string, add func(string, string, string, bool, string)) {
	sql := fmt.Sprintf("SELECT COUNT(*) FROM sqlite_master WHERE type='%s' AND name='%s';", objectType, escapeSQL(name))
	expectCount(driver, sqlitePath, dbPath, rel, check, sql, 1, true, add)
}

func expectColumn(driver, sqlitePath, dbPath, rel, table, column string, add func(string, string, string, bool, string)) {
	sql := fmt.Sprintf("SELECT COUNT(*) FROM pragma_table_info('%s') WHERE name='%s';", escapeSQL(table), escapeSQL(column))
	expectCount(driver, sqlitePath, dbPath, rel, "column_exists:"+table+"."+column, sql, 1, true, add)
}

func expectCount(driver, sqlitePath, dbPath, rel, check, sql string, expected int, exact bool, add func(string, string, string, bool, string)) {
	out, err := sqliteScalar(driver, sqlitePath, dbPath, sql)
	if err != nil {
		add(rel, check, "critical", false, err.Error())
		return
	}
	count, err := strconv.Atoi(strings.TrimSpace(out))
	if err != nil {
		add(rel, check, "critical", false, "non-integer result: "+strings.TrimSpace(out))
		return
	}
	if exact && count != expected {
		add(rel, check, "critical", false, fmt.Sprintf("expected=%d observed=%d", expected, count))
		return
	}
	if !exact && count < expected {
		add(rel, check, "critical", false, fmt.Sprintf("expected_min=%d observed=%d", expected, count))
		return
	}
	add(rel, check, "info", true, fmt.Sprintf("observed=%d", count))
}

func sqliteScalar(driver string, sqlitePath string, dbPath string, sql string) (string, error) {
	return sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, sql)
}

func escapeSQL(value string) string {
	return strings.ReplaceAll(value, "'", "''")
}
