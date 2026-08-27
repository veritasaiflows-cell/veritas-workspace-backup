package jsonstruct

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const SchemaVersion = "go_json_proof_structural_validator.v1"

type Options struct {
	Root        string
	IndexPath   string
	SQLitePath  string
	Driver      string
	MaxAgeHours int
	Limit       int
	Now         time.Time
}

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   any    `json:"detail,omitempty"`
}

func (f Finding) IsOK() bool { return f.OK }

func (f Finding) FindingSeverity() string { return f.Severity }

type Summary struct {
	Checks                  int            `json:"checks"`
	Critical                int            `json:"critical"`
	Warnings                int            `json:"warnings"`
	IndexedJSONArtifacts    int            `json:"indexed_json_artifacts"`
	ParsedJSONArtifacts     int            `json:"parsed_json_artifacts"`
	MissingFileCount        int            `json:"missing_file_count"`
	ParseFailureCount       int            `json:"parse_failure_count"`
	HashMismatchCount       int            `json:"hash_mismatch_count"`
	StaleArtifactCount      int            `json:"stale_artifact_count"`
	AuthorityViolationCount int            `json:"authority_violation_count"`
	ArtifactTypes           map[string]int `json:"artifact_types"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	IndexPath         string          `json:"index_path"`
	SQLiteDriver      string          `json:"sqlite_driver"`
	MaxAgeHours       int             `json:"max_age_hours"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	indexRel := defaulted(opts.IndexPath, "tmp/veritas-artifact-index.sqlite")
	driver := defaulted(opts.Driver, sqlutil.DriverInProcess)
	sqlitePath := defaulted(opts.SQLitePath, "sqlite3")
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 168
	}
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

	indexPath := resolve(root, indexRel)
	add(indexRel, "artifact_index_exists", "critical", fileExists(indexPath), "")
	if err := sqlutil.ValidateDriver(driver); err != nil {
		add(indexRel, "sqlite_driver_supported", "critical", false, err.Error())
	} else {
		add(indexRel, "sqlite_driver_supported", "info", true, sqlutil.NormalizeDriver(driver))
	}
	if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, indexPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
		add(indexRel, "artifact_index_integrity", "critical", false, strings.TrimSpace(out)+" "+errorText(err))
	} else {
		add(indexRel, "artifact_index_integrity", "info", true, "ok")
	}

	query := `SELECT source_file, artifact_type, file_mtime_utc, file_sha256, status
FROM artifact_file_state
WHERE lower(source_file) LIKE '%.json'
ORDER BY source_file`
	if opts.Limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", opts.Limit)
	}
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, indexPath, query)
	if err != nil {
		add(indexRel, "artifact_file_state_query", "critical", false, err.Error())
		rows = nil
	} else {
		add(indexRel, "artifact_file_state_query", "info", true, len(rows))
	}

	artifactTypes := map[string]int{}
	parsedCount := 0
	missingCount := 0
	parseFailures := 0
	hashMismatches := 0
	staleCount := 0
	authorityViolations := 0

	for _, row := range rows {
		relPath := text(row["source_file"])
		if relPath == "" {
			add(indexRel, "artifact_source_file_present", "critical", false, row)
			continue
		}
		artifactType := defaulted(text(row["artifact_type"]), "unknown")
		artifactTypes[artifactType]++
		fullPath := resolve(root, relPath)
		if !fileExists(fullPath) {
			missingCount++
			add(relPath, "artifact_file_exists", "critical", false, "")
			continue
		}
		add(relPath, "artifact_file_exists", "info", true, "")

		if expected := text(row["file_sha256"]); expected != "" {
			actual, err := fileSHA256(fullPath)
			if err != nil {
				add(relPath, "artifact_sha256_readable", "warning", false, err.Error())
			} else if !strings.EqualFold(actual, expected) {
				hashMismatches++
				add(relPath, "artifact_sha256_matches_index", "warning", false, map[string]any{"expected": expected, "actual": actual})
			} else {
				add(relPath, "artifact_sha256_matches_index", "info", true, actual)
			}
		}

		payload := map[string]any{}
		bytes, err := os.ReadFile(fullPath)
		if err != nil {
			add(relPath, "json_readable", "critical", false, err.Error())
			continue
		}
		if err := json.Unmarshal(bytes, &payload); err != nil {
			parseFailures++
			add(relPath, "json_parse", "critical", false, err.Error())
			continue
		}
		parsedCount++
		add(relPath, "json_parse", "info", true, "")

		status := text(payload["status"])
		add(relPath, "status_present", "warning", status != "", status)
		add(relPath, "status_vocabulary_not_blocked", "critical", !blockedStatus(status), status)
		schema := text(payload["schema_version"])
		if schema == "" {
			schema = text(payload["schema"])
		}
		generated := timestampText(payload)
		add(relPath, "schema_or_generated_at_present", "warning", schema != "" || generated != "", map[string]any{"schema": schema, "generated_at": generated})
		if generated != "" {
			if stale, ok := freshness(relPath, generated, now, maxAgeHours, add); ok && stale {
				staleCount++
			}
		}
		violations := authorityViolationsIn(payload)
		if len(violations) > 0 {
			authorityViolations += len(violations)
		}
		add(relPath, "forbidden_authority_flags_false", "critical", len(violations) == 0, violations)
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		IndexPath:         filepath.ToSlash(indexRel),
		SQLiteDriver:      sqlutil.NormalizeDriver(driver),
		MaxAgeHours:       maxAgeHours,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                  base.Checks,
			Critical:                base.Critical,
			Warnings:                base.Warnings,
			IndexedJSONArtifacts:    len(rows),
			ParsedJSONArtifacts:     parsedCount,
			MissingFileCount:        missingCount,
			ParseFailureCount:       parseFailures,
			HashMismatchCount:       hashMismatches,
			StaleArtifactCount:      staleCount,
			AuthorityViolationCount: authorityViolations,
			ArtifactTypes:           artifactTypes,
		},
		NextSafeAction: "Use as bulk read-only JSON proof structure lint. Repair artifact producers or rerun indexing; do not mutate source artifacts from this validator.",
	}
}

var forbiddenAuthorityTerms = []string{
	"archive_delete_apply_allowed",
	"brokerage_or_account_action",
	"capital_deployment",
	"canon_or_portfolio_mutation",
	"canonical_mutation_allowed",
	"config_auth_runtime_mutation",
	"cron_schedule_mutation",
	"customer_or_external_delivery",
	"db_mutation",
	"money_movement",
	"owner_approval_inferred",
	"paper_or_live_execution",
	"paper_order_submit_allowed",
	"proposal_apply_allowed",
	"sql_write_or_import",
	"trade_execution_allowed",
	"trade_or_account_action_allowed",
}

func authorityViolationsIn(payload map[string]any) []string {
	violations := []string{}
	for _, key := range []string{"authority_boundary", "authority"} {
		if raw, ok := payload[key]; ok {
			violations = append(violations, authorityViolations(raw, key)...)
		}
	}
	sort.Strings(violations)
	return violations
}

func authorityViolations(value any, prefix string) []string {
	object, ok := value.(map[string]any)
	if !ok {
		return nil
	}
	out := []string{}
	for key, raw := range object {
		path := key
		if prefix != "" {
			path = prefix + "." + key
		}
		if child, ok := raw.(map[string]any); ok {
			out = append(out, authorityViolations(child, path)...)
			continue
		}
		if forbiddenAuthorityKey(key) && truthy(raw) {
			out = append(out, path+"="+text(raw))
		}
	}
	return out
}

func forbiddenAuthorityKey(key string) bool {
	lower := strings.ToLower(key)
	if protectiveAuthorityKey(lower) {
		return false
	}
	for _, term := range forbiddenAuthorityTerms {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func protectiveAuthorityKey(lower string) bool {
	for _, term := range []string{
		"approval_required",
		"owner_approval_required",
		"requires_separate",
		"required_for",
	} {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func freshness(path, generated string, now time.Time, maxAgeHours int, add func(string, string, string, bool, any)) (bool, bool) {
	parsed, err := parseTime(generated)
	if err != nil {
		add(path, "generated_at_parse", "warning", false, generated)
		return false, false
	}
	age := now.Sub(parsed.UTC())
	if age < -5*time.Minute {
		add(path, "generated_at_not_future", "critical", false, fmt.Sprintf("future_by=%s", -age))
		return false, true
	}
	stale := age > time.Duration(maxAgeHours)*time.Hour
	add(path, "freshness_within_max_age", "warning", !stale, map[string]any{"age_hours": int(age.Hours()), "max_age_hours": maxAgeHours})
	return stale, true
}

func timestampText(payload map[string]any) string {
	for _, key := range []string{"generated_at_utc", "generated_at", "indexed_at_utc", "file_mtime_utc"} {
		if value := text(payload[key]); value != "" {
			return value
		}
	}
	return ""
}

func parseTime(value string) (time.Time, error) {
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported timestamp: %s", value)
}

func blockedStatus(value string) bool {
	lower := strings.ToLower(strings.TrimSpace(value))
	for _, term := range []string{"blocked", "critical", "error", "failed", "fail_closed"} {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
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

func fileSHA256(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func resolve(root, relPath string) string {
	if filepath.IsAbs(relPath) {
		return relPath
	}
	return filepath.Join(root, filepath.FromSlash(relPath))
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
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

func errorText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
