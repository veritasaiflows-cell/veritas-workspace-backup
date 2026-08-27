package artifactfreshness

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

const SchemaVersion = "go_workflow_artifact_freshness_gate.v1"

type Options struct {
	Root        string
	IndexPath   string
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

func (f Finding) IsOK() bool { return f.OK }

func (f Finding) FindingSeverity() string { return f.Severity }

type Summary struct {
	Checks                 int            `json:"checks"`
	Critical               int            `json:"critical"`
	Warnings               int            `json:"warnings"`
	ArtifactFileRows       int            `json:"artifact_file_rows"`
	SourceFreshnessRows    int            `json:"source_freshness_rows"`
	MissingFileCount       int            `json:"missing_file_count"`
	HashMismatchCount      int            `json:"hash_mismatch_count"`
	StaleCriticalCount     int            `json:"stale_critical_count"`
	StaleWarningCount      int            `json:"stale_warning_count"`
	StopLineCount          int            `json:"stop_line_count"`
	ArtifactStatusCounts   map[string]int `json:"artifact_status_counts"`
	FreshnessClassCounts   map[string]int `json:"freshness_class_counts"`
	CriticalStaleArtifacts []string       `json:"critical_stale_artifacts,omitempty"`
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
		findings = append(findings, Finding{Path: filepath.ToSlash(path), Check: check, Severity: severity, OK: ok, Detail: detail})
	}

	indexPath := resolve(root, indexRel)
	add(indexRel, "artifact_index_exists", "critical", fileExists(indexPath), "")
	if err := sqlutil.ValidateDriver(driver); err != nil {
		add(indexRel, "sqlite_driver_supported", "critical", false, err.Error())
	}
	if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, indexPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
		add(indexRel, "artifact_index_integrity", "critical", false, strings.TrimSpace(out)+" "+errorText(err))
	} else {
		add(indexRel, "artifact_index_integrity", "info", true, "ok")
	}

	fileRows := queryRows(driver, sqlitePath, indexPath, indexRel, `SELECT source_file, artifact_type, file_mtime_utc, file_sha256, status FROM artifact_file_state ORDER BY source_file`, add)
	freshRows := queryRows(driver, sqlitePath, indexPath, indexRel, `SELECT source_file, source_key, path, classification, criticality, generated_at_utc, age_hours, stale_after_hours, stop_line FROM source_freshness_rows ORDER BY source_file, source_key`, add)

	missingFiles := 0
	hashMismatches := 0
	statusCounts := map[string]int{}
	for _, row := range fileRows {
		relPath := text(row["source_file"])
		if relPath == "" {
			add(indexRel, "artifact_source_file_present", "critical", false, row)
			continue
		}
		status := defaulted(text(row["status"]), "unknown")
		statusCounts[status]++
		add(relPath, "artifact_status_indexed_or_file_state", "warning", status == "indexed" || status == "file_state_only", status)
		fullPath := resolve(root, relPath)
		if !fileExists(fullPath) {
			missingFiles++
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
			}
		}
		if mtime := text(row["file_mtime_utc"]); mtime != "" {
			if stale, ok := staleByGenerated(mtime, maxAgeHours, now); ok {
				add(relPath, "file_mtime_within_default_max_age", "warning", !stale, map[string]any{"file_mtime_utc": mtime, "max_age_hours": maxAgeHours})
			}
		}
	}

	staleCritical := 0
	staleWarning := 0
	stopLines := 0
	classCounts := map[string]int{}
	criticalStaleArtifacts := []string{}
	for _, row := range freshRows {
		path := firstNonEmpty(text(row["path"]), text(row["source_file"]))
		classification := defaulted(text(row["classification"]), "unknown")
		classCounts[classification]++
		criticality := strings.ToLower(text(row["criticality"]))
		stopLine := intValue(row["stop_line"]) != 0
		if stopLine {
			stopLines++
		}
		add(path, "source_freshness_stop_line_clear", "critical", !stopLine, row["source_key"])
		stale := false
		if staleAfter := floatValue(row["stale_after_hours"]); staleAfter > 0 {
			stale = floatValue(row["age_hours"]) > staleAfter
		} else if generated := text(row["generated_at_utc"]); generated != "" {
			stale, _ = staleByGenerated(generated, maxAgeHours, now)
		}
		if stale && criticality == "critical" {
			staleCritical++
			criticalStaleArtifacts = append(criticalStaleArtifacts, path)
			add(path, "critical_source_freshness_not_stale", "critical", false, map[string]any{"source_key": row["source_key"], "age_hours": row["age_hours"], "stale_after_hours": row["stale_after_hours"]})
		} else if stale {
			staleWarning++
			add(path, "source_freshness_not_stale", "warning", false, map[string]any{"source_key": row["source_key"], "age_hours": row["age_hours"], "stale_after_hours": row["stale_after_hours"]})
		} else {
			add(path, "source_freshness_not_stale", "info", true, row["source_key"])
		}
	}
	sort.Strings(criticalStaleArtifacts)

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
			Checks:                 base.Checks,
			Critical:               base.Critical,
			Warnings:               base.Warnings,
			ArtifactFileRows:       len(fileRows),
			SourceFreshnessRows:    len(freshRows),
			MissingFileCount:       missingFiles,
			HashMismatchCount:      hashMismatches,
			StaleCriticalCount:     staleCritical,
			StaleWarningCount:      staleWarning,
			StopLineCount:          stopLines,
			ArtifactStatusCounts:   statusCounts,
			FreshnessClassCounts:   classCounts,
			CriticalStaleArtifacts: firstN(criticalStaleArtifacts, 20),
		},
		NextSafeAction: "Use as read-only workflow artifact freshness gate. Refresh owning producers or inspect stale critical rows before workflow advancement.",
	}
}

func queryRows(driver, sqlitePath, dbPath, dbRel, query string, add func(string, string, string, bool, any)) []map[string]any {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(dbRel, "query:"+firstWords(query, 3), "critical", false, err.Error())
		return nil
	}
	add(dbRel, "query:"+firstWords(query, 3), "info", true, len(rows))
	return rows
}

func staleByGenerated(value string, maxAgeHours int, now time.Time) (bool, bool) {
	parsed, err := parseTime(value)
	if err != nil {
		return false, false
	}
	return now.Sub(parsed.UTC()) > time.Duration(maxAgeHours)*time.Hour, true
}

func parseTime(value string) (time.Time, error) {
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported timestamp: %s", value)
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

func floatValue(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case string:
		var out float64
		fmt.Sscanf(typed, "%f", &out)
		return out
	default:
		return 0
	}
}

func defaulted(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func firstWords(value string, n int) string {
	fields := strings.Fields(value)
	if len(fields) < n {
		n = len(fields)
	}
	return strings.Join(fields[:n], "_")
}

func firstN(values []string, n int) []string {
	if len(values) <= n {
		return values
	}
	return values[:n]
}

func errorText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
