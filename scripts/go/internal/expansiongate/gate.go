package expansiongate

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strconv"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const (
	expectedDeprecatedProduction int64 = 0
	expectedLivePilot            int64 = 25
	target500                    int64 = 500
)

var supportedActiveCounts = map[int64]bool{100: true, 200: true, 300: true, 400: true, 500: true}
var supportedReviewMonitorCounts = map[int64]bool{58: true, 158: true, 258: true, 358: true, 458: true}
var tierTargets = map[string]any{"A": 25, "B": 75, "C": 150, "D": 250}
var enrichmentBatch1 = []string{"AAPL", "AVGO", "ASML", "COST", "CRM", "PANW", "TSM", "V", "UNH", "WMT"}
var requiredEnrichmentFamilies = []string{
	"official_fundamentals",
	"key_financial_metrics",
	"latest_earnings_performance",
	"price_band_stop",
	"technical_posture",
	"risk_register",
	"valuation_multiples",
	"revenue_growth_margins_fcf_debt",
	"analyst_consensus",
}

type AuthorityBoundary struct {
	ReportOnly                           bool `json:"report_only"`
	BroadTickerImportAllowed             bool `json:"broad_ticker_import_allowed"`
	ProductionAnswerPathOverwriteAllowed bool `json:"production_answer_path_overwrite_allowed"`
	SQLCanonExpansionAllowed             bool `json:"sql_canon_expansion_allowed"`
	CanonOrPortfolioMutationAllowed      bool `json:"canon_or_portfolio_mutation_allowed"`
	OwnerApprovalInferred                bool `json:"owner_approval_inferred"`
	PaperOrLiveTradeAuthorityAllowed     bool `json:"paper_or_live_trade_authority_allowed"`
	BrokerageOrAccountActionAllowed      bool `json:"brokerage_or_account_action_allowed"`
	MoneyMovementAllowed                 bool `json:"money_movement_allowed"`
}

type CurrentState struct {
	StateDB                  string           `json:"state_db"`
	Exists                   bool             `json:"exists"`
	IntegrityCheck           string           `json:"integrity_check,omitempty"`
	UniverseRows             *int64           `json:"universe_rows,omitempty"`
	AllTickerSQLRows         *int64           `json:"all_ticker_sql_rows,omitempty"`
	ProductionCurrentCards   *int64           `json:"production_current_cards,omitempty"`
	ProductionAnswerPathRows *int64           `json:"production_answer_path_rows,omitempty"`
	ReviewMonitorThinRows    *int64           `json:"review_monitor_thin_rows,omitempty"`
	FundamentalSnapshotRows  *int64           `json:"fundamental_snapshot_rows,omitempty"`
	AnalystSnapshotRows      *int64           `json:"analyst_snapshot_rows,omitempty"`
	TickerFamilyStatusRows   *int64           `json:"ticker_family_status_rows,omitempty"`
	CardRegistryRows         *int64           `json:"card_registry_rows,omitempty"`
	MissingCardRows          *int64           `json:"missing_card_rows,omitempty"`
	AuthorityForbiddenRows   *int64           `json:"authority_forbidden_rows,omitempty"`
	PilotFixtures            *int64           `json:"pilot_fixtures,omitempty"`
	LivePilotCandidates      *int64           `json:"live_pilot_candidates,omitempty"`
	PilotProductionOverlap   *int64           `json:"pilot_production_overlap,omitempty"`
	TierCounts               []map[string]any `json:"tier_counts,omitempty"`
}

type Check struct {
	Name     string `json:"name"`
	OK       bool   `json:"ok"`
	Detail   any    `json:"detail"`
	Severity string `json:"severity"`
}

type Validation struct {
	Status   string  `json:"status"`
	Checks   []Check `json:"checks"`
	Failed   int     `json:"failed"`
	Warnings int     `json:"warnings"`
}

type StagingGate struct {
	Phase                string   `json:"phase"`
	ImplementationStatus string   `json:"implementation_status,omitempty"`
	Scope                string   `json:"scope,omitempty"`
	Acceptance           []string `json:"acceptance"`
}

type Report struct {
	SchemaVersion          string            `json:"schema_version"`
	GeneratedAtUTC         string            `json:"generated_at_utc"`
	Status                 string            `json:"status"`
	SQLiteDriver           string            `json:"sqlite_driver"`
	AuthorityBoundary      AuthorityBoundary `json:"authority_boundary"`
	CurrentState           CurrentState      `json:"current_state"`
	CoverageSummary        map[string]any    `json:"coverage_summary"`
	ProviderRuntimeSummary map[string]any    `json:"provider_runtime_summary"`
	Refresh100Summary      map[string]any    `json:"refresh_100_summary"`
	SourceOpenCleanup      map[string]any    `json:"source_open_cleanup_summary"`
	Validation             Validation        `json:"validation"`
	StagingGates           []StagingGate     `json:"staging_gates"`
	PhasedApproach         []StagingGate     `json:"phased_approach"`
	ShardDesign            map[string]any    `json:"shard_design"`
	FreshnessPolicy        []map[string]any  `json:"freshness_policy"`
	EnrichmentPilot        map[string]any    `json:"enrichment_pilot"`
	SourceOpenCleanupGate  map[string]any    `json:"source_open_cleanup_gate"`
	ImplementationStatus   map[string]any    `json:"implementation_status"`
	NextSafeAction         string            `json:"next_safe_action"`
}

type Options struct {
	Root       string
	SQLitePath string
	Driver     string
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
	state := stateCounts(root, driver, sqlitePath)
	coverage := coverageSummary(root)
	provider := providerRuntimeSummary(root)
	refresh := refresh100Summary(root)
	sourceOpen := sourceOpenCleanupSummary(root)
	checks := []Check{
		check("state_db_exists", state.Exists, state.StateDB, "critical"),
		check("state_db_integrity_ok", state.IntegrityCheck == "ok", state.IntegrityCheck, "critical"),
		check("active_sql_rows_supported_scaleout_count", int64PtrInSet(state.AllTickerSQLRows, supportedActiveCounts), map[string]any{"actual": state.AllTickerSQLRows, "supported": []int64{100, 200, 300, 400, 500}}, "critical"),
		check("production_current_cards_empty_sql_first_wait_state", int64PtrEqual(state.ProductionCurrentCards, expectedDeprecatedProduction), map[string]any{"actual": state.ProductionCurrentCards, "expected": expectedDeprecatedProduction, "empty_production_scope_is_valid_wait_state": true, "source": "sql_first_300_cutover"}, "critical"),
		check("production_answer_path_rows_empty_sql_first_wait_state", int64PtrEqual(state.ProductionAnswerPathRows, expectedDeprecatedProduction), map[string]any{"actual": state.ProductionAnswerPathRows, "expected": expectedDeprecatedProduction, "empty_production_scope_is_valid_wait_state": true, "source": "sql_first_300_cutover"}, "critical"),
		check("review_monitor_thin_rows_supported_scaleout_count", int64PtrInSet(state.ReviewMonitorThinRows, supportedReviewMonitorCounts), map[string]any{"actual": state.ReviewMonitorThinRows, "supported": []int64{58, 158, 258, 358, 458}}, "critical"),
		check("fundamental_rows_for_supported_scaleout", int64PtrInSet(state.FundamentalSnapshotRows, supportedActiveCounts), map[string]any{"actual": state.FundamentalSnapshotRows, "supported": []int64{100, 200, 300, 400, 500}}, "critical"),
		check("analyst_rows_for_supported_scaleout", int64PtrInSet(state.AnalystSnapshotRows, supportedActiveCounts), map[string]any{"actual": state.AnalystSnapshotRows, "supported": []int64{100, 200, 300, 400, 500}}, "critical"),
		check("family_status_rows_for_supported_scaleout_x20", familyStatusRowsMatch(state.AllTickerSQLRows, state.TickerFamilyStatusRows), state.TickerFamilyStatusRows, "critical"),
		check("live_pilot_isolated_25", int64PtrEqual(state.LivePilotCandidates, expectedLivePilot), state.LivePilotCandidates, "critical"),
		check("pilot_production_overlap_zero", int64PtrEqual(state.PilotProductionOverlap, 0), state.PilotProductionOverlap, "critical"),
		check("refresh_artifact_supported_scaleout_ok", refresh["status"] == "ok" && intLikeInSet(refresh["all_ticker_sql_rows"], supportedActiveCounts), refresh, "critical"),
		check("coverage_registry_indexes_supported_scaleout", intLikeInSet(coverage["ticker_count_indexed"], supportedActiveCounts), coverage, "warning"),
		check("provider_runtime_proof_review_monitor_ok", provider["status"] == "ok" && intLikeInSet(provider["ok_count"], supportedReviewMonitorCounts) && provider["success_rate"] == float64(1), provider, "warning"),
		check("source_open_cleanup_queue_top_15_ok", sourceOpenCleanupQueueReady(sourceOpen), sourceOpen, "critical"),
		check("shard_targets_sum_500", sumTierTargets() == target500, tierTargets, "critical"),
		check("enrichment_batch_1_bounded_10", len(enrichmentBatch1) == 10, enrichmentBatch1, "critical"),
	}
	failed := 0
	warnings := 0
	for _, check := range checks {
		if !check.OK && check.Severity == "critical" {
			failed++
		} else if !check.OK && check.Severity == "warning" {
			warnings++
		}
	}
	status := "ready_for_source_open_cleanup"
	validationStatus := "ok"
	if failed > 0 {
		status = "blocked"
		validationStatus = "blocked"
	}
	return Report{
		SchemaVersion:          "sql_500_ticker_expansion_design_gate_go.v1",
		GeneratedAtUTC:         reporting.UTCNow(),
		Status:                 status,
		SQLiteDriver:           driver,
		AuthorityBoundary:      AuthorityBoundary{ReportOnly: true},
		CurrentState:           state,
		CoverageSummary:        coverage,
		ProviderRuntimeSummary: provider,
		Refresh100Summary:      refresh,
		SourceOpenCleanup:      sourceOpen,
		Validation:             Validation{Status: validationStatus, Checks: checks, Failed: failed, Warnings: warnings},
		StagingGates:           phasedApproach(),
		PhasedApproach:         phasedApproach(),
		ShardDesign:            shardDesign(),
		FreshnessPolicy:        freshnessPolicy(),
		EnrichmentPilot: map[string]any{
			"batch":             "review_100_enrichment_batch_1",
			"tickers":           enrichmentBatch1,
			"required_families": requiredEnrichmentFamilies,
			"write_target":      "tmp/ticker-intelligence-cards plus tmp/finance-intelligence-state.sqlite derived review rows only",
			"promotion_rule":    "no decision-grade promotion until source-open evidence and validation pass",
		},
		SourceOpenCleanupGate: map[string]any{
			"artifact":                          "tmp/wf78-review-monitor-source-open-cleanup-queue.json",
			"top_pass_count":                    sourceOpen["top_source_open_pass_count"],
			"promotion_ready_count":             sourceOpen["promotion_ready_count"],
			"blocked_source_open_cleanup_count": sourceOpen["blocked_source_open_cleanup_count"],
			"promotion_rule":                    "review-monitor ticker promotion remains blocked until source-open cleanup gate reports promotion_ready for that ticker",
		},
		ImplementationStatus: map[string]any{
			"readiness_shard_gate_implemented":      true,
			"actual_500_import_performed":           false,
			"cron_schedule_changed":                 false,
			"canon_or_portfolio_mutation_performed": false,
			"enrichment_batches_completed":          true,
			"ready_for_source_open_cleanup":         failed == 0,
		},
		NextSafeAction: "Work the top 15 source-open cleanup queue; do not broaden to 500 import or promote review-monitor tickers until source-open blockers clear and this gate remains clean.",
	}
}

func stateCounts(root, driver, sqlitePath string) CurrentState {
	relPath := "tmp/finance-intelligence-state.sqlite"
	dbPath := filepath.Join(root, filepath.FromSlash(relPath))
	state := CurrentState{StateDB: relPath}
	if _, err := os.Stat(dbPath); err != nil {
		return state
	}
	state.Exists = true
	if value, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check"); err == nil {
		state.IntegrityCheck = value
	}
	state.ProductionCurrentCards = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM current_ticker_cards")
	state.UniverseRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM universe")
	state.AllTickerSQLRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM all_ticker_sql_rows")
	state.ProductionAnswerPathRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM universe WHERE production_answer_path_member = 1")
	state.ReviewMonitorThinRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM universe WHERE thin_monitor_row = 1 AND universe_scope = 'review_100_monitor'")
	state.FundamentalSnapshotRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM fundamental_snapshot")
	state.AnalystSnapshotRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM analyst_snapshot")
	state.TickerFamilyStatusRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM ticker_family_status")
	state.CardRegistryRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM card_registry")
	state.MissingCardRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM card_registry WHERE card_exists = 0")
	state.AuthorityForbiddenRows = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM card_registry WHERE authority_forbidden_true_json <> '[]'")
	state.PilotFixtures = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM current_pilot_fixtures")
	state.LivePilotCandidates = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM current_live_pilot_candidates")
	state.PilotProductionOverlap = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM current_live_pilot_candidates WHERE ticker IN (SELECT ticker FROM current_ticker_cards)")
	state.TierCounts = tierCounts(driver, sqlitePath, dbPath)
	return state
}

func check(name string, ok bool, detail any, severity string) Check {
	return Check{Name: name, OK: ok, Detail: detail, Severity: severity}
}

func tierCounts(driver, sqlitePath, dbPath string) []map[string]any {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT tier, universe_scope, COUNT(*) AS rows FROM universe GROUP BY tier, universe_scope ORDER BY tier, universe_scope")
	if err != nil {
		return nil
	}
	out := []map[string]any{}
	for _, row := range rows {
		out = append(out, map[string]any{"tier": row["tier"], "universe_scope": row["universe_scope"], "rows": row["rows"]})
	}
	return out
}

func scalarInt(driver, sqlitePath, dbPath, sql string) *int64 {
	value, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, sql)
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

func intLikeEqual(value any, expected int64) bool {
	switch v := value.(type) {
	case int:
		return int64(v) == expected
	case int64:
		return v == expected
	case float64:
		return int64(v) == expected
	default:
		return false
	}
}

func intLikeInSet(value any, supported map[int64]bool) bool {
	switch v := value.(type) {
	case int:
		return supported[int64(v)]
	case int64:
		return supported[v]
	case float64:
		return supported[int64(v)]
	default:
		return false
	}
}

func sourceOpenCleanupQueueReady(value map[string]any) bool {
	return stringLikeInSet(value["status"], map[string]bool{"ok": true, "blocked": true}) &&
		stringLikeInSet(value["validation_status"], map[string]bool{"ok": true, "blocked": true}) &&
		intLikeInSet(value["review_monitor_cards"], supportedReviewMonitorCounts) &&
		intLikeEqual(value["top_source_open_pass_count"], 15) &&
		intLikeEqual(value["authority_violation_count"], 0)
}

func stringLikeInSet(value any, supported map[string]bool) bool {
	text, ok := value.(string)
	return ok && supported[text]
}

func familyStatusRowsMatch(activeRows, familyRows *int64) bool {
	return activeRows != nil && familyRows != nil && *familyRows == *activeRows*20
}

func sumTierTargets() int64 {
	var total int64
	for _, value := range tierTargets {
		switch v := value.(type) {
		case int:
			total += int64(v)
		case int64:
			total += v
		case float64:
			total += int64(v)
		}
	}
	return total
}

func loadJSON(root, rel string) map[string]any {
	path := filepath.Join(root, filepath.FromSlash(rel))
	data, err := os.ReadFile(path)
	if err != nil {
		return map[string]any{}
	}
	var payload map[string]any
	if err := json.Unmarshal(data, &payload); err != nil {
		return map[string]any{}
	}
	return payload
}

func nestedMap(payload map[string]any, key string) map[string]any {
	if value, ok := payload[key].(map[string]any); ok {
		return value
	}
	return map[string]any{}
}

func coverageSummary(root string) map[string]any {
	payload := loadJSON(root, "tmp/finance-data-coverage-current.json")
	summary := nestedMap(payload, "summary")
	return map[string]any{
		"path":                     "tmp/finance-data-coverage-current.json",
		"exists":                   len(payload) > 0,
		"status":                   payload["status"],
		"ticker_count_indexed":     summary["ticker_count_indexed"],
		"source_artifacts_stale":   summary["source_artifacts_stale"],
		"source_artifacts_present": summary["source_artifacts_present"],
	}
}

func providerRuntimeSummary(root string) map[string]any {
	payload := loadJSON(root, "tmp/wf78-100-ticker-provider-runtime-proof.json")
	summary := nestedMap(payload, "summary")
	policy := nestedMap(payload, "policy")
	return map[string]any{
		"path":                   "tmp/wf78-100-ticker-provider-runtime-proof.json",
		"exists":                 len(payload) > 0,
		"status":                 payload["status"],
		"candidate_count":        summary["candidate_count"],
		"ok_count":               summary["ok_count"],
		"error_count":            summary["error_count"],
		"success_rate":           summary["success_rate"],
		"total_runtime_seconds":  summary["total_runtime_seconds"],
		"max_latency_seconds":    summary["max_latency_seconds"],
		"runtime_budget_seconds": policy["runtime_budget_seconds"],
		"minimum_success_rate":   policy["minimum_success_rate"],
		"circuit_breaker_opened": summary["circuit_breaker_opened"],
	}
}

func refresh100Summary(root string) map[string]any {
	payload := loadJSON(root, "tmp/finance-intelligence-state-refresh-100.json")
	scope := nestedMap(payload, "refresh_scope")
	validation := nestedMap(payload, "state_validation")
	stateSummary := nestedMap(validation, "summary")
	return map[string]any{
		"path":                           "tmp/finance-intelligence-state-refresh-100.json",
		"exists":                         len(payload) > 0,
		"status":                         payload["status"],
		"active_tickers":                 scope["active_tickers"],
		"production_decision_grade_rows": scope["production_decision_grade_rows"],
		"review_monitor_thin_rows":       scope["review_monitor_thin_rows"],
		"state_validation_status":        validation["status"],
		"all_ticker_sql_rows":            stateSummary["all_ticker_sql_rows"],
	}
}

func sourceOpenCleanupSummary(root string) map[string]any {
	payload := loadJSON(root, "tmp/wf78-review-monitor-source-open-cleanup-queue.json")
	summary := nestedMap(payload, "summary")
	validation := nestedMap(payload, "validation")
	return map[string]any{
		"path":                              "tmp/wf78-review-monitor-source-open-cleanup-queue.json",
		"exists":                            len(payload) > 0,
		"status":                            payload["status"],
		"validation_status":                 validation["status"],
		"review_monitor_cards":              summary["review_monitor_cards"],
		"top_source_open_pass_count":        summary["top_source_open_pass_count"],
		"promotion_ready_count":             summary["promotion_ready_count"],
		"blocked_source_open_cleanup_count": summary["blocked_source_open_cleanup_count"],
		"authority_violation_count":         summary["authority_violation_count"],
	}
}

func phasedApproach() []StagingGate {
	return []StagingGate{
		{Phase: "500-S0 baseline and authority freeze", ImplementationStatus: "implemented", Scope: "supported SQL-first active rows; retired production cards/path remain empty; review-monitor thin rows remain supported", Acceptance: []string{"all active rows routable", "retired production answer path remains empty", "no authority widening"}},
		{Phase: "500-S1 enrichment and source-open cleanup gate", ImplementationStatus: "enrichment_complete_cleanup_gate_active", Scope: "all 58 review-monitor cards exist; first bounded cleanup pass ranks top 15 source-open candidates", Acceptance: []string{"cleanup queue validates", "top pass stays bounded to 10-15", "promotion stays review-only until source-open blockers clear"}},
		{Phase: "500-S2 100-to-200 thin-row shard simulation", ImplementationStatus: "design_ready_no_import", Scope: "add candidate shards as proposed rows only; prove runtime/error budget before writes", Acceptance: []string{"A/B freshness unaffected", "C/D rows thin by default", "rollback and no-overwrite proof exists"}},
		{Phase: "500-S3 200/350 operating shard gate", ImplementationStatus: "design_ready_no_import", Scope: "separate A/B daily shards from C/D rotating shards", Acceptance: []string{"daily A/B continues if C/D degrades", "retry/backoff/circuit breaker policy explicit", "cron remains review-only"}},
		{Phase: "500-S4 500 operating mode", ImplementationStatus: "design_ready_no_import", Scope: "500 searchable/routable, about 100 priority-monitored, about 25 decision-grade", Acceptance: []string{"full cards generated selectively", "retail/customer use remains gated", "canon/portfolio stays owner-gated"}},
	}
}

func shardDesign() map[string]any {
	return map[string]any{
		"target_total": target500,
		"tier_targets": tierTargets,
		"shards": []map[string]any{
			{"name": "tier_a_decision_queue", "target": 25, "cadence": "daily plus intraday trigger", "data_depth": "full decision-grade card", "failure_mode": "block action claims, keep route visible"},
			{"name": "tier_b_priority_watch", "target": 75, "cadence": "daily technical, weekly fundamentals/analyst", "data_depth": "priority card with source-open gaps", "failure_mode": "do not promote to decision-grade"},
			{"name": "tier_c_sector_theme_monitor", "target": 150, "cadence": "weekly or event-triggered rotating shards", "data_depth": "thin row plus technical/price freshness", "failure_mode": "stays monitor-only"},
			{"name": "tier_d_broad_radar", "target": 250, "cadence": "monthly/quarterly rotation", "data_depth": "thin route row plus catalyst flags", "failure_mode": "drop/defer shard without affecting A/B"},
		},
		"runtime_policy": map[string]any{
			"preserve_a_b_before_c_d":                     true,
			"batch_size_default":                          25,
			"max_parallel_provider_lanes":                 4,
			"circuit_breaker":                             "open on provider/error-budget failure; never degrade SQL-first routing or resurrect retired production answer path",
			"source_open_required_before_material_claims": true,
		},
	}
}

func freshnessPolicy() []map[string]any {
	return []map[string]any{
		{"tier": "A", "freshness": "price/technical daily plus intraday triggers; fundamentals weekly/event; official evidence on material claim"},
		{"tier": "B", "freshness": "price/technical daily; fundamentals/analyst weekly; risk register on promotion/event"},
		{"tier": "C", "freshness": "weekly or triggered; fundamentals/analyst required only before promotion"},
		{"tier": "D", "freshness": "monthly/quarterly broad radar; no decision-grade claims without promotion"},
	}
}

func Validate(report Report) error {
	if !report.AuthorityBoundary.ReportOnly ||
		report.AuthorityBoundary.BroadTickerImportAllowed ||
		report.AuthorityBoundary.ProductionAnswerPathOverwriteAllowed ||
		report.AuthorityBoundary.SQLCanonExpansionAllowed ||
		report.AuthorityBoundary.CanonOrPortfolioMutationAllowed ||
		report.AuthorityBoundary.OwnerApprovalInferred ||
		report.AuthorityBoundary.PaperOrLiveTradeAuthorityAllowed ||
		report.AuthorityBoundary.BrokerageOrAccountActionAllowed ||
		report.AuthorityBoundary.MoneyMovementAllowed {
		return errors.New("authority false flag widened")
	}
	if report.Validation.Status != "ok" {
		return errors.New("validation not ok")
	}
	return nil
}
