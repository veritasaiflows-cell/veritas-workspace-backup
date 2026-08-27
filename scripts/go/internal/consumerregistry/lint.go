package consumerregistry

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const SchemaVersion = "go_sql_consumer_registry_drift_lint.v1"

var allowedCutoverStates = map[string]bool{
	"not_cut_over":         true,
	"sql_shadow":           true,
	"sql_shadow_validated": true,
	"sql_primary":          true,
	"sql_primary_guarded":  true,
	"blocked":              true,
	"source_producer":      true,
	"archived":             true,
}

type Options struct {
	Root          string
	DBPath        string
	SQLitePath    string
	Driver        string
	InventoryPath string
	BacklogPath   string
	GuardPath     string
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
	Checks                   int            `json:"checks"`
	Critical                 int            `json:"critical"`
	Warnings                 int            `json:"warnings"`
	InventoryConsumerCount   int            `json:"inventory_consumer_count"`
	InventoryBacklogCount    int            `json:"inventory_backlog_count"`
	BacklogCount             int            `json:"backlog_count"`
	RegistryCount            int            `json:"registry_count"`
	MissingRegistryCount     int            `json:"missing_registry_count"`
	ExtraRegistryCount       int            `json:"extra_registry_count"`
	FieldMismatchCount       int            `json:"field_mismatch_count"`
	InvalidCutoverStateCount int            `json:"invalid_cutover_state_count"`
	SourceHashMismatchCount  int            `json:"source_hash_mismatch_count"`
	RawSQLReviewCount        int            `json:"raw_sql_review_count"`
	PriorityCounts           map[string]int `json:"priority_counts"`
	LaneCounts               map[string]int `json:"lane_counts"`
	CutoverStateCounts       map[string]int `json:"cutover_state_counts"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	DBPath            string          `json:"db_path"`
	InventoryPath     string          `json:"inventory_path"`
	BacklogPath       string          `json:"backlog_path"`
	GuardPath         string          `json:"guard_path"`
	SQLiteDriver      string          `json:"sqlite_driver"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

type registryRow struct {
	ConsumerPath         string
	ConsumerType         string
	Priority             string
	MigrationLane        string
	CutoverState         string
	FallbackRequired     int
	ParityRequired       int
	RawSQLNeedsReview    int
	SourceArtifactPath   string
	SourceArtifactSHA256 string
}

type backlogItem struct {
	Path                        string
	Priority                    string
	ConsumerType                string
	MigrationAction             string
	RequiresParityBeforeCutover bool
	RequiresTypedAccessLayer    bool
	FallbackRequired            bool
	RawSQLNeedsReview           bool
}

type loadedJSON struct {
	Path    string
	Payload map[string]any
	Bytes   []byte
	OK      bool
}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	driver := opts.Driver
	if driver == "" {
		driver = sqlutil.DriverInProcess
	}
	sqlitePath := opts.SQLitePath
	if sqlitePath == "" {
		sqlitePath = "sqlite3"
	}
	dbRel := defaulted(opts.DBPath, "state/finance/finance-canon.sqlite")
	inventoryRel := defaulted(opts.InventoryPath, "tmp/sql-canon-consumer-inventory.json")
	backlogRel := defaulted(opts.BacklogPath, "tmp/sql-canon-consumer-migration-backlog.json")
	guardRel := defaulted(opts.GuardPath, "tmp/sql-canon-consumer-registry-guard.json")

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
	inventory := readJSON(root, inventoryRel, add)
	backlog := readJSON(root, backlogRel, add)
	guard := readJSON(root, guardRel, add)

	inventoryConsumerCount := intFromPath(inventory.Payload, "summary.consumer_count")
	inventoryBacklogCount := intFromPath(inventory.Payload, "summary.backlog_count")
	backlogItems := parseBacklogItems(backlog.Payload)
	backlogByPath := map[string]backlogItem{}
	for _, item := range backlogItems {
		backlogByPath[item.Path] = item
	}
	add(inventoryRel, "inventory_status_ok", "critical", text(inventory.Payload["status"]) == "ok", text(inventory.Payload["status"]))
	add(backlogRel, "backlog_status_ready", "critical", text(backlog.Payload["status"]) == "ready", text(backlog.Payload["status"]))
	add(guardRel, "registry_guard_status_ok", "critical", text(guard.Payload["status"]) == "ok", text(guard.Payload["status"]))
	add(inventoryRel, "inventory_backlog_matches_backlog_items", "critical", inventoryBacklogCount == len(backlogItems), map[string]int{"inventory_backlog_count": inventoryBacklogCount, "backlog_items": len(backlogItems)})

	rows := []registryRow{}
	if _, err := os.Stat(dbPath); err != nil {
		add(dbRel, "db_exists", "critical", false, err.Error())
	} else {
		add(dbRel, "db_exists", "info", true, "")
		if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
			add(dbRel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
		} else {
			add(dbRel, "sqlite_integrity_check", "info", true, "ok")
		}
		rows = readRegistryRows(driver, sqlitePath, dbPath, dbRel, add)
	}

	rowByPath := map[string]registryRow{}
	for _, row := range rows {
		rowByPath[row.ConsumerPath] = row
	}

	missing := sortedSetDiff(keys(backlogByPath), keys(rowByPath))
	advisoryMissing := []string{}
	blockingMissing := []string{}
	for _, path := range missing {
		if advisoryMissingRegistryItem(backlogByPath[path]) {
			advisoryMissing = append(advisoryMissing, path)
		} else {
			blockingMissing = append(blockingMissing, path)
		}
	}
	extra := sortedSetDiff(keys(rowByPath), keys(backlogByPath))
	add(dbRel, "registry_path_set_matches_backlog", "critical", len(blockingMissing) == 0, map[string]any{
		"missing":                firstN(blockingMissing, 20),
		"advisory_missing":       firstN(advisoryMissing, 20),
		"extra":                  firstN(extra, 20),
		"missing_count":          len(blockingMissing),
		"advisory_missing_count": len(advisoryMissing),
		"extra_count":            len(extra),
	})

	backlogSHA := sha256Bytes(backlog.Bytes)
	mismatches := []map[string]any{}
	invalidStates := []string{}
	sourceHashMismatches := []string{}
	rawSQLReviewCount := 0
	priorityCounts := map[string]int{}
	laneCounts := map[string]int{}
	cutoverCounts := map[string]int{}

	for _, row := range rows {
		priorityCounts[row.Priority]++
		laneCounts[row.MigrationLane]++
		cutoverCounts[row.CutoverState]++
		if row.RawSQLNeedsReview != 0 {
			rawSQLReviewCount++
		}
		if !allowedCutoverStates[row.CutoverState] {
			invalidStates = append(invalidStates, row.ConsumerPath+"="+row.CutoverState)
		}
		item, ok := backlogByPath[row.ConsumerPath]
		if !ok {
			continue
		}
		if row.SourceArtifactPath != filepath.ToSlash(backlogRel) || row.SourceArtifactSHA256 != backlogSHA {
			sourceHashMismatches = append(sourceHashMismatches, row.ConsumerPath)
		}
		compare := func(field string, db any, source any) {
			if fmt.Sprint(db) != fmt.Sprint(source) {
				mismatches = append(mismatches, map[string]any{"path": row.ConsumerPath, "field": field, "db": db, "backlog": source})
			}
		}
		compare("consumer_type", row.ConsumerType, item.ConsumerType)
		compare("priority", row.Priority, item.Priority)
		compare("migration_lane", row.MigrationLane, migrationLaneFor(item.ConsumerType))
		compare("fallback_required", row.FallbackRequired, boolInt(item.FallbackRequired))
		compare("parity_required", row.ParityRequired, boolInt(item.RequiresParityBeforeCutover))
		compare("raw_sql_needs_review", row.RawSQLNeedsReview, boolInt(item.RawSQLNeedsReview))
	}
	sort.Strings(invalidStates)
	sort.Strings(sourceHashMismatches)
	add(dbRel, "registry_fields_match_backlog", "critical", len(mismatches) == 0, firstNMaps(mismatches, 20))
	add(dbRel, "cutover_states_allowed", "critical", len(invalidStates) == 0, firstN(invalidStates, 20))
	sourceHashSeverity := "critical"
	if len(sourceHashMismatches) > 0 && len(blockingMissing) == 0 && len(extra) == 0 && len(mismatches) == 0 && len(advisoryMissing) > 0 {
		sourceHashSeverity = "warning"
	}
	add(dbRel, "registry_source_artifact_hash_current", sourceHashSeverity, len(sourceHashMismatches) == 0, map[string]any{
		"mismatch_count": len(sourceHashMismatches),
		"examples":       firstN(sourceHashMismatches, 20),
		"current_sha256": backlogSHA,
	})
	add(dbRel, "raw_sql_review_count_zero", "critical", rawSQLReviewCount == 0, rawSQLReviewCount)
	add(dbRel, "guard_registry_count_matches_sql", "critical", intFromPath(guard.Payload, "registry_count") == len(rows), map[string]int{"guard": intFromPath(guard.Payload, "registry_count"), "sql": len(rows)})

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		DBPath:            filepath.ToSlash(dbRel),
		InventoryPath:     filepath.ToSlash(inventoryRel),
		BacklogPath:       filepath.ToSlash(backlogRel),
		GuardPath:         filepath.ToSlash(guardRel),
		SQLiteDriver:      sqlutil.NormalizeDriver(driver),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                   base.Checks,
			Critical:                 base.Critical,
			Warnings:                 base.Warnings,
			InventoryConsumerCount:   inventoryConsumerCount,
			InventoryBacklogCount:    inventoryBacklogCount,
			BacklogCount:             len(backlogItems),
			RegistryCount:            len(rows),
			MissingRegistryCount:     len(missing),
			ExtraRegistryCount:       len(extra),
			FieldMismatchCount:       len(mismatches),
			InvalidCutoverStateCount: len(invalidStates),
			SourceHashMismatchCount:  len(sourceHashMismatches),
			RawSQLReviewCount:        rawSQLReviewCount,
			PriorityCounts:           sortedCounts(priorityCounts),
			LaneCounts:               sortedCounts(laneCounts),
			CutoverStateCounts:       sortedCounts(cutoverCounts),
		},
		NextSafeAction: "Use as read-only implementation-job drift proof. If blocked, refresh inventory/registry through the approved SQL consumer registry guard/sync path; do not suppress real drift.",
	}
}

func readRegistryRows(driver, sqlitePath, dbPath, dbRel string, add func(string, string, string, bool, any)) []registryRow {
	query := `SELECT consumer_path, consumer_type, priority, migration_lane, cutover_state, fallback_required, parity_required, raw_sql_needs_review, source_artifact_path, COALESCE(source_artifact_sha256, '') AS source_artifact_sha256 FROM consumer_migration_registry ORDER BY consumer_path;`
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(dbRel, "registry_rows_read", "critical", false, err.Error())
		return nil
	}
	add(dbRel, "registry_rows_read", "info", true, len(rows))
	out := make([]registryRow, 0, len(rows))
	for _, row := range rows {
		out = append(out, registryRow{
			ConsumerPath:         text(row["consumer_path"]),
			ConsumerType:         text(row["consumer_type"]),
			Priority:             text(row["priority"]),
			MigrationLane:        text(row["migration_lane"]),
			CutoverState:         text(row["cutover_state"]),
			FallbackRequired:     intValue(row["fallback_required"]),
			ParityRequired:       intValue(row["parity_required"]),
			RawSQLNeedsReview:    intValue(row["raw_sql_needs_review"]),
			SourceArtifactPath:   text(row["source_artifact_path"]),
			SourceArtifactSHA256: text(row["source_artifact_sha256"]),
		})
	}
	return out
}

func readJSON(root, relPath string, add func(string, string, string, bool, any)) loadedJSON {
	path := resolve(root, relPath)
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(relPath, "json_exists", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_exists", "info", true, "")
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}, Bytes: bytes}
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{Path: relPath, Payload: payload, Bytes: bytes, OK: true}
}

func parseBacklogItems(payload map[string]any) []backlogItem {
	rawItems, _ := payload["items"].([]any)
	items := []backlogItem{}
	for _, raw := range rawItems {
		itemMap, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		path := text(itemMap["path"])
		if path == "" {
			continue
		}
		items = append(items, backlogItem{
			Path:                        path,
			Priority:                    text(itemMap["priority"]),
			ConsumerType:                text(itemMap["consumer_type"]),
			MigrationAction:             text(itemMap["migration_action"]),
			RequiresParityBeforeCutover: truthy(itemMap["requires_parity_before_cutover"]),
			RequiresTypedAccessLayer:    truthy(itemMap["requires_typed_access_layer"]),
			FallbackRequired:            truthy(itemMap["fallback_required"]),
			RawSQLNeedsReview:           truthy(itemMap["raw_sql_needs_review"]),
		})
	}
	return items
}

func migrationLaneFor(consumerType string) string {
	switch consumerType {
	case "production_or_answer_path_consumer":
		return "answer_path_parity_lane"
	case "finance_routing_or_freshness_consumer":
		return "wf78_wf77_routing_lane"
	case "cron_or_governance_consumer":
		return "cron_pm_governance_lane"
	case "pm_cockpit_consumer":
		return "pm_cockpit_lane"
	case "WF75_internal_product_consumer":
		return "wf75_product_lane"
	case "test_or_parity_consumer":
		return "test_parity_lane"
	case "source_producer_or_loader":
		return "source_loader_lane"
	default:
		return "typed_access_guard_lane"
	}
}

func advisoryMissingRegistryItem(item backlogItem) bool {
	return item.ConsumerType == "test_or_parity_consumer" &&
		item.Priority != "P0" &&
		item.Priority != "P1" &&
		!item.RawSQLNeedsReview &&
		!item.RequiresParityBeforeCutover
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

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
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
		case "1", "true", "yes", "ok", "ready":
			return true
		}
	}
	return false
}

func intValue(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case string:
		parsed, _ := strconv.Atoi(strings.TrimSpace(typed))
		return parsed
	default:
		return 0
	}
}

func boolInt(value bool) int {
	if value {
		return 1
	}
	return 0
}

func intFromPath(payload map[string]any, path string) int {
	var current any = payload
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return 0
		}
		current = object[part]
	}
	return intValue(current)
}

func sha256Bytes(bytes []byte) string {
	sum := sha256.Sum256(bytes)
	return hex.EncodeToString(sum[:])
}

func keys[T any](m map[string]T) []string {
	out := make([]string, 0, len(m))
	for key := range m {
		out = append(out, key)
	}
	sort.Strings(out)
	return out
}

func sortedSetDiff(left, right []string) []string {
	rightSet := map[string]bool{}
	for _, value := range right {
		rightSet[value] = true
	}
	out := []string{}
	for _, value := range left {
		if !rightSet[value] {
			out = append(out, value)
		}
	}
	sort.Strings(out)
	return out
}

func firstN(values []string, n int) []string {
	if len(values) <= n {
		return values
	}
	return values[:n]
}

func firstNMaps(values []map[string]any, n int) []map[string]any {
	if len(values) <= n {
		return values
	}
	return values[:n]
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
