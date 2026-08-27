package sourcefreshness

import (
	"crypto/sha256"
	"encoding/hex"
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

const SchemaVersion = "go_sql_source_artifact_freshness_lint.v1"

type Options struct {
	Root        string
	DBPath      string
	SQLitePath  string
	Driver      string
	MaxAgeHours int
	Now         time.Time
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

type ArtifactSummary struct {
	Path                string `json:"path"`
	LineageRows         int    `json:"lineage_rows"`
	HashVariants        int    `json:"hash_variants"`
	GeneratedAtUTC      string `json:"generated_at_utc,omitempty"`
	SourceStatus        string `json:"source_status,omitempty"`
	ValidatorStatus     string `json:"validator_status,omitempty"`
	SourceArtifactKnown bool   `json:"source_artifact_known"`
	HashMatchesDisk     bool   `json:"hash_matches_disk"`
}

type Summary struct {
	Checks                        int               `json:"checks"`
	Critical                      int               `json:"critical"`
	Warnings                      int               `json:"warnings"`
	LineageRowCount               int               `json:"lineage_row_count"`
	LineageArtifactPathCount      int               `json:"lineage_artifact_path_count"`
	SourceArtifactTableRowCount   int               `json:"source_artifact_table_row_count"`
	MissingFileCount              int               `json:"missing_file_count"`
	HashMismatchCount             int               `json:"hash_mismatch_count"`
	MissingSourceArtifactRowCount int               `json:"missing_source_artifact_row_count"`
	StaleArtifactCount            int               `json:"stale_artifact_count"`
	ThinHumanSurfaceExemptCount   int               `json:"thin_human_surface_exempt_count"`
	BlockedSourceStatusCount      int               `json:"blocked_source_status_count"`
	ForbiddenAuthorityStatusCount int               `json:"forbidden_authority_status_count"`
	ArtifactSummaries             []ArtifactSummary `json:"artifact_summaries"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	DBPath            string          `json:"db_path"`
	SQLiteDriver      string          `json:"sqlite_driver"`
	MaxAgeHours       int             `json:"max_age_hours"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	dbRel := defaulted(opts.DBPath, "state/finance/finance-canon.sqlite")
	driver := defaulted(opts.Driver, sqlutil.DriverInProcess)
	sqlitePath := defaulted(opts.SQLitePath, "sqlite3")
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 240
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
	for _, table := range []string{"source_lineage", "source_artifacts"} {
		count, err := scalarInt(driver, sqlitePath, dbPath, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='"+escapeSQL(table)+"';")
		add(dbRel, "table_exists:"+table, "critical", err == nil && count == 1, map[string]any{"count": count, "error": errorText(err)})
	}

	lineageRows := readRows(driver, sqlitePath, dbPath, dbRel, lineageQuery, add)
	sourceArtifactRows := readRows(driver, sqlitePath, dbPath, dbRel, "SELECT artifact_path, sha256, generated_at_utc, validator_status FROM source_artifacts ORDER BY artifact_path;", add)
	sourceArtifacts := map[string]map[string]any{}
	for _, row := range sourceArtifactRows {
		sourceArtifacts[text(row["artifact_path"])] = row
	}

	lineageRowCount := 0
	missingFiles := 0
	hashMismatches := 0
	missingSourceArtifactRows := 0
	staleArtifacts := 0
	thinHumanSurfaceExemptions := 0
	blockedStatuses := 0
	forbiddenStatuses := 0
	summaries := []ArtifactSummary{}

	for _, row := range lineageRows {
		path := text(row["source_artifact_path"])
		lineageRowsForPath := intValue(row["row_count"])
		lineageRowCount += lineageRowsForPath
		hashVariants := intValue(row["hash_variant_count"])
		expectedHash := text(row["sample_sha256"])
		generatedAt := text(row["max_generated_at_utc"])
		sourceStatus := text(row["source_statuses"])
		validatorStatus := text(row["validator_statuses"])
		add(path, "lineage_artifact_path_present", "critical", path != "", "")
		add(path, "lineage_source_hash_present", "critical", expectedHash != "", "")
		add(path, "lineage_single_hash_per_path", "warning", hashVariants <= 1, hashVariants)

		fullPath := resolve(root, path)
		_, statErr := os.Stat(fullPath)
		if statErr != nil {
			missingFiles++
		}
		add(path, "source_artifact_file_exists", "critical", statErr == nil, errorText(statErr))
		thinHumanSurface := statErr == nil && thinHumanSurfacePolicySource(fullPath)

		hashMatches := false
		if statErr == nil && expectedHash != "" {
			actualHash, err := fileSHA256(fullPath)
			hashMatches = strings.EqualFold(actualHash, expectedHash)
			if err != nil {
				add(path, "source_artifact_hash_readable", "warning", false, err.Error())
			} else if !hashMatches {
				hashMismatches++
				add(path, "source_artifact_hash_matches_lineage", "warning", false, map[string]any{"expected": expectedHash, "actual": actualHash})
			} else {
				add(path, "source_artifact_hash_matches_lineage", "info", true, actualHash)
			}
		}

		sourceArtifactRow, sourceArtifactKnown := sourceArtifacts[path]
		if !sourceArtifactKnown {
			missingSourceArtifactRows++
		}
		add(path, "source_artifacts_registry_row_present", "warning", sourceArtifactKnown, "")
		if sourceArtifactKnown {
			registryHash := text(sourceArtifactRow["sha256"])
			add(path, "source_artifacts_registry_hash_present", "warning", registryHash != "", "")
			if registryHash != "" && expectedHash != "" {
				add(path, "source_artifacts_registry_hash_matches_lineage", "warning", strings.EqualFold(registryHash, expectedHash), map[string]any{"registry": registryHash, "lineage": expectedHash})
			}
		}

		if generatedAt == "" {
			add(path, "source_generated_at_present", "warning", false, "")
		} else if parsed, err := parseTime(generatedAt); err != nil {
			add(path, "source_generated_at_parse", "warning", false, generatedAt)
		} else {
			age := now.Sub(parsed)
			stale := age > time.Duration(maxAgeHours)*time.Hour
			if stale && thinHumanSurface {
				thinHumanSurfaceExemptions++
				add(path, "source_generated_at_policy_surface_exempt", "info", true, map[string]any{
					"generated_at_utc": generatedAt,
					"age_hours":        int(age.Hours()),
					"reason":           "thin human policy/provenance surface; structured freshness is SQL/proof-owned",
				})
			} else if stale {
				staleArtifacts++
				add(path, "source_generated_at_fresh", "warning", false, map[string]any{"generated_at_utc": generatedAt, "age_hours": int(age.Hours())})
			} else {
				add(path, "source_generated_at_fresh", "warning", true, map[string]any{"generated_at_utc": generatedAt, "age_hours": int(age.Hours())})
			}
		}

		if blockedStatus(sourceStatus) || blockedStatus(validatorStatus) {
			blockedStatuses++
		}
		add(path, "source_status_not_blocked", "critical", !blockedStatus(sourceStatus), sourceStatus)
		add(path, "validator_status_not_blocked", "critical", !blockedStatus(validatorStatus), validatorStatus)
		if forbiddenAuthorityStatus(sourceStatus) || forbiddenAuthorityStatus(validatorStatus) {
			forbiddenStatuses++
		}
		add(path, "source_status_no_forbidden_authority", "critical", !forbiddenAuthorityStatus(sourceStatus), sourceStatus)
		add(path, "validator_status_no_forbidden_authority", "critical", !forbiddenAuthorityStatus(validatorStatus), validatorStatus)

		summaries = append(summaries, ArtifactSummary{
			Path:                filepath.ToSlash(path),
			LineageRows:         lineageRowsForPath,
			HashVariants:        hashVariants,
			GeneratedAtUTC:      generatedAt,
			SourceStatus:        sourceStatus,
			ValidatorStatus:     validatorStatus,
			SourceArtifactKnown: sourceArtifactKnown,
			HashMatchesDisk:     hashMatches,
		})
	}

	sort.Slice(summaries, func(i, j int) bool { return summaries[i].Path < summaries[j].Path })
	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		DBPath:            filepath.ToSlash(dbRel),
		SQLiteDriver:      sqlutil.NormalizeDriver(driver),
		MaxAgeHours:       maxAgeHours,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                        base.Checks,
			Critical:                      base.Critical,
			Warnings:                      base.Warnings,
			LineageRowCount:               lineageRowCount,
			LineageArtifactPathCount:      len(lineageRows),
			SourceArtifactTableRowCount:   len(sourceArtifactRows),
			MissingFileCount:              missingFiles,
			HashMismatchCount:             hashMismatches,
			MissingSourceArtifactRowCount: missingSourceArtifactRows,
			StaleArtifactCount:            staleArtifacts,
			ThinHumanSurfaceExemptCount:   thinHumanSurfaceExemptions,
			BlockedSourceStatusCount:      blockedStatuses,
			ForbiddenAuthorityStatusCount: forbiddenStatuses,
			ArtifactSummaries:             summaries,
		},
		NextSafeAction: "Use as read-only SQL source lineage proof. Repair stale or mismatched source artifacts through the owning SQL-canon producers; do not mutate SQL/canon/portfolio state from this validator.",
	}
}

const lineageQuery = `SELECT
  source_artifact_path,
  COUNT(*) AS row_count,
  COUNT(DISTINCT source_artifact_sha256) AS hash_variant_count,
  MIN(source_generated_at_utc) AS min_generated_at_utc,
  MAX(source_generated_at_utc) AS max_generated_at_utc,
  MIN(source_artifact_sha256) AS sample_sha256,
  GROUP_CONCAT(DISTINCT source_status) AS source_statuses,
  GROUP_CONCAT(DISTINCT validator_status) AS validator_statuses
FROM source_lineage
GROUP BY source_artifact_path
ORDER BY source_artifact_path;`

func readRows(driver, sqlitePath, dbPath, dbRel, query string, add func(string, string, string, bool, any)) []map[string]any {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(dbRel, "query:"+firstSQLWords(query, 3), "critical", false, err.Error())
		return nil
	}
	add(dbRel, "query:"+firstSQLWords(query, 3), "info", true, len(rows))
	return rows
}

func scalarInt(driver, sqlitePath, dbPath, query string) (int, error) {
	out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		return 0, err
	}
	var count int
	_, err = fmt.Sscanf(strings.TrimSpace(out), "%d", &count)
	return count, err
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

func thinHumanSurfacePolicySource(path string) bool {
	if strings.ToLower(filepath.Ext(path)) != ".md" {
		return false
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	text := strings.ToLower(string(raw))
	return strings.Contains(text, "thin human surface") &&
		strings.Contains(text, "structured owner") &&
		strings.Contains(text, "state/finance/finance-canon.sqlite")
}

func parseTime(value string) (time.Time, error) {
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported timestamp: %s", value)
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
	switch typed := value.(type) {
	case nil:
		return ""
	case string:
		return strings.TrimSpace(typed)
	default:
		return strings.TrimSpace(fmt.Sprint(typed))
	}
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
		var out int
		fmt.Sscanf(typed, "%d", &out)
		return out
	default:
		return 0
	}
}

func blockedStatus(value string) bool {
	lower := strings.ToLower(value)
	return strings.Contains(lower, "blocked") || strings.Contains(lower, "error") || strings.Contains(lower, "fail")
}

func forbiddenAuthorityStatus(value string) bool {
	lower := strings.ToLower(value)
	for _, term := range []string{"capital_deployment", "trade_execution", "paper_or_live", "owner_approval", "money_movement", "brokerage"} {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func firstSQLWords(query string, n int) string {
	fields := strings.Fields(strings.ReplaceAll(query, "\n", " "))
	if len(fields) < n {
		n = len(fields)
	}
	return strings.Join(fields[:n], "_")
}

func escapeSQL(value string) string {
	return strings.ReplaceAll(value, "'", "''")
}

func errorText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
