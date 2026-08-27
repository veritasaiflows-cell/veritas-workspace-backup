package bandfreshness

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const SchemaVersion = "go_entry_stop_band_freshness_validator.v1"

var referenceFieldNames = []string{
	"reference_price_low",
	"reference_price_high",
	"reference_invalidation_level",
}

type Options struct {
	Root               string
	CanonDBPath        string
	FinanceStateDBPath string
	CanonCacheDBPath   string
	SQLitePath         string
	Driver             string
	MaxAgeHours        int
	Now                time.Time
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
	Path              string `json:"path"`
	ExpectedSHA256    string `json:"expected_sha256,omitempty"`
	ActualSHA256      string `json:"actual_sha256,omitempty"`
	HashMatchesDisk   bool   `json:"hash_matches_disk"`
	GeneratedAtUTC    string `json:"generated_at_utc,omitempty"`
	FreshnessStatus   string `json:"freshness_status,omitempty"`
	ValidationStatus  string `json:"validation_status,omitempty"`
	AuthorityClass    string `json:"authority_class,omitempty"`
	ReferenceRowCount int    `json:"reference_row_count"`
	LineageRowCount   int    `json:"lineage_row_count"`
	MirrorRowCount    int    `json:"mirror_row_count"`
}

type Summary struct {
	Checks                        int               `json:"checks"`
	Critical                      int               `json:"critical"`
	Warnings                      int               `json:"warnings"`
	ExecutionBoardSHA256          string            `json:"execution_board_sha256"`
	CanonReferenceRows            int               `json:"canon_reference_rows"`
	CanonReferenceRowsWithLevels  int               `json:"canon_reference_rows_with_levels"`
	CanonReferenceSourcePaths     int               `json:"canon_reference_source_paths"`
	FinanceStateMirrorRows        int               `json:"finance_state_mirror_rows"`
	FinanceStateValidMirrorRows   int               `json:"finance_state_valid_mirror_rows"`
	CanonCacheMirrorTickers       int               `json:"canon_cache_mirror_tickers"`
	ReferenceLineageTickers       int               `json:"reference_lineage_tickers"`
	MissingSourcePathCount        int               `json:"missing_source_path_count"`
	MissingSourceHashCount        int               `json:"missing_source_hash_count"`
	HashMismatchCount             int               `json:"hash_mismatch_count"`
	StaleSourceCount              int               `json:"stale_source_count"`
	MissingLineageTickerCount     int               `json:"missing_lineage_ticker_count"`
	IncompleteLineageTickerCount  int               `json:"incomplete_lineage_ticker_count"`
	BlockedStatusCount            int               `json:"blocked_status_count"`
	ForbiddenAuthorityStatusCount int               `json:"forbidden_authority_status_count"`
	ArtifactSummaries             []ArtifactSummary `json:"artifact_summaries"`
}

type Report struct {
	SchemaVersion      string          `json:"schema_version"`
	GeneratedAtUTC     string          `json:"generated_at_utc"`
	Status             string          `json:"status"`
	Root               string          `json:"root"`
	ExecutionBoardPath string          `json:"execution_board_path"`
	CanonDBPath        string          `json:"canon_db_path"`
	FinanceStateDBPath string          `json:"finance_state_db_path"`
	CanonCacheDBPath   string          `json:"canon_cache_db_path"`
	SQLiteDriver       string          `json:"sqlite_driver"`
	MaxAgeHours        int             `json:"max_age_hours"`
	AuthorityBoundary  map[string]bool `json:"authority_boundary"`
	Findings           []Finding       `json:"findings"`
	Summary            Summary         `json:"summary"`
	NextSafeAction     string          `json:"next_safe_action"`
}

type referenceRow struct {
	Ticker         string
	Low            any
	High           any
	Stop           any
	SourcePath     string
	SourceSHA256   string
	GeneratedAtUTC string
	AuthorityClass string
	FallbackRule   string
}

type lineageSummary struct {
	Ticker          string
	FieldCount      int
	RowCount        int
	SourcePath      string
	SourceSHA256    string
	GeneratedAtUTC  string
	SourceStatus    string
	ValidatorStatus string
	AuthorityClass  string
}

type mirrorRow struct {
	Ticker           string
	SourcePath       string
	SourceSHA256     string
	GeneratedAtUTC   string
	FreshnessStatus  string
	ValidationStatus string
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	driver := defaulted(opts.Driver, sqlutil.DriverInProcess)
	sqlitePath := defaulted(opts.SQLitePath, "sqlite3")
	canonRel := defaulted(opts.CanonDBPath, "state/finance/finance-canon.sqlite")
	financeStateRel := defaulted(opts.FinanceStateDBPath, "tmp/finance-intelligence-state.sqlite")
	canonCacheRel := defaulted(opts.CanonCacheDBPath, "tmp/veritas-canon-cache.sqlite")
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

	boardRel := filepath.ToSlash(filepath.Join("03. Portfolio", "Execution Board.md"))
	boardPath := resolve(root, boardRel)
	boardSHA := ""
	if hash, err := fileSHA256(boardPath); err != nil {
		add(boardRel, "execution_board_readable", "critical", false, err.Error())
	} else {
		boardSHA = hash
		add(boardRel, "execution_board_readable", "info", true, "")
		add(boardRel, "execution_board_sha256_present", "info", boardSHA != "", boardSHA)
	}

	canonRows := []referenceRow{}
	lineageByTicker := map[string]lineageSummary{}
	canonPath := resolve(root, canonRel)
	if checkDB(driver, sqlitePath, canonPath, canonRel, true, add) {
		for _, table := range []string{"reference_levels", "source_lineage"} {
			count, err := scalarInt(driver, sqlitePath, canonPath, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='"+escapeSQL(table)+"';")
			add(canonRel, "table_exists:"+table, "critical", err == nil && count == 1, map[string]any{"count": count, "error": errorText(err)})
		}
		canonRows = readReferenceRows(driver, sqlitePath, canonPath, canonRel, add)
		lineageByTicker = readLineage(driver, sqlitePath, canonPath, canonRel, add)
	}

	financeMirror := []mirrorRow{}
	financePath := resolve(root, financeStateRel)
	if checkDB(driver, sqlitePath, financePath, financeStateRel, false, add) {
		financeMirror = readFinanceStateMirror(driver, sqlitePath, financePath, financeStateRel, add)
	}

	canonCacheRows := []mirrorRow{}
	canonCachePath := resolve(root, canonCacheRel)
	if checkDB(driver, sqlitePath, canonCachePath, canonCacheRel, false, add) {
		canonCacheRows = readCanonCacheMirror(driver, sqlitePath, canonCachePath, canonCacheRel, add)
	}

	artifactStats := map[string]*ArtifactSummary{}
	missingSourcePath := 0
	missingSourceHash := 0
	hashMismatches := 0
	staleSources := 0
	blockedStatuses := 0
	forbiddenStatuses := 0
	missingLineageTickers := 0
	incompleteLineageTickers := 0
	canonRowsWithLevels := 0

	for _, row := range canonRows {
		if present(row.Low) && present(row.High) && present(row.Stop) {
			canonRowsWithLevels++
		}
		add(canonRel, "reference_row_has_entry_stop_values:"+row.Ticker, "critical", present(row.Low) && present(row.High) && present(row.Stop), row.Ticker)
		if row.SourcePath == "" {
			missingSourcePath++
		}
		if row.SourceSHA256 == "" {
			missingSourceHash++
		}
		add(canonRel, "reference_source_path_present:"+row.Ticker, "critical", row.SourcePath != "", row.Ticker)
		add(canonRel, "reference_source_hash_present:"+row.Ticker, "critical", row.SourceSHA256 != "", row.Ticker)
		add(canonRel, "reference_authority_review_only:"+row.Ticker, "critical", !forbiddenAuthorityStatus(row.AuthorityClass), row.AuthorityClass)
		if forbiddenAuthorityStatus(row.AuthorityClass) {
			forbiddenStatuses++
		}
		if stale := checkSourceArtifact(root, row.SourcePath, row.SourceSHA256, row.GeneratedAtUTC, maxAgeHours, now, "canon_reference", add); stale {
			staleSources++
		}
		if row.SourcePath != "" {
			summary := artifactFor(artifactStats, row.SourcePath)
			summary.ExpectedSHA256 = row.SourceSHA256
			summary.GeneratedAtUTC = row.GeneratedAtUTC
			summary.AuthorityClass = row.AuthorityClass
			summary.ReferenceRowCount++
		}
		lineage, ok := lineageByTicker[row.Ticker]
		if !ok {
			missingLineageTickers++
		}
		add(canonRel, "reference_lineage_present:"+row.Ticker, "critical", ok, row.Ticker)
		if ok {
			complete := lineage.FieldCount >= len(referenceFieldNames)
			if !complete {
				incompleteLineageTickers++
			}
			add(canonRel, "reference_lineage_has_entry_stop_fields:"+row.Ticker, "critical", complete, map[string]any{"field_count": lineage.FieldCount, "row_count": lineage.RowCount})
			if lineage.SourceSHA256 == "" {
				missingSourceHash++
			}
			if blockedStatus(lineage.SourceStatus) || blockedStatus(lineage.ValidatorStatus) {
				blockedStatuses++
			}
			if forbiddenAuthorityStatus(lineage.AuthorityClass) || forbiddenAuthorityStatus(lineage.SourceStatus) || forbiddenAuthorityStatus(lineage.ValidatorStatus) {
				forbiddenStatuses++
			}
			add(canonRel, "reference_lineage_hash_present:"+row.Ticker, "critical", lineage.SourceSHA256 != "", row.Ticker)
			add(canonRel, "reference_lineage_status_not_blocked:"+row.Ticker, "critical", !blockedStatus(lineage.SourceStatus) && !blockedStatus(lineage.ValidatorStatus), map[string]string{"source_status": lineage.SourceStatus, "validator_status": lineage.ValidatorStatus})
			add(canonRel, "reference_lineage_authority_review_only:"+row.Ticker, "critical", !forbiddenAuthorityStatus(lineage.AuthorityClass), lineage.AuthorityClass)
			if lineage.SourcePath != "" {
				summary := artifactFor(artifactStats, lineage.SourcePath)
				summary.ExpectedSHA256 = firstNonEmpty(summary.ExpectedSHA256, lineage.SourceSHA256)
				summary.GeneratedAtUTC = firstNonEmpty(summary.GeneratedAtUTC, lineage.GeneratedAtUTC)
				summary.ValidationStatus = lineage.ValidatorStatus
				summary.AuthorityClass = firstNonEmpty(summary.AuthorityClass, lineage.AuthorityClass)
				summary.LineageRowCount += lineage.RowCount
			}
		}
	}

	validMirrorRows := 0
	for _, row := range financeMirror {
		if strings.EqualFold(row.ValidationStatus, "ok") && freshStatus(row.FreshnessStatus) {
			validMirrorRows++
		}
		if row.SourcePath == "" && row.SourceSHA256 == "" {
			continue
		}
		if row.SourcePath == "" {
			missingSourcePath++
		}
		if row.SourceSHA256 == "" {
			missingSourceHash++
		}
		add(financeStateRel, "mirror_source_path_present:"+row.Ticker, "critical", row.SourcePath != "", row.Ticker)
		add(financeStateRel, "mirror_source_hash_present:"+row.Ticker, "critical", row.SourceSHA256 != "", row.Ticker)
		if !freshStatus(row.FreshnessStatus) || blockedStatus(row.ValidationStatus) {
			blockedStatuses++
		}
		add(financeStateRel, "mirror_status_current:"+row.Ticker, "critical", freshStatus(row.FreshnessStatus) && !blockedStatus(row.ValidationStatus), map[string]string{"freshness_status": row.FreshnessStatus, "validation_status": row.ValidationStatus})
		if stale := checkSourceArtifact(root, row.SourcePath, row.SourceSHA256, row.GeneratedAtUTC, maxAgeHours, now, "finance_state_mirror", add); stale {
			staleSources++
		}
		summary := artifactFor(artifactStats, row.SourcePath)
		summary.ExpectedSHA256 = firstNonEmpty(summary.ExpectedSHA256, row.SourceSHA256)
		summary.GeneratedAtUTC = firstNonEmpty(summary.GeneratedAtUTC, row.GeneratedAtUTC)
		summary.FreshnessStatus = firstNonEmpty(summary.FreshnessStatus, row.FreshnessStatus)
		summary.ValidationStatus = firstNonEmpty(summary.ValidationStatus, row.ValidationStatus)
		summary.MirrorRowCount++
	}

	canonCacheTickerSet := map[string]bool{}
	for _, row := range canonCacheRows {
		canonCacheTickerSet[row.Ticker] = true
		if row.SourcePath == "" {
			missingSourcePath++
		}
		if row.SourceSHA256 == "" {
			missingSourceHash++
		}
		add(canonCacheRel, "canon_cache_source_path_present:"+row.Ticker, "critical", row.SourcePath != "", row.Ticker)
		add(canonCacheRel, "canon_cache_source_hash_present:"+row.Ticker, "critical", row.SourceSHA256 != "", row.Ticker)
		if !freshStatus(row.FreshnessStatus) || blockedStatus(row.ValidationStatus) {
			blockedStatuses++
		}
		add(canonCacheRel, "canon_cache_status_current:"+row.Ticker, "critical", freshStatus(row.FreshnessStatus) && !blockedStatus(row.ValidationStatus), map[string]string{"freshness_status": row.FreshnessStatus, "validation_status": row.ValidationStatus})
		if forbiddenAuthorityStatus(row.ValidationStatus) {
			forbiddenStatuses++
		}
		if stale := checkSourceArtifact(root, row.SourcePath, row.SourceSHA256, row.GeneratedAtUTC, maxAgeHours, now, "canon_cache_mirror", add); stale {
			staleSources++
		}
		summary := artifactFor(artifactStats, row.SourcePath)
		summary.ExpectedSHA256 = firstNonEmpty(summary.ExpectedSHA256, row.SourceSHA256)
		summary.GeneratedAtUTC = firstNonEmpty(summary.GeneratedAtUTC, row.GeneratedAtUTC)
		summary.FreshnessStatus = firstNonEmpty(summary.FreshnessStatus, row.FreshnessStatus)
		summary.ValidationStatus = firstNonEmpty(summary.ValidationStatus, row.ValidationStatus)
		summary.MirrorRowCount++
	}

	for _, summary := range artifactStats {
		if summary.Path == "" {
			continue
		}
		actual, err := fileSHA256(resolve(root, summary.Path))
		if err == nil {
			summary.ActualSHA256 = actual
			summary.HashMatchesDisk = summary.ExpectedSHA256 == "" || strings.EqualFold(summary.ExpectedSHA256, actual)
			if summary.ExpectedSHA256 != "" && !summary.HashMatchesDisk {
				hashMismatches++
			}
		}
	}

	artifactSummaries := make([]ArtifactSummary, 0, len(artifactStats))
	for _, summary := range artifactStats {
		if summary.Path != "" {
			artifactSummaries = append(artifactSummaries, *summary)
		}
	}
	sort.Slice(artifactSummaries, func(i, j int) bool { return artifactSummaries[i].Path < artifactSummaries[j].Path })

	sourcePaths := map[string]bool{}
	for _, row := range canonRows {
		if row.SourcePath != "" {
			sourcePaths[row.SourcePath] = true
		}
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:      SchemaVersion,
		GeneratedAtUTC:     reporting.UTCNow(),
		Status:             reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:               filepath.ToSlash(root),
		ExecutionBoardPath: boardRel,
		CanonDBPath:        filepath.ToSlash(canonRel),
		FinanceStateDBPath: filepath.ToSlash(financeStateRel),
		CanonCacheDBPath:   filepath.ToSlash(canonCacheRel),
		SQLiteDriver:       sqlutil.NormalizeDriver(driver),
		MaxAgeHours:        maxAgeHours,
		AuthorityBoundary:  reporting.ReadOnlyAuthorityBoundary(),
		Findings:           findings,
		Summary: Summary{
			Checks:                        base.Checks,
			Critical:                      base.Critical,
			Warnings:                      base.Warnings,
			ExecutionBoardSHA256:          boardSHA,
			CanonReferenceRows:            len(canonRows),
			CanonReferenceRowsWithLevels:  canonRowsWithLevels,
			CanonReferenceSourcePaths:     len(sourcePaths),
			FinanceStateMirrorRows:        len(financeMirror),
			FinanceStateValidMirrorRows:   validMirrorRows,
			CanonCacheMirrorTickers:       len(canonCacheTickerSet),
			ReferenceLineageTickers:       len(lineageByTicker),
			MissingSourcePathCount:        missingSourcePath,
			MissingSourceHashCount:        missingSourceHash,
			HashMismatchCount:             hashMismatches,
			StaleSourceCount:              staleSources,
			MissingLineageTickerCount:     missingLineageTickers,
			IncompleteLineageTickerCount:  incompleteLineageTickers,
			BlockedStatusCount:            blockedStatuses,
			ForbiddenAuthorityStatusCount: forbiddenStatuses,
			ArtifactSummaries:             artifactSummaries,
		},
		NextSafeAction: "Use as read-only entry/stop band source-freshness proof. Repair hash, freshness, or lineage drift through the owning finance producers; do not mutate SQL, Markdown, portfolio notes, or execution state from this validator.",
	}
}

func checkDB(driver, sqlitePath, dbPath, rel string, required bool, add func(string, string, string, bool, any)) bool {
	if _, err := os.Stat(dbPath); err != nil {
		severity := "warning"
		if required {
			severity = "critical"
		}
		add(rel, "db_exists", severity, false, err.Error())
		return false
	}
	add(rel, "db_exists", "info", true, "")
	if err := sqlutil.ValidateDriver(driver); err != nil {
		add(rel, "sqlite_driver_supported", "critical", false, err.Error())
		return false
	}
	if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
		add(rel, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
		return false
	}
	add(rel, "sqlite_integrity_check", "info", true, "ok")
	return true
}

func readReferenceRows(driver, sqlitePath, dbPath, rel string, add func(string, string, string, bool, any)) []referenceRow {
	query := `SELECT ticker, reference_price_low, reference_price_high, reference_invalidation_level,
COALESCE(source_artifact_path, '') AS source_artifact_path,
COALESCE(source_artifact_sha256, '') AS source_artifact_sha256,
COALESCE(source_generated_at_utc, '') AS source_generated_at_utc,
COALESCE(authority_class, '') AS authority_class,
COALESCE(fallback_rule, '') AS fallback_rule
FROM reference_levels
ORDER BY ticker;`
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(rel, "reference_rows_read", "critical", false, err.Error())
		return nil
	}
	add(rel, "reference_rows_read", "info", true, len(rows))
	out := make([]referenceRow, 0, len(rows))
	for _, row := range rows {
		out = append(out, referenceRow{
			Ticker:         text(row["ticker"]),
			Low:            row["reference_price_low"],
			High:           row["reference_price_high"],
			Stop:           row["reference_invalidation_level"],
			SourcePath:     text(row["source_artifact_path"]),
			SourceSHA256:   text(row["source_artifact_sha256"]),
			GeneratedAtUTC: text(row["source_generated_at_utc"]),
			AuthorityClass: text(row["authority_class"]),
			FallbackRule:   text(row["fallback_rule"]),
		})
	}
	return out
}

func readLineage(driver, sqlitePath, dbPath, rel string, add func(string, string, string, bool, any)) map[string]lineageSummary {
	query := `SELECT scope_key AS ticker,
COUNT(DISTINCT field_name) AS field_count,
COUNT(*) AS row_count,
MIN(source_artifact_path) AS source_artifact_path,
MIN(COALESCE(source_artifact_sha256, '')) AS source_artifact_sha256,
MAX(COALESCE(source_generated_at_utc, '')) AS source_generated_at_utc,
GROUP_CONCAT(DISTINCT COALESCE(source_status, '')) AS source_status,
GROUP_CONCAT(DISTINCT COALESCE(validator_status, '')) AS validator_status,
GROUP_CONCAT(DISTINCT COALESCE(authority_class, '')) AS authority_class
FROM source_lineage
WHERE field_family='reference_levels'
  AND field_name IN ('reference_price_low', 'reference_price_high', 'reference_invalidation_level')
GROUP BY scope_key
ORDER BY scope_key;`
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(rel, "reference_lineage_read", "critical", false, err.Error())
		return map[string]lineageSummary{}
	}
	add(rel, "reference_lineage_read", "info", true, len(rows))
	out := map[string]lineageSummary{}
	for _, row := range rows {
		ticker := text(row["ticker"])
		if ticker == "" {
			continue
		}
		out[ticker] = lineageSummary{
			Ticker:          ticker,
			FieldCount:      intValue(row["field_count"]),
			RowCount:        intValue(row["row_count"]),
			SourcePath:      text(row["source_artifact_path"]),
			SourceSHA256:    text(row["source_artifact_sha256"]),
			GeneratedAtUTC:  text(row["source_generated_at_utc"]),
			SourceStatus:    text(row["source_status"]),
			ValidatorStatus: text(row["validator_status"]),
			AuthorityClass:  text(row["authority_class"]),
		}
	}
	return out
}

func readFinanceStateMirror(driver, sqlitePath, dbPath, rel string, add func(string, string, string, bool, any)) []mirrorRow {
	query := `SELECT ticker,
COALESCE(source_artifact_path, '') AS source_artifact_path,
COALESCE(source_artifact_hash, '') AS source_artifact_hash,
COALESCE(source_timestamp, '') AS source_timestamp,
COALESCE(freshness_status, '') AS freshness_status,
COALESCE(validation_status, '') AS validation_status
FROM latest_valid_entry_stop_refs
ORDER BY ticker;`
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(rel, "latest_valid_entry_stop_refs_read", "critical", false, err.Error())
		return nil
	}
	add(rel, "latest_valid_entry_stop_refs_read", "info", true, len(rows))
	out := make([]mirrorRow, 0, len(rows))
	for _, row := range rows {
		out = append(out, mirrorRow{
			Ticker:           text(row["ticker"]),
			SourcePath:       text(row["source_artifact_path"]),
			SourceSHA256:     text(row["source_artifact_hash"]),
			GeneratedAtUTC:   text(row["source_timestamp"]),
			FreshnessStatus:  text(row["freshness_status"]),
			ValidationStatus: text(row["validation_status"]),
		})
	}
	return out
}

func readCanonCacheMirror(driver, sqlitePath, dbPath, rel string, add func(string, string, string, bool, any)) []mirrorRow {
	query := `SELECT scope AS ticker,
COALESCE(source_artifact_path, '') AS source_artifact_path,
COALESCE(source_artifact_hash, '') AS source_artifact_hash,
COALESCE(sql_generated_at_utc, '') AS sql_generated_at_utc,
COALESCE(freshness_status, '') AS freshness_status,
COALESCE(validator_status, '') AS validator_status
FROM canon_cache_fields
WHERE field_name IN ('reference_invalidation_level','reference_price_high','reference_price_low')
ORDER BY scope, field_name;`
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		add(rel, "canon_cache_reference_fields_read", "critical", false, err.Error())
		return nil
	}
	add(rel, "canon_cache_reference_fields_read", "info", true, len(rows))
	out := make([]mirrorRow, 0, len(rows))
	for _, row := range rows {
		out = append(out, mirrorRow{
			Ticker:           text(row["ticker"]),
			SourcePath:       text(row["source_artifact_path"]),
			SourceSHA256:     text(row["source_artifact_hash"]),
			GeneratedAtUTC:   text(row["sql_generated_at_utc"]),
			FreshnessStatus:  text(row["freshness_status"]),
			ValidationStatus: text(row["validator_status"]),
		})
	}
	return out
}

func checkSourceArtifact(root, relPath, expectedHash, generated string, maxAgeHours int, now time.Time, prefix string, add func(string, string, string, bool, any)) bool {
	if relPath == "" {
		return false
	}
	fullPath := resolve(root, relPath)
	actualHash, err := fileSHA256(fullPath)
	if err != nil {
		add(relPath, prefix+"_source_artifact_readable", "critical", false, err.Error())
		return false
	}
	add(relPath, prefix+"_source_artifact_readable", "info", true, "")
	if expectedHash != "" {
		add(relPath, prefix+"_source_hash_matches_disk", "warning", strings.EqualFold(expectedHash, actualHash), map[string]string{"expected": expectedHash, "actual": actualHash})
	}
	if generated == "" {
		add(relPath, prefix+"_generated_at_present", "warning", false, "")
		return false
	}
	parsed, err := parseTime(generated)
	if err != nil {
		add(relPath, prefix+"_generated_at_parse", "warning", false, generated)
		return false
	}
	age := now.Sub(parsed)
	stale := age > time.Duration(maxAgeHours)*time.Hour
	add(relPath, prefix+"_source_fresh_within_max_age", "warning", !stale, map[string]any{"generated_at_utc": generated, "age_hours": int(age.Hours()), "max_age_hours": maxAgeHours})
	return stale
}

func artifactFor(values map[string]*ArtifactSummary, path string) *ArtifactSummary {
	path = filepath.ToSlash(path)
	if values[path] == nil {
		values[path] = &ArtifactSummary{Path: path}
	}
	return values[path]
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

func parseTime(value string) (time.Time, error) {
	value = strings.TrimSpace(value)
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed.UTC(), nil
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
		parsed, _ := strconv.Atoi(strings.TrimSpace(typed))
		return parsed
	default:
		return 0
	}
}

func present(value any) bool {
	if value == nil {
		return false
	}
	if text(value) == "" {
		return false
	}
	return true
}

func freshStatus(value string) bool {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "ok", "fresh", "current", "match":
		return true
	default:
		return false
	}
}

func blockedStatus(value string) bool {
	lower := strings.ToLower(strings.TrimSpace(value))
	if lower == "" {
		return false
	}
	for _, term := range []string{"blocked", "critical", "error", "failed", "fail_closed", "stale"} {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func forbiddenAuthorityStatus(value string) bool {
	lower := strings.ToLower(strings.TrimSpace(value))
	for _, term := range []string{"capital_deployment", "trade_execution", "paper_or_live", "owner_approval", "money_movement", "brokerage", "deployment_authority_allowed"} {
		if strings.Contains(lower, term) && !strings.Contains(lower, "no_") && !strings.Contains(lower, "not_") && !strings.Contains(lower, "review_only") {
			return true
		}
	}
	return false
}

func firstNonEmpty(left, right string) string {
	if left != "" {
		return left
	}
	return right
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
