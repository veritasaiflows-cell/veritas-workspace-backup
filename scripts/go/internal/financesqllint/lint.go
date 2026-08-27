package financesqllint

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"veritas.local/wf74/internal/reporting"
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
}

type Report struct {
	SchemaVersion  string    `json:"schema_version"`
	GeneratedAtUTC string    `json:"generated_at_utc"`
	Status         string    `json:"status"`
	Root           string    `json:"root"`
	CheckedJSON    []string  `json:"checked_json"`
	CheckedDBs     []string  `json:"checked_dbs"`
	Findings       []Finding `json:"findings"`
	Summary        Summary   `json:"summary"`
	Boundary       string    `json:"boundary"`
}

type Options struct {
	Root       string
	JSONFiles  []string
	DBFiles    []string
	SQLitePath string
	SkipDB     bool
}

var defaultJSONFiles = []string{
	"tmp/finance-data-coverage-current.json",
	"tmp/capital-deployment-recommendation-validation.json",
	"tmp/sql-coverage-guard.json",
	"tmp/sql-latency-benchmark-current.json",
}

var defaultDBFiles = []string{
	"state/finance/finance-canon.sqlite",
	"tmp/veritas-canon-cache.sqlite",
	"tmp/veritas-artifact-index.sqlite",
	"tmp/json-sql-promotion-index.sqlite",
	"tmp/finance-intelligence-state.sqlite",
}

var forbiddenTruthyKeys = map[string]bool{
	"proposal_apply_allowed":                      true,
	"per_packet_owner_approval_inferred":          true,
	"owner_approval_inferred":                     true,
	"owner_approval_inference_allowed":            true,
	"trade_execution_allowed":                     true,
	"trade_or_account_action_allowed":             true,
	"live_brokerage_or_account_action_allowed":    true,
	"brokerage_or_account_action_allowed":         true,
	"paper_order_submit_allowed_by_this_registry": true,
	"paper_order_cancel_allowed_by_this_registry": true,
	"paper_or_live_execution_allowed":             true,
	"sql_as_canon_promotion_allowed":              true,
	"sql_canon_migration_allowed":                 true,
	"full_sql_canon_migration_allowed":            true,
	"tmp_artifact_promotion_allowed":              true,
	"db_path_migration_allowed":                   true,
	"customer_output_allowed":                     true,
}

var forbiddenPositivePatterns = []struct {
	name string
	re   *regexp.Regexp
}{
	{"execution_language", regexp.MustCompile(`(?i)\b(approved|ready|allowed|authorized)\s+(for\s+)?(trade|trading|execution|order|account\s+action|live\s+brokerage)\b`)},
	{"owner_approval_language", regexp.MustCompile(`(?i)\b(owner|randall)\s+approval\s+(is\s+)?(inferred|assumed|automatic)\b`)},
	{"guaranteed_return_language", regexp.MustCompile(`(?i)\b(guaranteed|guarantees)\s+(return|profit|alpha|win\s*rate|performance)\b`)},
	{"sql_canon_promotion_language", regexp.MustCompile(`(?i)\b(sql|sqlite)\s+(is\s+)?(canon|canonical|source\s+of\s+truth|approval\s+surface)\b`)},
	{"proposal_apply_language", regexp.MustCompile(`(?i)\b(proposal|packet)\s+(apply|application)\s+(is\s+)?(allowed|approved|ready|automatic)\b`)},
}

var negativeContext = regexp.MustCompile(`(?i)\b(no|not|never|without|blocked|forbidden|prohibited|disallowed|review[- ]only|not\s+canon|not\s+approval|not\s+execution|owner[- ]gated|requires\s+approval|proposal[- ]only)\b`)

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	jsonFiles := opts.JSONFiles
	if len(jsonFiles) == 0 {
		jsonFiles = defaultJSONFiles
	}
	dbFiles := opts.DBFiles
	if len(dbFiles) == 0 && !opts.SkipDB {
		dbFiles = defaultDBFiles
	}

	var findings []Finding
	add := func(path, check, severity string, ok bool, detail string) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	checkedJSON := scanJSON(root, jsonFiles, add)
	var checkedDBs []string
	if !opts.SkipDB {
		checkedDBs = scanDBs(root, dbFiles, opts.SQLitePath, add)
	}

	baseSummary := reporting.SummarizeFindings(findings)

	return Report{
		SchemaVersion:  "finance_sql_boundary_lint.v1",
		GeneratedAtUTC: reporting.UTCNow(),
		Status:         reporting.StatusFromCounts(baseSummary.Critical, baseSummary.Warnings),
		Root:           filepath.ToSlash(root),
		CheckedJSON:    checkedJSON,
		CheckedDBs:     checkedDBs,
		Findings:       findings,
		Summary:        Summary{Checks: baseSummary.Checks, Critical: baseSummary.Critical, Warnings: baseSummary.Warnings},
		Boundary:       "Read-only Go finance/SQL validator. No SQL writes, SQL-as-canon promotion, canon/portfolio mutation, paper/live/account action, external delivery, or owner approval inference.",
	}
}

func scanJSON(root string, files []string, add func(string, string, string, bool, string)) []string {
	expanded := expandJSONFiles(root, files)
	var checked []string
	for _, rel := range expanded {
		path := filepath.Join(root, filepath.FromSlash(rel))
		bytes, err := os.ReadFile(path)
		if err != nil {
			add(rel, "json_exists", "critical", false, err.Error())
			continue
		}
		checked = append(checked, filepath.ToSlash(rel))
		add(rel, "json_exists", "info", true, "")
		var doc any
		if err := json.Unmarshal(bytes, &doc); err != nil {
			add(rel, "json_valid", "critical", false, err.Error())
			continue
		}
		add(rel, "json_valid", "info", true, "")
		scanAuthorityFlags(rel, doc, add)
		scanPositiveLanguage(rel, string(bytes), add)
	}
	return checked
}

func expandJSONFiles(root string, files []string) []string {
	out := make([]string, 0, len(files)+8)
	seen := map[string]bool{}
	add := func(rel string) {
		rel = filepath.ToSlash(rel)
		if !seen[rel] {
			out = append(out, rel)
			seen[rel] = true
		}
	}
	for _, rel := range files {
		add(rel)
	}
	cards, _ := filepath.Glob(filepath.Join(root, "tmp", "ticker-intelligence-cards", "*.current.json"))
	for i, card := range cards {
		if i >= 8 {
			break
		}
		if rel, err := filepath.Rel(root, card); err == nil {
			add(rel)
		}
	}
	return out
}

func scanAuthorityFlags(path string, value any, add func(string, string, string, bool, string)) {
	var walk func(any, string)
	walk = func(v any, prefix string) {
		switch node := v.(type) {
		case map[string]any:
			for key, child := range node {
				next := key
				if prefix != "" {
					next = prefix + "." + key
				}
				if forbiddenTruthyKeys[key] && isTruthy(child) {
					add(path, "forbidden_truthy_finance_authority_flag", "critical", false, fmt.Sprintf("%s=%v", next, child))
				}
				walk(child, next)
			}
		case []any:
			for i, child := range node {
				walk(child, fmt.Sprintf("%s[%d]", prefix, i))
			}
		}
	}
	walk(value, "")
}

func isTruthy(value any) bool {
	switch v := value.(type) {
	case bool:
		return v
	case float64:
		return v != 0
	case string:
		text := strings.TrimSpace(strings.ToLower(v))
		return text == "true" || text == "allowed" || text == "approved" || text == "ready" || text == "enabled" || text == "yes"
	default:
		return false
	}
}

func scanPositiveLanguage(path, raw string, add func(string, string, string, bool, string)) {
	lines := strings.Split(raw, "\n")
	for lineNo, line := range lines {
		for _, pattern := range forbiddenPositivePatterns {
			loc := pattern.re.FindStringIndex(line)
			if loc == nil {
				continue
			}
			window := contextWindow(line, loc[0], loc[1])
			if negativeContext.MatchString(window) {
				continue
			}
			add(path, pattern.name, "critical", false, fmt.Sprintf("line=%d text=%s", lineNo+1, strings.TrimSpace(window)))
		}
	}
}

func contextWindow(line string, start, end int) string {
	left := start - 80
	if left < 0 {
		left = 0
	}
	right := end + 80
	if right > len(line) {
		right = len(line)
	}
	return line[left:right]
}

func scanDBs(root string, files []string, sqlitePath string, add func(string, string, string, bool, string)) []string {
	var checked []string
	for _, rel := range files {
		path := filepath.Join(root, filepath.FromSlash(rel))
		if _, err := os.Stat(path); err != nil {
			add(rel, "db_exists", "critical", false, err.Error())
			continue
		}
		checked = append(checked, filepath.ToSlash(rel))
		add(rel, "db_exists", "info", true, "")
		if sqlitePath == "" {
			add(rel, "sqlite3_available", "warning", false, "sqlite3 binary not provided")
			continue
		}
		checkSQLiteDB(rel, path, sqlitePath, add)
	}
	return checked
}

func checkSQLiteDB(rel, path, sqlitePath string, add func(string, string, string, bool, string)) {
	if out, err := sqliteScalar(sqlitePath, path, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
		add(rel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
	} else {
		add(rel, "sqlite_integrity_check", "info", true, "ok")
	}

	switch filepath.ToSlash(rel) {
	case "state/finance/finance-canon.sqlite":
		expectCountInSet(sqlitePath, path, rel, "finance_active_rows_supported_scaleout_count", "SELECT COUNT(*) FROM current_active_universe;", []int{100, 200, 300, 400, 500}, add)
		expectCount(sqlitePath, path, rel, "finance_production_answer_rows_fail_closed", "SELECT COUNT(*) FROM current_answer_path;", 0, add)
		expectCountInSet(sqlitePath, path, rel, "finance_review_monitor_rows_supported_scaleout_count", "SELECT COUNT(*) FROM review_monitor_universe;", []int{58, 158, 258, 358, 458}, add)
		expectCount(sqlitePath, path, rel, "finance_execution_flags_zero", "SELECT COUNT(*) FROM evidence_status WHERE paper_or_live_execution_allowed != 0 OR customer_output_allowed != 0;", 0, add)
	case "tmp/veritas-canon-cache.sqlite":
		expectCount(sqlitePath, path, rel, "canon_cache_rows_265", "SELECT COUNT(*) FROM canon_cache_fields;", 265, add)
		expectCount(sqlitePath, path, rel, "canon_cache_validator_not_ok_zero", "SELECT COUNT(*) FROM canon_cache_fields WHERE validator_status != 'ok' OR reconciliation_status != 'match';", 0, add)
	case "tmp/veritas-artifact-index.sqlite":
		expectCount(sqlitePath, path, rel, "artifact_index_forbidden_authority_zero", "SELECT COUNT(*) FROM authority_flags WHERE flag_value != 0 AND flag_name IN ('proposal_apply_allowed','per_packet_owner_approval_inferred','owner_approval_inferred','owner_approval_inference_allowed','trade_execution_allowed','trade_or_account_action_allowed','live_brokerage_or_account_action_allowed','brokerage_or_account_action_allowed','paper_order_submit_allowed_by_this_registry','paper_order_cancel_allowed_by_this_registry','paper_or_live_execution_allowed','sql_as_canon_promotion_allowed','sql_canon_migration_allowed','full_sql_canon_migration_allowed','tmp_artifact_promotion_allowed','db_path_migration_allowed','customer_output_allowed');", 0, add)
	case "tmp/json-sql-promotion-index.sqlite":
		expectCount(sqlitePath, path, rel, "json_sql_tables_exist", "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view');", -1, add)
	case "tmp/finance-intelligence-state.sqlite":
		expectCount(sqlitePath, path, rel, "finance_state_tables_exist", "SELECT COUNT(*) FROM sqlite_master WHERE type IN ('table','view');", -1, add)
	}
}

func expectCountInSet(sqlitePath, dbPath, rel, check, sql string, allowed []int, add func(string, string, string, bool, string)) {
	out, err := sqliteScalar(sqlitePath, dbPath, sql)
	if err != nil {
		add(rel, check, "critical", false, err.Error())
		return
	}
	count, err := strconv.Atoi(strings.TrimSpace(out))
	if err != nil {
		add(rel, check, "critical", false, "non-integer result: "+strings.TrimSpace(out))
		return
	}
	for _, expected := range allowed {
		if count == expected {
			add(rel, check, "info", true, fmt.Sprintf("observed=%d allowed=%v", count, allowed))
			return
		}
	}
	add(rel, check, "critical", false, fmt.Sprintf("allowed=%v observed=%d", allowed, count))
}

func expectCount(sqlitePath, dbPath, rel, check, sql string, expected int, add func(string, string, string, bool, string)) {
	out, err := sqliteScalar(sqlitePath, dbPath, sql)
	if err != nil {
		add(rel, check, "critical", false, err.Error())
		return
	}
	count, err := strconv.Atoi(strings.TrimSpace(out))
	if err != nil {
		add(rel, check, "critical", false, "non-integer result: "+strings.TrimSpace(out))
		return
	}
	if expected >= 0 && count != expected {
		add(rel, check, "critical", false, fmt.Sprintf("expected=%d observed=%d", expected, count))
		return
	}
	if expected < 0 && count <= 0 {
		add(rel, check, "critical", false, fmt.Sprintf("expected positive observed=%d", count))
		return
	}
	add(rel, check, "info", true, fmt.Sprintf("observed=%d", count))
}

func sqliteScalar(sqlitePath string, dbPath string, sql string) (string, error) {
	cmd := exec.Command(sqlitePath, dbPath, sql)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out), err
	}
	return string(out), nil
}
