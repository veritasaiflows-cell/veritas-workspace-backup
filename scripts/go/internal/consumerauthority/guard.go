package consumerauthority

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const (
	SchemaVersion              = "sql_consumer_authority_guard_go.v1"
	artifactIndexRelPath       = "tmp/veritas-artifact-index.sqlite"
	canonCacheRelPath          = "tmp/veritas-canon-cache.sqlite"
	wf72ActivationStateRelPath = "tmp/wf72-entry-stop-sql-activation-state.json"
	wf72A2FallbackRelPath      = "tmp/wf72-a2-consumer-authority-fallback-values.json"
	lowRiskBoundary            = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
	wf72Boundary               = "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority"
)

var lowRiskApprovedKeys = []string{
	"NVDA:earnings_lifecycle_status",
	"NVDA:post_earnings_review_confirmed",
	"NVDA:last_earnings_date",
	"NVDA:post_earnings_review_date",
	"deployment:source_freshness_classification",
	"earnings:source_freshness_classification",
	"breadth:source_freshness_classification",
	"credit:source_freshness_classification",
	"fundamental_ir:source_freshness_classification",
	"fundamentals:source_freshness_classification",
	"market:source_freshness_classification",
	"policy:source_freshness_classification",
	"technical:source_freshness_classification",
}

var forbiddenAuthorityFlags = []string{
	"generated_report_is_canonical",
	"live_trade_or_account_action_allowed",
	"money_movement_allowed",
	"owner_approval_inferred",
	"paper_trade_submit_cancel_allowed_by_today_card",
	"trade_execution_allowed",
	"trade_or_account_action_allowed",
}

var forbiddenFieldTerms = []string{
	"account", "allocation", "approval", "auth", "band", "broker", "buy", "cash", "channel", "config",
	"credential", "endpoint", "entitlement", "entry", "entry_band", "execution", "live", "order",
	"owner_approval", "paper", "risk", "risk_rule", "sector", "sell", "service", "sizing", "sleeve",
	"stop", "stop_loss", "target_weight", "trade", "trim", "weight",
}

var entryStopReferenceMetadataFields = map[string]bool{
	"reference_price_low":               true,
	"reference_price_high":              true,
	"reference_invalidation_level":      true,
	"reference_level_source_timestamp":  true,
	"reference_level_source_sha256":     true,
	"reference_level_owner_source_path": true,
}

type Options struct {
	Root           string
	SQLitePath     string
	Driver         string
	FallbackPath   string
	FallbackValues map[string]any
}

type AuthorityBoundary struct {
	ReportOnly                   bool `json:"report_only"`
	ReadOnly                     bool `json:"read_only"`
	SQLWriteOrImportAllowed      bool `json:"sql_write_or_import_allowed"`
	DBMutation                   bool `json:"db_mutation"`
	CanonOrPortfolioMutation     bool `json:"canon_or_portfolio_mutation"`
	CustomerOrExternalDelivery   bool `json:"customer_or_external_delivery"`
	PaperOrLiveExecution         bool `json:"paper_or_live_execution"`
	OwnerApprovalInferred        bool `json:"owner_approval_inferred"`
	ConfigAuthRuntimeMutation    bool `json:"config_auth_runtime_mutation"`
	TradeOrAccountActionAllowed  bool `json:"trade_or_account_action_allowed"`
	MoneyMovementAllowed         bool `json:"money_movement_allowed"`
	DashboardBehaviorChange      bool `json:"dashboard_behavior_change_allowed"`
	CanonicalNoteMutationAllowed bool `json:"canonical_note_mutation_allowed"`
}

type DBRead struct {
	Path           string   `json:"db_path"`
	Exists         bool     `json:"exists"`
	ReadMode       string   `json:"read_mode"`
	IntegrityCheck string   `json:"integrity_check,omitempty"`
	TableNames     []string `json:"table_names,omitempty"`
	Error          string   `json:"error,omitempty"`
}

type Check struct {
	Name   string `json:"name"`
	OK     bool   `json:"ok"`
	Detail any    `json:"detail"`
}

type Validation struct {
	Status string   `json:"status"`
	Errors []string `json:"errors"`
}

type activationState struct {
	Status                       string   `json:"status"`
	ActiveEntryStopReferenceKeys []string `json:"active_entry_stop_reference_keys"`
}

type Summary struct {
	Checks                             int `json:"checks"`
	Failed                             int `json:"failed"`
	ApprovedKeys                       int `json:"approved_keys"`
	ActiveEntryStopReferenceKeys       int `json:"active_entry_stop_reference_keys"`
	CacheRows                          int `json:"cache_rows"`
	ExtraKeys                          int `json:"extra_keys"`
	MissingKeys                        int `json:"missing_keys"`
	FallbackMissingKeys                int `json:"fallback_missing_keys"`
	ForbiddenTrueRows                  int `json:"forbidden_true_rows"`
	CacheForbiddenRows                 int `json:"cache_forbidden_rows"`
	CacheStaleOrUnsafeRows             int `json:"cache_stale_or_unsafe_rows"`
	CanonStageApplyAllowedTrueCount    int `json:"canon_stage_apply_allowed_true_count"`
	CanonStageIncompleteReviewOnlyRows int `json:"canon_stage_incomplete_review_only_rows"`
}

type Report struct {
	SchemaVersion                      string            `json:"schema_version"`
	GeneratedAtUTC                     string            `json:"generated_at_utc"`
	Status                             string            `json:"status"`
	SQLiteDriver                       string            `json:"sqlite_driver"`
	SQLReadAllowed                     bool              `json:"sql_read_allowed"`
	ConsumerFamily                     string            `json:"consumer_family"`
	ConsumerSideRequiredBeforeSQLReads bool              `json:"consumer_side_required_before_non_optional_sql_reads"`
	AuthorityBoundary                  AuthorityBoundary `json:"authority_boundary"`
	ApprovedKeys                       []string          `json:"approved_keys"`
	ActiveEntryStopReferenceKeys       []string          `json:"active_entry_stop_reference_keys"`
	ArtifactIndexRead                  DBRead            `json:"artifact_index_read"`
	CacheRead                          DBRead            `json:"cache_read"`
	CacheMeta                          map[string]string `json:"cache_meta"`
	FallbackRead                       DBRead            `json:"fallback_read"`
	Summary                            Summary           `json:"summary"`
	Checks                             []Check           `json:"checks"`
	Issues                             []string          `json:"issues"`
	FallbackMissingKeys                []string          `json:"fallback_missing_keys"`
	ExtraKeys                          []string          `json:"extra_keys"`
	MissingKeys                        []string          `json:"missing_keys"`
	ForbiddenTrueRows                  []map[string]any  `json:"forbidden_true_rows"`
	CacheForbiddenRows                 []map[string]any  `json:"cache_forbidden_rows"`
	CacheStaleOrUnsafeRows             []map[string]any  `json:"cache_stale_or_unsafe_rows"`
	CanonStageApplyAllowedTrueCount    *int64            `json:"canon_stage_apply_allowed_true_count,omitempty"`
	CanonStageIncompleteReviewOnlyRows *int64            `json:"canon_stage_incomplete_review_only_rows,omitempty"`
	Validation                         Validation        `json:"validation"`
	NextSafeAction                     string            `json:"next_safe_action"`
}

func Run(opts Options) Report {
	root := defaultString(opts.Root, ".")
	sqlitePath := defaultString(opts.SQLitePath, "sqlite3")
	driver := defaultString(opts.Driver, sqlutil.DriverCLI)
	fallbackValues, fallbackRead := loadFallbackValues(root, opts.FallbackPath, opts.FallbackValues)
	approvedKeys := append([]string{}, lowRiskApprovedKeys...)
	activeKeys := activeEntryStopReferenceKeys(root)
	approvedKeys = append(approvedKeys, activeKeys...)

	artifactRead, forbiddenRows, applyAllowed, incompleteRows := inspectArtifactIndex(root, driver, sqlitePath)
	cacheRead, cacheMeta, cacheRows := inspectCanonCache(root, driver, sqlitePath)
	rowByKey := mapRowsByKey(cacheRows)
	extraKeys, missingKeys := diffKeys(keys(rowByKey), approvedKeys)
	cacheForbiddenRows, staleRows, fallbackMissing := inspectCacheRows(root, approvedKeys, activeKeys, rowByKey, fallbackValues)

	checks := []Check{}
	add := func(name string, ok bool, detail any) {
		checks = append(checks, Check{Name: name, OK: ok, Detail: detail})
	}
	allowedBoundaries := map[string]bool{lowRiskBoundary: true}
	if len(activeKeys) > 0 {
		allowedBoundaries[wf72Boundary] = true
	}
	add("artifact_index_read_available", artifactRead.Exists && artifactRead.Error == "", artifactRead)
	add("forbidden_authority_flags_false", len(forbiddenRows) == 0, firstRows(forbiddenRows, 5))
	add("canon_stage_apply_not_allowed", applyAllowed != nil && *applyAllowed == 0, valueOrMinusOne(applyAllowed))
	add("higher_risk_family_gates_no_activation", true, "all higher-risk family gates deny SQL-canon activation")
	add("canon_cache_exists", cacheRead.Exists, cacheRead.Path)
	add("canon_cache_integrity_ok", cacheRead.IntegrityCheck == "ok", cacheRead.IntegrityCheck)
	add("canon_cache_schema_present", hasTables(cacheRead.TableNames, "canon_cache_meta", "canon_cache_fields"), cacheRead.TableNames)
	add("sql_canon_boundary_active", allowedBoundaries[cacheMeta["authority_boundary"]], cacheMeta["authority_boundary"])
	add("sql_canon_authority_true", boolText(cacheMeta["sql_canon_authority"]), cacheMeta["sql_canon_authority"])
	add("consumer_scope_dashboard_proof_metadata_only", cacheMeta["consumer_authority_scope"] == "dashboard_proof_metadata_only", cacheMeta["consumer_authority_scope"])
	add("fallback_required_meta_true", boolText(cacheMeta["fallback_required"]), cacheMeta["fallback_required"])
	add("exact_approved_keys_only", len(extraKeys) == 0 && len(missingKeys) == 0, map[string]any{"extra": extraKeys, "missing": missingKeys})
	add("row_boundaries_and_field_families_allowed", len(cacheForbiddenRows) == 0, firstRows(cacheForbiddenRows, 5))
	add("fallback_values_present", len(fallbackMissing) == 0, fallbackMissing)
	add("cache_source_freshness_safe", len(staleRows) == 0, firstRows(staleRows, 5))

	issues := []string{}
	for _, check := range checks {
		if !check.OK {
			issues = append(issues, check.Name+": "+short(check.Detail))
		}
	}
	status := "ok"
	validationStatus := "ok"
	if len(issues) > 0 {
		status = "fail_closed"
		validationStatus = "blocked"
	}
	summary := Summary{
		Checks:                             len(checks),
		Failed:                             len(issues),
		ApprovedKeys:                       len(approvedKeys),
		ActiveEntryStopReferenceKeys:       len(activeKeys),
		CacheRows:                          len(cacheRows),
		ExtraKeys:                          len(extraKeys),
		MissingKeys:                        len(missingKeys),
		FallbackMissingKeys:                len(fallbackMissing),
		ForbiddenTrueRows:                  len(forbiddenRows),
		CacheForbiddenRows:                 len(cacheForbiddenRows),
		CacheStaleOrUnsafeRows:             len(staleRows),
		CanonStageApplyAllowedTrueCount:    int(valueOrMinusOne(applyAllowed)),
		CanonStageIncompleteReviewOnlyRows: int(valueOrMinusOne(incompleteRows)),
	}
	return Report{
		SchemaVersion:                      SchemaVersion,
		GeneratedAtUTC:                     reporting.UTCNow(),
		Status:                             status,
		SQLiteDriver:                       driver,
		SQLReadAllowed:                     len(issues) == 0,
		ConsumerFamily:                     "dashboard proof metadata",
		ConsumerSideRequiredBeforeSQLReads: true,
		AuthorityBoundary:                  AuthorityBoundary{ReportOnly: true, ReadOnly: true},
		ApprovedKeys:                       approvedKeys,
		ActiveEntryStopReferenceKeys:       activeKeys,
		ArtifactIndexRead:                  artifactRead,
		CacheRead:                          cacheRead,
		CacheMeta:                          cacheMeta,
		FallbackRead:                       fallbackRead,
		Summary:                            summary,
		Checks:                             checks,
		Issues:                             issues,
		FallbackMissingKeys:                fallbackMissing,
		ExtraKeys:                          extraKeys,
		MissingKeys:                        missingKeys,
		ForbiddenTrueRows:                  forbiddenRows,
		CacheForbiddenRows:                 cacheForbiddenRows,
		CacheStaleOrUnsafeRows:             staleRows,
		CanonStageApplyAllowedTrueCount:    applyAllowed,
		CanonStageIncompleteReviewOnlyRows: incompleteRows,
		Validation:                         Validation{Status: validationStatus, Errors: issues},
		NextSafeAction:                     "Use as a Go SQL consumer authority probe. SQL reads remain allowed only when the WF72 A2 fallback fixture is present, parity is clean, and authority flags stay false; Python fallback remains retained.",
	}
}

func inspectArtifactIndex(root, driver, sqlitePath string) (DBRead, []map[string]any, *int64, *int64) {
	dbPath := filepath.Join(root, filepath.FromSlash(artifactIndexRelPath))
	read := DBRead{Path: artifactIndexRelPath, ReadMode: "not_opened_missing_db"}
	if _, err := os.Stat(dbPath); err != nil {
		return read, nil, nil, nil
	}
	read.Exists = true
	read.ReadMode = "sqlite_ro"
	read.TableNames = tableNames(driver, sqlitePath, dbPath)
	if !hasTables(read.TableNames, "authority_flags", "canon_proposal_staging") {
		read.Error = "required tables missing"
		return read, nil, nil, nil
	}
	quoted := []string{}
	for _, flag := range forbiddenAuthorityFlags {
		quoted = append(quoted, "'"+strings.ReplaceAll(flag, "'", "''")+"'")
	}
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, `
SELECT artifact_run_id, flag_name, flag_value, surface, raw_value, source_file
FROM authority_flags
WHERE flag_value != 0 AND flag_name IN (`+strings.Join(quoted, ",")+`)
ORDER BY source_file, flag_name`)
	if err != nil {
		read.Error = err.Error()
	}
	applyAllowed := scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM canon_proposal_staging WHERE proposal_apply_allowed != 0")
	incompleteRows := scalarInt(driver, sqlitePath, dbPath, `
SELECT COUNT(*)
FROM canon_proposal_staging
WHERE proposal_apply_allowed = 0
  AND applied = 0
  AND (requires_owner_approval != 1 OR source_lineage_status = 'unverified' OR evidence_status = 'unstaged')`)
	return read, rows, applyAllowed, incompleteRows
}

func inspectCanonCache(root, driver, sqlitePath string) (DBRead, map[string]string, []map[string]any) {
	dbPath := filepath.Join(root, filepath.FromSlash(canonCacheRelPath))
	read := DBRead{Path: canonCacheRelPath, ReadMode: "not_opened_missing_db"}
	if _, err := os.Stat(dbPath); err != nil {
		return read, nil, nil
	}
	read.Exists = true
	read.ReadMode = "sqlite_ro"
	if integrity, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check"); err == nil {
		read.IntegrityCheck = integrity
	} else {
		read.Error = err.Error()
	}
	read.TableNames = tableNames(driver, sqlitePath, dbPath)
	if !hasTables(read.TableNames, "canon_cache_meta", "canon_cache_fields") {
		read.Error = "required tables missing"
		return read, nil, nil
	}
	metaRows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT key, value FROM canon_cache_meta ORDER BY key")
	if err != nil {
		read.Error = err.Error()
		return read, nil, nil
	}
	meta := map[string]string{}
	for _, row := range metaRows {
		meta[text(row["key"])] = text(row["value"])
	}
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT * FROM canon_cache_fields ORDER BY scope, field_name")
	if err != nil {
		read.Error = err.Error()
	}
	return read, meta, rows
}

func inspectCacheRows(root string, approvedKeys, activeKeys []string, rowByKey map[string]map[string]any, fallbackValues map[string]any) ([]map[string]any, []map[string]any, []string) {
	active := set(activeKeys)
	forbiddenRows := []map[string]any{}
	staleRows := []map[string]any{}
	fallbackMissing := []string{}
	for _, key := range approvedKeys {
		row, ok := rowByKey[key]
		if !ok {
			continue
		}
		fieldName := text(row["field_name"])
		expectedBoundary := lowRiskBoundary
		if active[key] {
			expectedBoundary = wf72Boundary
		}
		if text(row["authority_boundary"]) != expectedBoundary || (containsForbiddenTerm(fieldName) && !active[key]) {
			forbiddenRows = append(forbiddenRows, row)
		}
		issues := []string{}
		fallbackValue, fallbackPresent := fallbackValue(fallbackValues, key)
		if !fallbackPresent {
			fallbackMissing = append(fallbackMissing, key)
		} else if text(row["field_value"]) != text(fallbackValue) {
			issues = append(issues, "field_value_mismatch sql="+text(row["field_value"])+" fallback="+text(fallbackValue))
		}
		if text(row["validator_status"]) != "ok" {
			issues = append(issues, "validator_status="+text(row["validator_status"]))
		}
		if text(row["reconciliation_status"]) != "match" {
			issues = append(issues, "reconciliation_status="+text(row["reconciliation_status"]))
		}
		if strings.ToLower(text(row["freshness_status"])) != "fresh" {
			issues = append(issues, "freshness_status="+text(row["freshness_status"]))
		}
		sourceRel := text(row["source_artifact_path"])
		sourceHash := text(row["source_artifact_hash"])
		if sourceRel == "" {
			issues = append(issues, "source_artifact_missing")
		} else if liveHash := fileHash(filepath.Join(root, filepath.FromSlash(sourceRel))); liveHash == "" {
			issues = append(issues, "source_artifact_missing")
		} else if sourceHash != "" && liveHash != sourceHash && (!fallbackPresent || text(row["field_value"]) != text(fallbackValue)) {
			issues = append(issues, "source_artifact_hash_mismatch")
		}
		if len(issues) > 0 {
			staleRows = append(staleRows, map[string]any{"key": key, "issues": issues, "source_artifact_path": sourceRel})
		}
	}
	return forbiddenRows, staleRows, fallbackMissing
}

func activeEntryStopReferenceKeys(root string) []string {
	path := filepath.Join(root, filepath.FromSlash(wf72ActivationStateRelPath))
	bytes, err := os.ReadFile(path)
	if err != nil {
		return []string{}
	}
	var state activationState
	if err := json.Unmarshal(bytes, &state); err != nil {
		return []string{}
	}
	switch strings.TrimSpace(state.Status) {
	case "ok", "complete", "activation_ready":
	default:
		return []string{}
	}
	out := []string{}
	seen := map[string]bool{}
	for _, raw := range state.ActiveEntryStopReferenceKeys {
		key := strings.TrimSpace(raw)
		parts := strings.SplitN(key, ":", 2)
		if len(parts) != 2 || strings.TrimSpace(parts[0]) == "" || !entryStopReferenceMetadataFields[strings.TrimSpace(parts[1])] {
			return []string{}
		}
		if !seen[key] {
			seen[key] = true
			out = append(out, key)
		}
	}
	sort.Strings(out)
	return out
}

func loadFallbackValues(root, fallbackPath string, direct map[string]any) (map[string]any, DBRead) {
	if direct != nil {
		return direct, DBRead{Path: "provided", Exists: true, ReadMode: "provided_map"}
	}
	if strings.TrimSpace(fallbackPath) == "" {
		defaultPath := filepath.Join(root, filepath.FromSlash(wf72A2FallbackRelPath))
		if _, err := os.Stat(defaultPath); err == nil {
			fallbackPath = wf72A2FallbackRelPath
		}
	}
	read := DBRead{Path: fallbackPath, ReadMode: "not_configured"}
	if strings.TrimSpace(fallbackPath) == "" {
		return map[string]any{}, read
	}
	path := fallbackPath
	if !filepath.IsAbs(path) {
		path = filepath.Join(root, filepath.FromSlash(path))
	}
	read.Path = fallbackPath
	if _, err := os.Stat(path); err != nil {
		read.Error = err.Error()
		return map[string]any{}, read
	}
	read.Exists = true
	read.ReadMode = "json"
	bytes, err := os.ReadFile(path)
	if err != nil {
		read.Error = err.Error()
		return map[string]any{}, read
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		read.Error = err.Error()
		return map[string]any{}, read
	}
	return payload, read
}

func fallbackValue(values map[string]any, key string) (any, bool) {
	if values == nil {
		return nil, false
	}
	if value, ok := values[key]; ok && text(value) != "" {
		return value, true
	}
	parts := strings.SplitN(key, ":", 2)
	if len(parts) != 2 {
		return nil, false
	}
	candidates := []string{parts[1], strings.ToLower(parts[0]) + ":" + parts[1]}
	for _, candidate := range candidates {
		if value, ok := values[candidate]; ok && text(value) != "" {
			return value, true
		}
	}
	return nil, false
}

func tableNames(driver, sqlitePath, dbPath string) []string {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
	if err != nil {
		return nil
	}
	names := []string{}
	for _, row := range rows {
		names = append(names, text(row["name"]))
	}
	return names
}

func scalarInt(driver, sqlitePath, dbPath, query string) *int64 {
	value, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		return nil
	}
	var out int64
	for _, ch := range strings.TrimSpace(value) {
		if ch < '0' || ch > '9' {
			return nil
		}
		out = out*10 + int64(ch-'0')
	}
	return &out
}

func mapRowsByKey(rows []map[string]any) map[string]map[string]any {
	out := map[string]map[string]any{}
	for _, row := range rows {
		out[text(row["scope"])+":"+text(row["field_name"])] = row
	}
	return out
}

func keys(rows map[string]map[string]any) []string {
	out := []string{}
	for key := range rows {
		out = append(out, key)
	}
	sort.Strings(out)
	return out
}

func diffKeys(actual, expected []string) ([]string, []string) {
	actualSet := set(actual)
	expectedSet := set(expected)
	extra := []string{}
	missing := []string{}
	for _, key := range actual {
		if !expectedSet[key] {
			extra = append(extra, key)
		}
	}
	for _, key := range expected {
		if !actualSet[key] {
			missing = append(missing, key)
		}
	}
	return extra, missing
}

func set(values []string) map[string]bool {
	out := map[string]bool{}
	for _, value := range values {
		out[value] = true
	}
	return out
}

func hasTables(tables []string, required ...string) bool {
	have := set(tables)
	for _, table := range required {
		if !have[table] {
			return false
		}
	}
	return true
}

func boolText(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "1", "true", "yes", "ok":
		return true
	default:
		return false
	}
}

func containsForbiddenTerm(fieldName string) bool {
	lowered := strings.ToLower(fieldName)
	for _, term := range forbiddenFieldTerms {
		if strings.Contains(lowered, term) {
			return true
		}
	}
	return false
}

func fileHash(path string) string {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(bytes)
	return hex.EncodeToString(sum[:])
}

func firstRows(rows []map[string]any, limit int) []map[string]any {
	if len(rows) <= limit {
		return rows
	}
	return rows[:limit]
}

func valueOrMinusOne(value *int64) int64 {
	if value == nil {
		return -1
	}
	return *value
}

func text(value any) string {
	return strings.TrimSpace(fmt.Sprint(value))
}

func short(value any) string {
	text := strings.TrimSpace(fmt.Sprint(value))
	if len(text) > 900 {
		return text[:900] + "...<truncated>"
	}
	return text
}

func defaultString(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func Validate(report Report) error {
	boundary := report.AuthorityBoundary
	if !boundary.ReportOnly ||
		!boundary.ReadOnly ||
		boundary.SQLWriteOrImportAllowed ||
		boundary.DBMutation ||
		boundary.CanonOrPortfolioMutation ||
		boundary.CustomerOrExternalDelivery ||
		boundary.PaperOrLiveExecution ||
		boundary.OwnerApprovalInferred ||
		boundary.ConfigAuthRuntimeMutation ||
		boundary.TradeOrAccountActionAllowed ||
		boundary.MoneyMovementAllowed ||
		boundary.DashboardBehaviorChange ||
		boundary.CanonicalNoteMutationAllowed {
		return errors.New("authority boundary widened")
	}
	if report.Status != "ok" && report.Status != "fail_closed" {
		return errors.New("unexpected status")
	}
	return nil
}
