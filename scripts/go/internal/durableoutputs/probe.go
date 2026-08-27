package durableoutputs

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"veritas.local/wf74/internal/reporting"
)

type Options struct {
	Root   string
	Mode   string
	Source string
	Extra  string
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Mode              string          `json:"mode"`
	SourceArtifacts   map[string]any  `json:"source_artifacts"`
	SourceShape       Shape           `json:"source_shape"`
	SemanticSummary   map[string]any  `json:"semantic_summary"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Validation        Validation      `json:"validation"`
	NextSafeAction    string          `json:"next_safe_action"`
}

type Shape struct {
	TopLevelKeys   []string `json:"top_level_keys"`
	Status         string   `json:"status"`
	Schema         any      `json:"schema"`
	SummaryKeys    []string `json:"summary_keys"`
	ValidationKeys []string `json:"validation_keys"`
	AuthorityKeys  []string `json:"authority_keys"`
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

const schemaVersion = "veritas.go_durable_output_probe.v1"

var supportedActiveCounts = map[int]bool{100: true, 200: true, 300: true, 400: true, 500: true}
var supportedReviewMonitorCounts = map[int]bool{58: true, 158: true, 258: true, 358: true, 458: true}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	mode := opts.Mode
	if mode == "" {
		mode = "finance_universe_validation"
	}
	source := resolve(root, opts.Source)
	extra := resolve(root, opts.Extra)
	if opts.Source == "" {
		source = defaultSource(root, mode)
	}
	if opts.Extra == "" {
		extra = defaultExtra(root, mode)
	}

	report := Report{
		SchemaVersion:     schemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Mode:              mode,
		SourceArtifacts:   map[string]any{"source": rel(root, source), "extra": rel(root, extra)},
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		NextSafeAction:    "Use this as a Go durable-output parity probe; keep Python as generator until repeated semantic/shape parity and consumer stability are green.",
	}

	sourcePayload, sourceErr := loadJSON(source)
	extraPayload, extraErr := loadJSON(extra)
	report.SourceShape = shape(sourcePayload)
	switch mode {
	case "finance_universe_validation":
		report.SemanticSummary = financeUniverseSummary(sourcePayload, extraPayload)
		report.Validation = validateFinanceUniverse(sourcePayload, extraPayload, sourceErr, extraErr)
	case "wf78_sql_phase2_readiness":
		report.SemanticSummary = wf78ReadinessSummary(sourcePayload)
		report.Validation = validateWF78Readiness(sourcePayload, sourceErr)
	default:
		report.Validation = Validation{Status: "blocked", Checks: []Check{{Name: "valid_mode", OK: false, Detail: mode}}, Failed: 1}
	}
	if report.Validation.Failed > 0 {
		report.Status = "blocked"
	} else {
		report.Status = "ok"
	}
	return report
}

func Validate(report Report) error {
	if report.Status != "ok" || report.Validation.Status != "ok" {
		return errors.New("durable output probe validation not ok")
	}
	if report.AuthorityBoundary["db_mutation"] ||
		report.AuthorityBoundary["canon_or_portfolio_mutation"] ||
		report.AuthorityBoundary["customer_or_external_delivery"] ||
		report.AuthorityBoundary["paper_or_live_execution"] ||
		report.AuthorityBoundary["owner_approval_inferred"] ||
		report.AuthorityBoundary["config_auth_runtime_mutation"] {
		return errors.New("authority boundary widened")
	}
	return nil
}

func defaultSource(root, mode string) string {
	switch mode {
	case "wf78_sql_phase2_readiness":
		return filepath.Join(root, "tmp", "wf78-sql-phase2-readiness.json")
	default:
		return filepath.Join(root, "tmp", "wf78-finance-universe-validation.json")
	}
}

func defaultExtra(root, mode string) string {
	switch mode {
	case "wf78_sql_phase2_readiness":
		return ""
	default:
		return filepath.Join(root, "data", "finance", "universe-v1.json")
	}
}

func resolve(root, path string) string {
	if path == "" || filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(root, path)
}

func loadJSON(path string) (map[string]any, error) {
	if path == "" {
		return map[string]any{}, nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return map[string]any{}, err
	}
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil {
		return map[string]any{}, err
	}
	return payload, nil
}

func shape(payload map[string]any) Shape {
	return Shape{
		TopLevelKeys:   sortedKeys(payload),
		Status:         stringValue(payload["status"]),
		Schema:         firstPresent(payload["schema"], payload["schema_version"]),
		SummaryKeys:    sortedKeys(asMap(payload["summary"])),
		ValidationKeys: sortedKeys(asMap(payload["validation"])),
		AuthorityKeys:  sortedKeys(asMap(payload["authority_boundary"])),
	}
}

func financeUniverseSummary(validation, universe map[string]any) map[string]any {
	validationSummary := asMap(validation["summary"])
	universeSummary := asMap(universe["summary"])
	entries := asList(universe["entries"])
	scopeCounts := map[string]int{}
	tierCounts := map[string]int{}
	instrumentTypeCounts := map[string]int{}
	sourceOpenMissing := 0
	for _, item := range entries {
		row := asMap(item)
		if row["active"] != true {
			continue
		}
		scopeCounts[stringValue(row["universe_scope"])]++
		tierCounts[stringValue(row["tier"])]++
		instrumentTypeCounts[stringValue(row["instrument_type"])]++
		if row["source_open_required"] != true {
			sourceOpenMissing++
		}
	}
	return map[string]any{
		"validation_status":               stringValue(validation["status"]),
		"validation_checks":               intValue(validationSummary["checks"]),
		"validation_failed":               intValue(validationSummary["failed"]),
		"active_ticker_count":             intValue(validationSummary["active_ticker_count"]),
		"production_active_ticker_count":  intValue(validationSummary["production_active_ticker_count"]),
		"pilot_fixture_count":             intValue(validationSummary["pilot_fixture_count"]),
		"review_100_monitor_count":        intValue(validationSummary["review_100_monitor_count"]),
		"universe_status":                 stringValue(universe["status"]),
		"universe_active_ticker_count":    intValue(universeSummary["active_ticker_count"]),
		"universe_production_count":       intValue(universeSummary["production_active_ticker_count"]),
		"universe_review_100_count":       intValue(universeSummary["review_100_monitor_count"]),
		"scope_counts":                    scopeCounts,
		"tier_counts":                     tierCounts,
		"instrument_type_counts":          instrumentTypeCounts,
		"source_open_missing":             sourceOpenMissing,
		"forbidden_authority_true_values": forbiddenTrueAuthority(validation, universe),
	}
}

func validateFinanceUniverse(validation, universe map[string]any, validationErr, universeErr error) Validation {
	checks := []Check{}
	add := func(name string, ok bool, detail any) {
		checks = append(checks, Check{Name: name, OK: ok, Detail: detail})
	}
	summary := asMap(validation["summary"])
	semantic := financeUniverseSummary(validation, universe)
	add("validation_artifact_readable", validationErr == nil, errString(validationErr))
	add("universe_artifact_readable", universeErr == nil, errString(universeErr))
	add("top_level_status_ok", stringValue(validation["status"]) == "ok", validation["status"])
	add("schema_version_1", intValue(validation["schema_version"]) == 1, validation["schema_version"])
	add("validation_failed_zero", intValue(summary["failed"]) == 0, summary)
	add("active_ticker_count_supported_scaleout", supportedActiveCounts[intValue(summary["active_ticker_count"])], summary["active_ticker_count"])
	add("production_scope_empty_sql_first_wait_state", intValue(summary["production_active_ticker_count"]) == 0, map[string]any{"actual": summary["production_active_ticker_count"], "expected": 0, "empty_production_scope_is_valid_wait_state": true})
	add("review_monitor_count_supported_scaleout", supportedReviewMonitorCounts[intValue(summary["review_100_monitor_count"])], summary["review_100_monitor_count"])
	add("pilot_count_zero", intValue(summary["pilot_fixture_count"]) == 0, summary["pilot_fixture_count"])
	add("universe_semantic_counts_match_validation",
		semantic["active_ticker_count"] == semantic["universe_active_ticker_count"] &&
			semantic["production_active_ticker_count"] == semantic["universe_production_count"] &&
			semantic["review_100_monitor_count"] == semantic["universe_review_100_count"],
		semantic)
	add("source_open_required_all_entries", semantic["source_open_missing"] == 0, semantic["source_open_missing"])
	add("no_forbidden_authority_true_values", len(asList(semantic["forbidden_authority_true_values"])) == 0, semantic["forbidden_authority_true_values"])
	return validationFromChecks(checks)
}

func wf78ReadinessSummary(readiness map[string]any) map[string]any {
	surfaces := asMap(readiness["surfaces"])
	surfaceStatus := map[string]any{}
	rowCounts := map[string]any{}
	for name, value := range surfaces {
		surface := asMap(value)
		surfaceStatus[name] = stringValue(surface["status"])
		if counts := asMap(surface["row_counts"]); len(counts) > 0 {
			rowCounts[name] = counts
		}
	}
	return map[string]any{
		"workflow":                        stringValue(readiness["workflow"]),
		"phase":                           stringValue(readiness["phase"]),
		"status":                          stringValue(readiness["status"]),
		"blocked_surface_count":           len(asList(readiness["blocked_surfaces"])),
		"surface_count":                   len(surfaces),
		"surface_status":                  surfaceStatus,
		"row_counts":                      rowCounts,
		"phase2_ready_when_count":         len(asList(readiness["phase2_ready_when"])),
		"forbidden_authority_true_values": forbiddenTrueAuthority(readiness),
	}
}

func validateWF78Readiness(readiness map[string]any, readinessErr error) Validation {
	checks := []Check{}
	add := func(name string, ok bool, detail any) {
		checks = append(checks, Check{Name: name, OK: ok, Detail: detail})
	}
	summary := wf78ReadinessSummary(readiness)
	surfaceStatus := asMap(summary["surface_status"])
	rowCounts := asMap(summary["row_counts"])
	add("readiness_artifact_readable", readinessErr == nil, errString(readinessErr))
	add("status_ready", stringValue(readiness["status"]) == "ready", readiness["status"])
	add("workflow_wf78", stringValue(readiness["workflow"]) == "WF78", readiness["workflow"])
	add("phase_2_readiness", stringValue(readiness["phase"]) == "phase_2_readiness", readiness["phase"])
	add("blocked_surfaces_empty", len(asList(readiness["blocked_surfaces"])) == 0, readiness["blocked_surfaces"])
	add("six_surfaces_present", len(asMap(readiness["surfaces"])) == 6, sortedKeys(asMap(readiness["surfaces"])))
	allOK := true
	for _, status := range surfaceStatus {
		if status != "ok" {
			allOK = false
		}
	}
	add("all_surfaces_ok", allOK, surfaceStatus)
	add("canon_cache_rows_265", nestedInt(rowCounts, "canon_cache", "canon_cache_fields") == 265, rowCounts["canon_cache"])
	financeState := asMap(rowCounts["finance_intelligence_state"])
	add("current_ticker_cards_empty_sql_first_wait_state", nestedInt(rowCounts, "finance_intelligence_state", "current_ticker_cards") == 0 && nestedInt(rowCounts, "finance_intelligence_state", "production_answer_path_rows") == 0, financeState)
	add("latest_valid_entry_stop_refs_not_ahead_of_active", nestedInt(rowCounts, "finance_intelligence_state", "latest_valid_entry_stop_refs") <= nestedInt(rowCounts, "finance_intelligence_state", "all_ticker_sql_rows"), financeState)
	add("no_forbidden_authority_true_values", len(asList(summary["forbidden_authority_true_values"])) == 0, summary["forbidden_authority_true_values"])
	return validationFromChecks(checks)
}

func validationFromChecks(checks []Check) Validation {
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

func forbiddenTrueAuthority(values ...map[string]any) []string {
	var hits []string
	for index, value := range values {
		hits = append(hits, forbiddenTrueAuthorityAt(value, fmt.Sprintf("$[%d]", index))...)
	}
	sort.Strings(hits)
	return hits
}

func forbiddenTrueAuthorityAt(value any, path string) []string {
	var hits []string
	switch typed := value.(type) {
	case map[string]any:
		for key, child := range typed {
			childPath := path + "." + key
			if child == true && (strings.HasSuffix(key, "_allowed") || strings.HasSuffix(key, "_authority") || key == "owner_approval_granted" || key == "owner_approval_inferred" || key == "database_path_migration_performed" || key == "tmp_database_promotion_performed" || key == "sql_canon_authority_expanded") {
				hits = append(hits, childPath)
			}
			hits = append(hits, forbiddenTrueAuthorityAt(child, childPath)...)
		}
	case []any:
		for index, child := range typed {
			hits = append(hits, forbiddenTrueAuthorityAt(child, fmt.Sprintf("%s[%d]", path, index))...)
		}
	}
	return hits
}

func nestedInt(values map[string]any, keys ...string) int {
	var current any = values
	for _, key := range keys {
		current = asMap(current)[key]
	}
	return intValue(current)
}

func asMap(value any) map[string]any {
	if out, ok := value.(map[string]any); ok {
		return out
	}
	return map[string]any{}
}

func asList(value any) []any {
	if out, ok := value.([]any); ok {
		return out
	}
	return []any{}
}

func sortedKeys(values map[string]any) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func stringValue(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	return ""
}

func intValue(value any) int {
	switch typed := value.(type) {
	case float64:
		return int(typed)
	case int:
		return typed
	default:
		return 0
	}
}

func firstPresent(values ...any) any {
	for _, value := range values {
		if value != nil {
			return value
		}
	}
	return nil
}

func errString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

func rel(root, path string) string {
	if path == "" {
		return ""
	}
	if relative, err := filepath.Rel(root, path); err == nil {
		return filepath.ToSlash(relative)
	}
	return filepath.ToSlash(path)
}
