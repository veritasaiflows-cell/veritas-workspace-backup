package financehuman

import (
	"errors"
	"os"
	"path/filepath"
	"strconv"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const (
	schemaVersion = "finance_human_notes_sql_check_go.v1"
	dbRelPath     = "state/finance/finance-canon.sqlite"
)

var supportedActiveCounts = map[int64]bool{100: true, 200: true, 300: true, 400: true, 500: true}
var supportedReviewMonitorCounts = map[int64]bool{58: true, 158: true, 258: true, 358: true, 458: true}

type AuthorityBoundary struct {
	ReportOnly                   bool `json:"report_only"`
	ReadOnly                     bool `json:"read_only"`
	HumanNoteArchiveApplied      bool `json:"human_note_archive_applied"`
	DeleteAllowed                bool `json:"delete_allowed"`
	CanonicalNoteMutationAllowed bool `json:"canonical_note_mutation_allowed"`
	PortfolioMutationAllowed     bool `json:"portfolio_mutation_allowed"`
	CustomerOrExternalDelivery   bool `json:"customer_or_external_delivery_allowed"`
	PaperOrLiveExecutionAllowed  bool `json:"paper_or_live_execution_allowed"`
	TradeOrAccountActionAllowed  bool `json:"trade_or_account_action_allowed"`
	MoneyMovementAllowed         bool `json:"money_movement_allowed"`
	OwnerApprovalInferred        bool `json:"owner_approval_inferred"`
	ConfigAuthRuntimeMutation    bool `json:"config_auth_runtime_mutation"`
}

type SQLCanonCheck struct {
	Status                string `json:"status"`
	Path                  string `json:"path"`
	SQLiteDriver          string `json:"sqlite_driver"`
	Exists                bool   `json:"exists"`
	Integrity             string `json:"integrity,omitempty"`
	ActiveTickerCount     *int64 `json:"active_ticker_count,omitempty"`
	LegacyAnswerPathCount *int64 `json:"legacy_answer_path_count,omitempty"`
	ReviewMonitorCount    *int64 `json:"review_monitor_count,omitempty"`
}

type Report struct {
	SchemaVersion     string            `json:"schema_version"`
	GeneratedAtUTC    string            `json:"generated_at_utc"`
	Status            string            `json:"status"`
	AuthorityBoundary AuthorityBoundary `json:"authority_boundary"`
	SQLCanonCheck     SQLCanonCheck     `json:"sql_canon_check"`
	Validation        Validation        `json:"validation"`
	NextSafeAction    string            `json:"next_safe_action"`
}

type Validation struct {
	Status string  `json:"status"`
	Checks []Check `json:"checks"`
	Failed int     `json:"failed"`
}

type Check struct {
	Name   string `json:"name"`
	OK     bool   `json:"ok"`
	Detail any    `json:"detail"`
}

type Options struct {
	Root       string
	Driver     string
	SQLitePath string
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
	check := readSQLCanon(root, driver, sqlitePath)
	validation := validateSQLCanon(check)
	status := "ok"
	if validation.Failed > 0 {
		status = "blocked"
	}
	return Report{
		SchemaVersion:  schemaVersion,
		GeneratedAtUTC: reporting.UTCNow(),
		Status:         status,
		AuthorityBoundary: AuthorityBoundary{
			ReportOnly: true,
			ReadOnly:   true,
		},
		SQLCanonCheck:  check,
		Validation:     validation,
		NextSafeAction: "Use this as the Go parity probe for the finance human-notes thinning SQL-canon count check; keep archive/move/delete decisions in the Python owner-review packet.",
	}
}

func readSQLCanon(root, driver, sqlitePath string) SQLCanonCheck {
	dbPath := filepath.Join(root, filepath.FromSlash(dbRelPath))
	check := SQLCanonCheck{Path: dbRelPath, SQLiteDriver: driver}
	if _, err := os.Stat(dbPath); err != nil {
		check.Status = "missing"
		return check
	}
	check.Exists = true
	check.Integrity, _ = scalar(driver, sqlitePath, dbPath, "PRAGMA integrity_check")
	check.ActiveTickerCount = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM current_active_universe")
	check.LegacyAnswerPathCount = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM current_answer_path")
	check.ReviewMonitorCount = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM review_monitor_universe")
	if check.Integrity == "ok" && int64PtrInSet(check.ActiveTickerCount, supportedActiveCounts) && int64PtrEqual(check.LegacyAnswerPathCount, 0) && int64PtrInSet(check.ReviewMonitorCount, supportedReviewMonitorCounts) {
		check.Status = "ok"
	} else {
		check.Status = "blocked"
	}
	return check
}

func validateSQLCanon(check SQLCanonCheck) Validation {
	checks := []Check{
		{Name: "finance_canon_db_exists", OK: check.Exists, Detail: check.Path},
		{Name: "integrity_ok", OK: check.Integrity == "ok", Detail: check.Integrity},
		{Name: "active_ticker_count_supported_scaleout", OK: int64PtrInSet(check.ActiveTickerCount, supportedActiveCounts), Detail: map[string]any{"actual": check.ActiveTickerCount, "supported": []int64{100, 200, 300, 400, 500}}},
		{Name: "legacy_answer_path_retired_empty", OK: int64PtrEqual(check.LegacyAnswerPathCount, 0), Detail: map[string]any{"actual": check.LegacyAnswerPathCount, "expected": 0, "empty_production_scope_is_valid_wait_state": true}},
		{Name: "review_monitor_count_supported_scaleout", OK: int64PtrInSet(check.ReviewMonitorCount, supportedReviewMonitorCounts), Detail: map[string]any{"actual": check.ReviewMonitorCount, "supported": []int64{58, 158, 258, 358, 458}}},
	}
	failed := 0
	for _, check := range checks {
		if !check.OK {
			failed++
		}
	}
	status := "ok"
	if failed > 0 {
		status = "blocked"
	}
	return Validation{Status: status, Checks: checks, Failed: failed}
}

func scalar(driver, sqlitePath, dbPath, query string) (string, error) {
	return sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
}

func scalarInt(driver, sqlitePath, dbPath, sql string) *int64 {
	value, err := scalar(driver, sqlitePath, dbPath, sql)
	if err != nil {
		return nil
	}
	parsed, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return nil
	}
	return &parsed
}

func int64PtrEqual(value *int64, expected int64) bool {
	return value != nil && *value == expected
}

func int64PtrInSet(value *int64, supported map[int64]bool) bool {
	return value != nil && supported[*value]
}

func Validate(report Report) error {
	boundary := report.AuthorityBoundary
	if !boundary.ReportOnly ||
		!boundary.ReadOnly ||
		boundary.HumanNoteArchiveApplied ||
		boundary.DeleteAllowed ||
		boundary.CanonicalNoteMutationAllowed ||
		boundary.PortfolioMutationAllowed ||
		boundary.CustomerOrExternalDelivery ||
		boundary.PaperOrLiveExecutionAllowed ||
		boundary.TradeOrAccountActionAllowed ||
		boundary.MoneyMovementAllowed ||
		boundary.OwnerApprovalInferred ||
		boundary.ConfigAuthRuntimeMutation {
		return errors.New("authority boundary widened")
	}
	if report.Validation.Status != "ok" {
		return errors.New("validation not ok")
	}
	return nil
}
