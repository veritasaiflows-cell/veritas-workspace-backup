package authorityevent

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const SchemaVersion = "go_finance_canon_authority_event_lint.v1"

type Options struct {
	Root       string
	DBPath     string
	SQLitePath string
	Driver     string
	Now        time.Time
}

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   any    `json:"detail,omitempty"`
}

func (f Finding) IsOK() bool {
	return f.OK
}

func (f Finding) FindingSeverity() string {
	return f.Severity
}

type Summary struct {
	Checks                       int            `json:"checks"`
	Critical                     int            `json:"critical"`
	Warnings                     int            `json:"warnings"`
	AuthorityEventCount          int            `json:"authority_event_count"`
	AuditEventCount              int            `json:"audit_event_count"`
	ValidatorRunCount            int            `json:"validator_run_count"`
	MigrationValidationRunCount  int            `json:"migration_validation_run_count"`
	ForbiddenAuthorityFlagCount  int            `json:"forbidden_authority_flag_count"`
	OwnerApprovalMissingCount    int            `json:"owner_approval_missing_count"`
	NonOKValidatorStatusCount    int            `json:"non_ok_validator_status_count"`
	MigrationValidationFailCount int            `json:"migration_validation_fail_count"`
	EventTypeCounts              map[string]int `json:"event_type_counts"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	DBPath            string          `json:"db_path"`
	SQLiteDriver      string          `json:"sqlite_driver"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

var requiredTables = []string{
	"authority_events",
	"audit_events",
	"validator_runs",
	"migration_validation_runs",
}

var forbiddenAuthorityTerms = []string{
	"brokerage_or_account_action",
	"capital_deployment",
	"cash_sizing_risk_rule_or_execution",
	"customer_or_external_delivery",
	"live_trading",
	"money_movement",
	"owner_approval_inferred",
	"paper_or_live_execution",
	"portfolio_or_canon_markdown_mutation",
	"trade_execution",
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	dbRel := defaulted(opts.DBPath, "state/finance/finance-canon.sqlite")
	driver := defaulted(opts.Driver, sqlutil.DriverInProcess)
	sqlitePath := defaulted(opts.SQLitePath, "sqlite3")
	now := opts.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}

	findings := []Finding{}
	add := func(path, check, severity string, ok bool, detail any) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	dbPath := resolve(root, dbRel)
	if _, err := os.Stat(dbPath); err != nil {
		add(dbRel, "db_exists", "critical", false, err.Error())
	} else {
		add(dbRel, "db_exists", "info", true, "")
	}
	if err := sqlutil.ValidateDriver(driver); err != nil {
		add(dbRel, "sqlite_driver_supported", "critical", false, err.Error())
	} else {
		add(dbRel, "sqlite_driver_supported", "info", true, sqlutil.NormalizeDriver(driver))
	}
	if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
		add(dbRel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
	} else {
		add(dbRel, "sqlite_integrity_check", "info", true, "ok")
	}
	for _, table := range requiredTables {
		count, err := scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='"+escapeSQL(table)+"';")
		add(dbRel, "table_exists:"+table, "critical", err == nil && count == 1, map[string]any{"count": count, "error": errorText(err)})
	}

	authorityRows := readRows(driver, sqlitePath, dbPath, dbRel, "SELECT event_id, event_time_utc, event_type, COALESCE(approval_source, '') AS approval_source, COALESCE(approval_message_id, '') AS approval_message_id, authority_boundary_json, detail_json FROM authority_events ORDER BY event_time_utc, event_id;", add)
	auditRows := readRows(driver, sqlitePath, dbPath, dbRel, "SELECT event_id, event_time_utc, event_type, detail_json FROM audit_events ORDER BY event_time_utc, event_id;", add)
	validatorRows := readRows(driver, sqlitePath, dbPath, dbRel, "SELECT name, artifact_path, COALESCE(status, '') AS status, COALESCE(generated_at_utc, '') AS generated_at_utc, summary_json FROM validator_runs ORDER BY name;", add)
	migrationRows := readRows(driver, sqlitePath, dbPath, dbRel, "SELECT run_id, run_time_utc, validator_name, status, artifact_path, detail_json FROM migration_validation_runs ORDER BY run_time_utc, run_id;", add)

	add(dbRel, "authority_events_present", "critical", len(authorityRows) > 0, len(authorityRows))
	add(dbRel, "audit_events_present", "warning", len(auditRows) > 0, len(auditRows))
	add(dbRel, "validator_runs_present", "warning", len(validatorRows) > 0, len(validatorRows))
	add(dbRel, "migration_validation_runs_present", "warning", len(migrationRows) > 0, len(migrationRows))

	eventTypeCounts := map[string]int{}
	forbiddenCount := 0
	missingOwnerApproval := 0
	for _, row := range authorityRows {
		eventID := text(row["event_id"])
		eventType := text(row["event_type"])
		eventTypeCounts[eventType]++
		checkTime(dbRel, "authority_event_time_parse:"+eventID, text(row["event_time_utc"]), now, add)
		add(dbRel, "authority_detail_json_parse:"+eventID, "critical", validJSON(text(row["detail_json"])), "")
		authorityPayload, ok := parseJSONObject(text(row["authority_boundary_json"]))
		add(dbRel, "authority_boundary_json_parse:"+eventID, "critical", ok, "")
		if ok {
			violations := authorityViolations(authorityPayload, "")
			forbiddenCount += len(violations)
			add(dbRel, "authority_boundary_forbidden_flags_false:"+eventID, "critical", len(violations) == 0, violations)
		}
		if strings.Contains(eventType, "owner_approved") {
			sourceOK := text(row["approval_source"]) != ""
			messageOK := text(row["approval_message_id"]) != ""
			if !sourceOK || !messageOK {
				missingOwnerApproval++
			}
			add(dbRel, "owner_approval_source_present:"+eventID, "critical", sourceOK, text(row["approval_source"]))
			add(dbRel, "owner_approval_message_present:"+eventID, "critical", messageOK, text(row["approval_message_id"]))
		}
	}

	rollbackWarnings := 0
	for _, row := range auditRows {
		eventID := text(row["event_id"])
		checkTime(dbRel, "audit_event_time_parse:"+eventID, text(row["event_time_utc"]), now, add)
		detail, ok := parseJSONObject(text(row["detail_json"]))
		add(dbRel, "audit_detail_json_parse:"+eventID, "critical", ok, "")
		if ok {
			violations := authorityViolations(detail, "")
			forbiddenCount += len(violations)
			add(dbRel, "audit_detail_forbidden_flags_false:"+eventID, "critical", len(violations) == 0, violations)
			if strings.Contains(text(row["event_type"]), "applied") && !hasRollbackTrace(detail) {
				rollbackWarnings++
				add(dbRel, "audit_event_has_rollback_or_fallback_trace:"+eventID, "warning", false, text(row["event_type"]))
			} else {
				add(dbRel, "audit_event_has_rollback_or_fallback_trace:"+eventID, "info", true, "")
			}
		}
	}
	_ = rollbackWarnings

	nonOKValidatorStatus := 0
	for _, row := range validatorRows {
		name := text(row["name"])
		status := text(row["status"])
		expectedBlocked := expectedBlockedValidatorStatus(name, status)
		if blockedStatus(status) && !expectedBlocked {
			nonOKValidatorStatus++
		}
		add(dbRel, "validator_status_not_blocked:"+name, "critical", !blockedStatus(status) || expectedBlocked, status)
		add(dbRel, "validator_summary_json_parse:"+name, "critical", validJSON(text(row["summary_json"])), "")
		artifact := text(row["artifact_path"])
		add(dbRel, "validator_artifact_path_present:"+name, "warning", artifact != "", "")
		if artifact != "" {
			_, err := os.Stat(resolve(root, artifact))
			artifactOK := err == nil || legacyMissingValidatorArtifact(name, status, artifact)
			add(dbRel, "validator_artifact_exists_or_is_legacy:"+name, "warning", artifactOK, artifact)
		}
		generated := text(row["generated_at_utc"])
		if generated != "" {
			checkTime(dbRel, "validator_generated_at_parse:"+name, generated, now, add)
		}
	}

	migrationFailCount := 0
	for _, row := range migrationRows {
		runID := text(row["run_id"])
		status := text(row["status"])
		if blockedStatus(status) {
			migrationFailCount++
		}
		add(dbRel, "migration_validation_status_not_blocked:"+runID, "critical", !blockedStatus(status), status)
		checkTime(dbRel, "migration_validation_time_parse:"+runID, text(row["run_time_utc"]), now, add)
		add(dbRel, "migration_validation_detail_json_parse:"+runID, "critical", validJSON(text(row["detail_json"])), "")
		add(dbRel, "migration_validation_artifact_path_present:"+runID, "warning", text(row["artifact_path"]) != "", "")
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		DBPath:            filepath.ToSlash(dbRel),
		SQLiteDriver:      sqlutil.NormalizeDriver(driver),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                       base.Checks,
			Critical:                     base.Critical,
			Warnings:                     base.Warnings,
			AuthorityEventCount:          len(authorityRows),
			AuditEventCount:              len(auditRows),
			ValidatorRunCount:            len(validatorRows),
			MigrationValidationRunCount:  len(migrationRows),
			ForbiddenAuthorityFlagCount:  forbiddenCount,
			OwnerApprovalMissingCount:    missingOwnerApproval,
			NonOKValidatorStatusCount:    nonOKValidatorStatus,
			MigrationValidationFailCount: migrationFailCount,
			EventTypeCounts:              sortedCounts(eventTypeCounts),
		},
		NextSafeAction: "Use as read-only authority-event proof. Repair source events through approved SQL-canon authority paths; do not mutate SQL/canon/portfolio state from this validator.",
	}
}

func legacyMissingValidatorArtifact(name, status, artifact string) bool {
	status = strings.ToLower(strings.TrimSpace(status))
	if strings.Contains(status, "not_required_superseded") {
		return true
	}
	name = strings.ToLower(strings.TrimSpace(name))
	artifact = strings.ToLower(strings.TrimSpace(artifact))
	return name == "ticker_card_100_validate_only" &&
		strings.Contains(artifact, "ticker-card-wf78-100-import-production42-validate-summary")
}

func readRows(driver, sqlitePath, dbPath, dbRel, query string, add func(string, string, string, bool, any)) []map[string]any {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	check := "query:" + firstSQLWords(query, 3)
	if err != nil {
		add(dbRel, check, "critical", false, err.Error())
		return nil
	}
	add(dbRel, check, "info", true, len(rows))
	return rows
}

func scalarInt(driver, sqlitePath, dbPath, query string) (int, error) {
	value, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		return 0, err
	}
	var out int
	_, err = fmt.Sscanf(strings.TrimSpace(value), "%d", &out)
	return out, err
}

func checkTime(path, check, value string, now time.Time, add func(string, string, string, bool, any)) {
	timestamp, err := time.Parse(time.RFC3339, value)
	if err != nil {
		add(path, check, "critical", false, err.Error())
		return
	}
	add(path, check, "info", true, value)
	if now.Sub(timestamp.UTC()) < -5*time.Minute {
		add(path, check+"_not_future", "critical", false, value)
	}
}

func parseJSONObject(value string) (map[string]any, bool) {
	var payload map[string]any
	if err := json.Unmarshal([]byte(value), &payload); err != nil {
		return map[string]any{}, false
	}
	return payload, true
}

func validJSON(value string) bool {
	var payload any
	return json.Unmarshal([]byte(value), &payload) == nil
}

func authorityViolations(value any, prefix string) []string {
	violations := []string{}
	object, ok := value.(map[string]any)
	if !ok {
		return violations
	}
	for key, raw := range object {
		path := key
		if prefix != "" {
			path = prefix + "." + key
		}
		if child, ok := raw.(map[string]any); ok {
			violations = append(violations, authorityViolations(child, path)...)
			continue
		}
		if forbiddenAuthorityKey(key) && truthy(raw) {
			violations = append(violations, path+"="+text(raw))
		}
	}
	sort.Strings(violations)
	return violations
}

func forbiddenAuthorityKey(key string) bool {
	lower := strings.ToLower(key)
	for _, term := range forbiddenAuthorityTerms {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func hasRollbackTrace(detail map[string]any) bool {
	for _, key := range []string{"backup_manifest", "backup_path", "rollback", "rollback_instructions", "fallback_retained", "archive_plan"} {
		if _, ok := detail[key]; ok {
			return true
		}
	}
	return false
}

func blockedStatus(status string) bool {
	lower := strings.ToLower(strings.TrimSpace(status))
	if lower == "" {
		return false
	}
	for _, term := range []string{"blocked", "critical", "error", "failed", "fail_closed"} {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func expectedBlockedValidatorStatus(name, status string) bool {
	lowerName := strings.ToLower(strings.TrimSpace(name))
	if lowerName != "sql_500_ticker_expansion_design_gate" {
		return false
	}
	lowerStatus := strings.ToLower(strings.TrimSpace(status))
	return strings.Contains(lowerStatus, "blocked")
}

func truthy(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case float64:
		return typed != 0
	case int:
		return typed != 0
	case int64:
		return typed != 0
	case string:
		switch strings.ToLower(strings.TrimSpace(typed)) {
		case "1", "true", "yes", "allowed", "ok":
			return true
		}
	}
	return false
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func resolve(root, relPath string) string {
	if filepath.IsAbs(relPath) {
		return relPath
	}
	return filepath.Join(root, filepath.FromSlash(relPath))
}

func defaulted(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func errorText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

func escapeSQL(value string) string {
	return strings.ReplaceAll(value, "'", "''")
}

func firstSQLWords(query string, n int) string {
	parts := strings.Fields(query)
	if len(parts) > n {
		parts = parts[:n]
	}
	return strings.ToLower(strings.Join(parts, "_"))
}

func sortedCounts(values map[string]int) map[string]int {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := map[string]int{}
	for _, key := range keys {
		out[key] = values[key]
	}
	return out
}
