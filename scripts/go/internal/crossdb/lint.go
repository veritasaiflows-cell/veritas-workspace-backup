package crossdb

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const SchemaVersion = "go_cross_db_referential_integrity_probe.v1"

type Options struct {
	Root       string
	SQLitePath string
	Driver     string
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

type SourceSummary struct {
	ID                string   `json:"id"`
	DBPath            string   `json:"db_path"`
	SQL               string   `json:"sql"`
	Required          bool     `json:"required"`
	Present           bool     `json:"present"`
	TickerCount       int      `json:"ticker_count"`
	MissingFromSource []string `json:"missing_from_source,omitempty"`
	ExtraInSource     []string `json:"extra_in_source,omitempty"`
}

type DBSummary struct {
	ID                     string `json:"id"`
	Path                   string `json:"path"`
	Required               bool   `json:"required"`
	Present                bool   `json:"present"`
	IntegrityStatus        string `json:"integrity_status,omitempty"`
	ForeignKeyFailureCount int    `json:"foreign_key_failure_count"`
	SourceCount            int    `json:"source_count"`
}

type Summary struct {
	Checks                   int             `json:"checks"`
	Critical                 int             `json:"critical"`
	Warnings                 int             `json:"warnings"`
	DBCount                  int             `json:"db_count"`
	PresentDBCount           int             `json:"present_db_count"`
	MissingOptionalDBCount   int             `json:"missing_optional_db_count"`
	IntegrityFailureCount    int             `json:"integrity_failure_count"`
	ForeignKeyFailureCount   int             `json:"foreign_key_failure_count"`
	ComparedSourceCount      int             `json:"compared_source_count"`
	RequiredSourceDriftCount int             `json:"required_source_drift_count"`
	OptionalSourceDriftCount int             `json:"optional_source_drift_count"`
	BaseTickerCount          int             `json:"base_ticker_count"`
	DBSummaries              []DBSummary     `json:"db_summaries"`
	SourceSummaries          []SourceSummary `json:"source_summaries"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	SQLiteDriver      string          `json:"sqlite_driver"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

type dbSpec struct {
	ID       string
	Path     string
	Required bool
	Sources  []sourceSpec
}

type sourceSpec struct {
	ID       string
	SQL      string
	Required bool
}

var dbSpecs = []dbSpec{
	{
		ID:       "finance_canon",
		Path:     "state/finance/finance-canon.sqlite",
		Required: true,
		Sources: []sourceSpec{
			{ID: "finance_canon.securities_active", SQL: "SELECT ticker FROM securities WHERE active=1", Required: true},
			{ID: "finance_canon.universe_membership", SQL: "SELECT ticker FROM universe_membership", Required: true},
			{ID: "finance_canon.answer_path_scope", SQL: "SELECT ticker FROM answer_path_scope", Required: true},
			{ID: "finance_canon.reference_levels", SQL: "SELECT ticker FROM reference_levels", Required: true},
			{ID: "finance_canon.tier_routing_state", SQL: "SELECT ticker FROM tier_routing_state", Required: true},
			{ID: "finance_canon.current_sql_canon_routing", SQL: "SELECT ticker FROM current_sql_canon_routing", Required: true},
		},
	},
	{
		ID:       "finance_intelligence_state",
		Path:     "tmp/finance-intelligence-state.sqlite",
		Required: false,
		Sources: []sourceSpec{
			{ID: "finance_state.universe", SQL: "SELECT ticker FROM universe", Required: false},
			{ID: "finance_state.entry_stop_reference", SQL: "SELECT ticker FROM entry_stop_reference", Required: false},
			{ID: "finance_state.latest_valid_entry_stop_refs", SQL: "SELECT ticker FROM latest_valid_entry_stop_refs", Required: false},
			{ID: "finance_state.current_ticker_cards", SQL: "SELECT ticker FROM current_ticker_cards", Required: false},
		},
	},
	{
		ID:       "canon_cache",
		Path:     "tmp/veritas-canon-cache.sqlite",
		Required: false,
		Sources: []sourceSpec{
			{ID: "canon_cache.reference_scopes", SQL: "SELECT DISTINCT scope AS ticker FROM canon_cache_fields WHERE field_name IN ('reference_invalidation_level','reference_price_high','reference_price_low')", Required: false},
			{ID: "canon_cache.all_scopes", SQL: "SELECT DISTINCT scope AS ticker FROM canon_cache_fields", Required: false},
		},
	},
	{
		ID:       "canonical_finance_data_plane",
		Path:     "tmp/canonical-finance-data-plane.sqlite",
		Required: false,
		Sources: []sourceSpec{
			{ID: "wf84.security_master_active", SQL: "SELECT ticker FROM security_master WHERE active=1", Required: false},
			{ID: "wf84.universe_membership", SQL: "SELECT ticker FROM universe_membership", Required: false},
			{ID: "wf84.entry_stop_reference", SQL: "SELECT ticker FROM entry_stop_reference", Required: false},
			{ID: "wf84.full_answer_section_context", SQL: "SELECT DISTINCT ticker FROM full_answer_section_context", Required: false},
			{ID: "wf84.v_current_decision_overview", SQL: "SELECT ticker FROM v_current_decision_overview", Required: false},
		},
	},
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	driver := defaulted(opts.Driver, sqlutil.DriverInProcess)
	sqlitePath := defaulted(opts.SQLitePath, "sqlite3")

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

	if err := sqlutil.ValidateDriver(driver); err != nil {
		add("sqlite", "sqlite_driver_supported", "critical", false, err.Error())
	} else {
		add("sqlite", "sqlite_driver_supported", "info", true, sqlutil.NormalizeDriver(driver))
	}

	sourceSets := map[string]map[string]bool{}
	sourceSummaries := []SourceSummary{}
	dbSummaries := []DBSummary{}
	integrityFailures := 0
	foreignKeyFailures := 0
	missingOptionalDBs := 0
	presentDBs := 0

	for _, db := range dbSpecs {
		dbPath := resolve(root, db.Path)
		dbSummary := DBSummary{ID: db.ID, Path: filepath.ToSlash(db.Path), Required: db.Required, SourceCount: len(db.Sources)}
		if _, err := os.Stat(dbPath); err != nil {
			severity := "warning"
			if db.Required {
				severity = "critical"
			} else {
				missingOptionalDBs++
			}
			add(db.Path, "db_exists", severity, false, err.Error())
			dbSummaries = append(dbSummaries, dbSummary)
			continue
		}
		presentDBs++
		dbSummary.Present = true
		add(db.Path, "db_exists", "info", true, "")
		if out, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check;"); err != nil || strings.TrimSpace(out) != "ok" {
			integrityFailures++
			dbSummary.IntegrityStatus = strings.TrimSpace(out)
			add(db.Path, "sqlite_integrity_check", "critical", false, strings.TrimSpace(out)+" "+fmt.Sprint(err))
		} else {
			dbSummary.IntegrityStatus = "ok"
			add(db.Path, "sqlite_integrity_check", "info", true, "ok")
		}
		fkRows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "PRAGMA foreign_key_check;")
		if err != nil {
			add(db.Path, "foreign_key_check_read", "critical", false, err.Error())
		} else {
			dbSummary.ForeignKeyFailureCount = len(fkRows)
			foreignKeyFailures += len(fkRows)
			add(db.Path, "foreign_key_check_empty", "critical", len(fkRows) == 0, firstNMaps(fkRows, 20))
		}
		for _, source := range db.Sources {
			tickers, err := readTickerSet(driver, sqlitePath, dbPath, source.SQL)
			if err != nil {
				severity := "warning"
				if db.Required || source.Required {
					severity = "critical"
				}
				add(db.Path, "ticker_source_read:"+source.ID, severity, false, err.Error())
				sourceSummaries = append(sourceSummaries, SourceSummary{
					ID:       source.ID,
					DBPath:   filepath.ToSlash(db.Path),
					SQL:      source.SQL,
					Required: db.Required || source.Required,
					Present:  false,
				})
				continue
			}
			add(db.Path, "ticker_source_read:"+source.ID, "info", true, len(tickers))
			sourceSets[source.ID] = tickers
			sourceSummaries = append(sourceSummaries, SourceSummary{
				ID:          source.ID,
				DBPath:      filepath.ToSlash(db.Path),
				SQL:         source.SQL,
				Required:    db.Required || source.Required,
				Present:     true,
				TickerCount: len(tickers),
			})
		}
		dbSummaries = append(dbSummaries, dbSummary)
	}

	baseSet := sourceSets["finance_canon.securities_active"]
	requiredDrift := 0
	optionalDrift := 0
	if len(baseSet) == 0 {
		add("state/finance/finance-canon.sqlite", "base_ticker_set_present", "critical", false, "finance_canon.securities_active empty or unreadable")
	} else {
		add("state/finance/finance-canon.sqlite", "base_ticker_set_present", "info", true, len(baseSet))
		for i := range sourceSummaries {
			source := &sourceSummaries[i]
			if !source.Present || source.ID == "finance_canon.securities_active" {
				continue
			}
			current := sourceSets[source.ID]
			missing := sortedSetDiff(keys(baseSet), keys(current))
			extra := sortedSetDiff(keys(current), keys(baseSet))
			source.MissingFromSource = firstN(missing, 50)
			source.ExtraInSource = firstN(extra, 50)
			ok := len(missing) == 0 && len(extra) == 0
			severity := "warning"
			if source.Required {
				severity = "critical"
			}
			if !ok {
				if source.Required {
					requiredDrift++
				} else {
					optionalDrift++
				}
			}
			add(source.DBPath, "ticker_set_matches_base:"+source.ID, severity, ok, map[string]any{
				"missing_count": len(missing),
				"extra_count":   len(extra),
				"missing":       firstN(missing, 20),
				"extra":         firstN(extra, 20),
			})
		}
	}

	sort.Slice(sourceSummaries, func(i, j int) bool { return sourceSummaries[i].ID < sourceSummaries[j].ID })
	sort.Slice(dbSummaries, func(i, j int) bool { return dbSummaries[i].ID < dbSummaries[j].ID })
	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		SQLiteDriver:      sqlutil.NormalizeDriver(driver),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                   base.Checks,
			Critical:                 base.Critical,
			Warnings:                 base.Warnings,
			DBCount:                  len(dbSpecs),
			PresentDBCount:           presentDBs,
			MissingOptionalDBCount:   missingOptionalDBs,
			IntegrityFailureCount:    integrityFailures,
			ForeignKeyFailureCount:   foreignKeyFailures,
			ComparedSourceCount:      len(sourceSets),
			RequiredSourceDriftCount: requiredDrift,
			OptionalSourceDriftCount: optionalDrift,
			BaseTickerCount:          len(baseSet),
			DBSummaries:              dbSummaries,
			SourceSummaries:          sourceSummaries,
		},
		NextSafeAction: "Use as read-only cross-DB ticker referential-integrity proof. Missing generated DBs are warning-grade; repair present DB integrity or required ticker-set drift through the owning producers.",
	}
}

func readTickerSet(driver, sqlitePath, dbPath, query string) (map[string]bool, error) {
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
	if err != nil {
		return nil, err
	}
	out := map[string]bool{}
	for _, row := range rows {
		ticker := strings.ToUpper(strings.TrimSpace(fmt.Sprint(row["ticker"])))
		if ticker == "" || ticker == "<nil>" {
			continue
		}
		out[ticker] = true
	}
	return out, nil
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

func keys(values map[string]bool) []string {
	out := make([]string, 0, len(values))
	for key := range values {
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
