package fieldfamilyparity

import (
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

const SchemaVersion = "go_canon_json_field_family_parity.v1"

var promotedFamilies = []string{
	"answer_path_scope",
	"evidence_freshness",
	"reference_levels",
	"source_lineage",
	"ticker_state",
	"tier_routing_state",
	"universe_membership",
}

var requiredCountTables = []string{
	"answer_path_scope",
	"evidence_freshness",
	"evidence_status",
	"reference_levels",
	"securities",
	"tier_routing_state",
	"universe_membership",
}

var forbiddenAuthorityTerms = []string{
	"capital_deployment_allowed",
	"paper_or_live_execution_allowed",
	"brokerage_or_account_action_allowed",
	"customer_or_external_delivery_allowed",
	"owner_approval_inferred",
	"sql_write_allowed",
	"db_mutation_allowed",
	"cron_schedule_mutation_allowed",
	"portfolio_or_canon_mutation_allowed",
	"archive_delete_apply_allowed",
}

type Options struct {
	Root                 string
	DBPath               string
	SQLitePath           string
	Driver               string
	FinanceAccessPath    string
	ReferenceProofPath   string
	AnswerHarnessPath    string
	WF78RoutingPath      string
	ConsumerRegistryPath string
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
	Checks                    int            `json:"checks"`
	Critical                  int            `json:"critical"`
	Warnings                  int            `json:"warnings"`
	SQLRowCounts              map[string]int `json:"sql_row_counts"`
	JSONCountMismatches       int            `json:"json_count_mismatches"`
	PromotedFamilyCount       int            `json:"promoted_family_count"`
	MissingPromotedFamilies   []string       `json:"missing_promoted_families"`
	SourceLineageFamilyCounts map[string]int `json:"source_lineage_family_counts"`
	SourceHashNullCount       int            `json:"source_hash_null_count"`
	ParityDiffCount           int            `json:"parity_diff_count"`
	AuthorityViolationCount   int            `json:"authority_violation_count"`
}

type Report struct {
	SchemaVersion        string          `json:"schema_version"`
	GeneratedAtUTC       string          `json:"generated_at_utc"`
	Status               string          `json:"status"`
	Root                 string          `json:"root"`
	DBPath               string          `json:"db_path"`
	SQLiteDriver         string          `json:"sqlite_driver"`
	FinanceAccessPath    string          `json:"finance_access_path"`
	ReferenceProofPath   string          `json:"reference_proof_path"`
	AnswerHarnessPath    string          `json:"answer_harness_path"`
	WF78RoutingPath      string          `json:"wf78_routing_path"`
	ConsumerRegistryPath string          `json:"consumer_registry_path"`
	AuthorityBoundary    map[string]bool `json:"authority_boundary"`
	Findings             []Finding       `json:"findings"`
	Summary              Summary         `json:"summary"`
	NextSafeAction       string          `json:"next_safe_action"`
}

type loadedJSON struct {
	Path    string
	Payload map[string]any
	OK      bool
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	driver := defaulted(opts.Driver, sqlutil.DriverInProcess)
	sqlitePath := defaulted(opts.SQLitePath, "sqlite3")
	dbRel := defaulted(opts.DBPath, "state/finance/finance-canon.sqlite")
	financeRel := defaulted(opts.FinanceAccessPath, "tmp/finance-sql-canon-access-validation.json")
	refRel := defaulted(opts.ReferenceProofPath, "tmp/reference-levels-sql-native-source-family-proof.json")
	answerRel := defaulted(opts.AnswerHarnessPath, "tmp/sql-canon-answer-path-ab-harness.json")
	routingRel := defaulted(opts.WF78RoutingPath, "tmp/sql-canon-wf78-routing-parity.json")
	registryRel := defaulted(opts.ConsumerRegistryPath, "tmp/go-sql-consumer-registry-drift-lint.json")

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

	finance := readJSON(root, financeRel, add)
	reference := readJSON(root, refRel, add)
	answer := readJSON(root, answerRel, add)
	routing := readJSON(root, routingRel, add)
	registry := readJSON(root, registryRel, add)

	dbPath := resolve(root, dbRel)
	sqlCounts := map[string]int{}
	sourceLineageFamilyCounts := map[string]int{}
	sourceHashNulls := 0
	if _, err := os.Stat(dbPath); err != nil {
		add(dbRel, "db_exists", "critical", false, err.Error())
	} else {
		add(dbRel, "db_exists", "info", true, "")
		if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
			add(dbRel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
		} else {
			add(dbRel, "sqlite_integrity_check", "info", true, "ok")
		}
		for _, table := range requiredCountTables {
			sqlCounts[table] = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM "+sqlutil.QuoteIdentifier(table)+";", dbRel, add)
		}
		sqlCounts["source_lineage"] = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM source_lineage;", dbRel, add)
		sqlCounts["consumer_migration_registry"] = scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM consumer_migration_registry;", dbRel, add)
		sourceLineageFamilyCounts = sourceLineageCounts(driver, sqlitePath, dbPath, dbRel, add)
		for _, table := range []string{"evidence_freshness", "reference_levels", "tier_routing_state", "source_lineage"} {
			sourceHashNulls += scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM "+sqlutil.QuoteIdentifier(table)+" WHERE source_artifact_path='' OR source_artifact_sha256 IS NULL OR source_artifact_sha256='';", dbRel, add)
		}
		add(dbRel, "source_hashes_present_for_source_backed_families", "critical", sourceHashNulls == 0, sourceHashNulls)
	}

	add(financeRel, "finance_access_status_ok", "critical", text(finance.Payload["status"]) == "ok", text(finance.Payload["status"]))
	add(financeRel, "finance_access_validation_ok", "critical", textAt(finance.Payload, "validation.status") == "ok", textAt(finance.Payload, "validation.status"))
	add(financeRel, "sql_json_canon_owner_true", "critical", boolAt(finance.Payload, "field_family_summary.review_only_sql_json_canon_owner"), boolAt(finance.Payload, "field_family_summary.review_only_sql_json_canon_owner"))
	add(financeRel, "source_open_required_true", "critical", boolAt(finance.Payload, "field_family_summary.source_open_required_before_material_claims"), boolAt(finance.Payload, "field_family_summary.source_open_required_before_material_claims"))

	jsonCountMismatches := 0
	for _, table := range append(requiredCountTables, "source_lineage", "consumer_migration_registry") {
		sqlCount, ok := sqlCounts[table]
		if !ok {
			continue
		}
		jsonCount := intAt(finance.Payload, "counts."+table)
		if sqlCount != jsonCount {
			jsonCountMismatches++
		}
		add(financeRel, "json_count_matches_sql:"+table, "critical", sqlCount == jsonCount, map[string]int{"json": jsonCount, "sql": sqlCount})
	}

	missingFamilies := []string{}
	for _, family := range promotedFamilies {
		if !containsString(stringArray(anyAt(finance.Payload, "field_family_summary.canon_owner_metadata.promoted_field_families")), family) {
			missingFamilies = append(missingFamilies, family)
		}
		add(financeRel, "promoted_family_declared:"+family, "critical", !containsString(missingFamilies, family), family)
		if family != "ticker_state" {
			add(financeRel, "field_family_canon_owner_true:"+family, "critical", boolAt(finance.Payload, "field_family_summary.field_families."+family+".canon_owner"), boolAt(finance.Payload, "field_family_summary.field_families."+family+".canon_owner"))
			add(financeRel, "field_family_sql_primary_true:"+family, "critical", boolAt(finance.Payload, "field_family_summary.field_families."+family+".sql_primary_current_state"), boolAt(finance.Payload, "field_family_summary.field_families."+family+".sql_primary_current_state"))
		}
	}
	sort.Strings(missingFamilies)

	for family, sqlCount := range sourceLineageFamilyCounts {
		jsonCount := intAt(finance.Payload, "field_family_summary.field_families.source_lineage.rows_by_field_family."+family)
		add(financeRel, "source_lineage_family_count_matches_sql:"+family, "critical", sqlCount == jsonCount, map[string]int{"json": jsonCount, "sql": sqlCount})
	}

	parityDiffs := 0
	add(refRel, "reference_proof_status_ok", "critical", text(reference.Payload["status"]) == "ok", text(reference.Payload["status"]))
	add(refRel, "reference_proof_validation_ok", "critical", textAt(reference.Payload, "validation.status") == "ok", textAt(reference.Payload, "validation.status"))
	add(refRel, "reference_sql_first_provenance_clean", "critical", boolAt(reference.Payload, "summary.sql_first_reference_provenance_clean"), boolAt(reference.Payload, "summary.sql_first_reference_provenance_clean"))
	add(refRel, "reference_dry_run_update_zero", "critical", intAt(reference.Payload, "summary.dry_run_sql_update_count") == 0, intAt(reference.Payload, "summary.dry_run_sql_update_count"))
	add(refRel, "reference_row_proof_count_matches_sql", "critical", intAt(reference.Payload, "summary.row_proof_count") == sqlCounts["reference_levels"], map[string]int{"row_proof": intAt(reference.Payload, "summary.row_proof_count"), "sql": sqlCounts["reference_levels"]})

	add(answerRel, "answer_harness_status_ok", "critical", text(answer.Payload["status"]) == "ok", text(answer.Payload["status"]))
	add(answerRel, "answer_harness_validation_ok", "critical", textAt(answer.Payload, "validation.status") == "ok", textAt(answer.Payload, "validation.status"))
	answerDiffs := lenAny(answer.Payload["diffs"])
	parityDiffs += answerDiffs
	add(answerRel, "answer_harness_diffs_empty", "critical", answerDiffs == 0, answerDiffs)
	add(answerRel, "answer_harness_sql_current_counts_match", "critical", intAt(answer.Payload, "sql_count") == intAt(answer.Payload, "current_count"), map[string]int{"sql": intAt(answer.Payload, "sql_count"), "current": intAt(answer.Payload, "current_count")})

	add(routingRel, "wf78_routing_status_ok", "critical", text(routing.Payload["status"]) == "ok", text(routing.Payload["status"]))
	add(routingRel, "wf78_routing_validation_ok", "critical", textAt(routing.Payload, "validation.status") == "ok", textAt(routing.Payload, "validation.status"))
	routingDiffs := intAt(routing.Payload, "diff_count")
	parityDiffs += routingDiffs
	add(routingRel, "wf78_routing_diff_count_zero", "critical", routingDiffs == 0, routingDiffs)
	add(routingRel, "wf78_routing_sql_source_counts_match", "critical", intAt(routing.Payload, "sql_count") == intAt(routing.Payload, "source_count"), map[string]int{"sql": intAt(routing.Payload, "sql_count"), "source": intAt(routing.Payload, "source_count")})

	registryStatus := text(registry.Payload["status"])
	registryCritical := intAt(registry.Payload, "summary.critical")
	registryAdvisoryOnly := registryStatus == "warning" && registryCritical == 0
	add(registryRel, "consumer_registry_drift_status_ok", "critical", registryStatus == "ok" || registryAdvisoryOnly, registryStatus)
	staleHashSeverity := "critical"
	if registryAdvisoryOnly {
		staleHashSeverity = "warning"
	}
	add(registryRel, "consumer_registry_stale_hash_zero", staleHashSeverity, intAt(registry.Payload, "summary.source_hash_mismatch_count") == 0, intAt(registry.Payload, "summary.source_hash_mismatch_count"))

	authorityViolations := []string{}
	for _, packet := range []loadedJSON{finance, reference, answer, routing, registry} {
		authorityViolations = append(authorityViolations, authorityViolationsFor(packet)...)
	}
	sort.Strings(authorityViolations)
	add("tmp", "forbidden_authority_flags_false", "critical", len(authorityViolations) == 0, firstN(authorityViolations, 30))

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:        SchemaVersion,
		GeneratedAtUTC:       reporting.UTCNow(),
		Status:               reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:                 filepath.ToSlash(root),
		DBPath:               filepath.ToSlash(dbRel),
		SQLiteDriver:         sqlutil.NormalizeDriver(driver),
		FinanceAccessPath:    filepath.ToSlash(financeRel),
		ReferenceProofPath:   filepath.ToSlash(refRel),
		AnswerHarnessPath:    filepath.ToSlash(answerRel),
		WF78RoutingPath:      filepath.ToSlash(routingRel),
		ConsumerRegistryPath: filepath.ToSlash(registryRel),
		AuthorityBoundary:    reporting.ReadOnlyAuthorityBoundary(),
		Findings:             findings,
		Summary: Summary{
			Checks:                    base.Checks,
			Critical:                  base.Critical,
			Warnings:                  base.Warnings,
			SQLRowCounts:              sortedCounts(sqlCounts),
			JSONCountMismatches:       jsonCountMismatches,
			PromotedFamilyCount:       len(promotedFamilies),
			MissingPromotedFamilies:   missingFamilies,
			SourceLineageFamilyCounts: sortedCounts(sourceLineageFamilyCounts),
			SourceHashNullCount:       sourceHashNulls,
			ParityDiffCount:           parityDiffs,
			AuthorityViolationCount:   len(authorityViolations),
		},
		NextSafeAction: "Use as read-only SQL-canon/JSON field-family parity proof. If blocked, route to the exact field-family authority repair path; do not answer from stale structured state.",
	}
}

func scalarInt(driver, sqlitePath, dbPath, query, rel string, add func(string, string, string, bool, any)) int {
	value, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(rel, "sql_scalar_query", "critical", false, err.Error())
		return 0
	}
	parsed, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil {
		add(rel, "sql_scalar_parse", "critical", false, value)
		return 0
	}
	return parsed
}

func sourceLineageCounts(driver, sqlitePath, dbPath, rel string, add func(string, string, string, bool, any)) map[string]int {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT field_family, COUNT(*) AS count FROM source_lineage GROUP BY field_family ORDER BY field_family;")
	if err != nil {
		add(rel, "source_lineage_family_counts_read", "critical", false, err.Error())
		return map[string]int{}
	}
	add(rel, "source_lineage_family_counts_read", "info", true, len(rows))
	out := map[string]int{}
	for _, row := range rows {
		out[text(row["field_family"])] = intValue(row["count"])
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
		return loadedJSON{Path: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{Path: relPath, Payload: payload, OK: true}
}

func authorityViolationsFor(packet loadedJSON) []string {
	out := []string{}
	walk(packet.Payload, "", func(path string, value any) {
		lower := strings.ToLower(path)
		for _, term := range forbiddenAuthorityTerms {
			if strings.Contains(lower, term) && truthy(value) {
				out = append(out, packet.Path+":"+path+"="+text(value))
				break
			}
		}
	})
	return out
}

func walk(value any, path string, visit func(string, any)) {
	switch typed := value.(type) {
	case map[string]any:
		for key, child := range typed {
			next := key
			if path != "" {
				next = path + "." + key
			}
			walk(child, next, visit)
		}
	case []any:
		for index, child := range typed {
			walk(child, fmt.Sprintf("%s[%d]", path, index), visit)
		}
	default:
		visit(path, typed)
	}
}

func resolve(root, relPath string) string {
	if filepath.IsAbs(relPath) {
		return relPath
	}
	return filepath.Join(root, filepath.FromSlash(relPath))
}

func anyAt(payload map[string]any, path string) any {
	var current any = payload
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return nil
		}
		current = object[part]
	}
	return current
}

func textAt(payload map[string]any, path string) string {
	return text(anyAt(payload, path))
}

func boolAt(payload map[string]any, path string) bool {
	return truthy(anyAt(payload, path))
}

func intAt(payload map[string]any, path string) int {
	return intValue(anyAt(payload, path))
}

func lenAny(value any) int {
	switch typed := value.(type) {
	case []any:
		return len(typed)
	case []string:
		return len(typed)
	case nil:
		return 0
	default:
		return 1
	}
}

func stringArray(value any) []string {
	raw, ok := value.([]any)
	if !ok {
		return nil
	}
	out := []string{}
	for _, item := range raw {
		value := text(item)
		if value != "" {
			out = append(out, value)
		}
	}
	sort.Strings(out)
	return out
}

func containsString(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
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

func truthy(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case float64:
		return typed != 0
	case int:
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

func defaulted(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func firstN(values []string, n int) []string {
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
