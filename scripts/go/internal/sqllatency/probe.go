package sqllatency

import (
	"math"
	"os"
	"path/filepath"
	"sort"
	"time"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

type BenchmarkSpec struct {
	Database string `json:"database"`
	Group    string `json:"group"`
	Label    string `json:"label"`
	SQL      string `json:"sql"`
}

type Result struct {
	Database string   `json:"database"`
	Group    string   `json:"group"`
	Label    string   `json:"label"`
	Status   string   `json:"status"`
	Rows     *int     `json:"rows,omitempty"`
	ColdMS   *float64 `json:"cold_ms,omitempty"`
	P50MS    *float64 `json:"p50_ms,omitempty"`
	P95MS    *float64 `json:"p95_ms,omitempty"`
	Error    string   `json:"error,omitempty"`
}

type Summary struct {
	Benchmarks      int      `json:"benchmarks"`
	Successful      int      `json:"successful"`
	FailedOrMissing int      `json:"failed_or_missing"`
	MaxP95MS        *float64 `json:"max_p95_ms,omitempty"`
}

type Report struct {
	SchemaVersion  string          `json:"schema_version"`
	GeneratedAtUTC string          `json:"generated_at_utc"`
	Status         string          `json:"status"`
	Root           string          `json:"root"`
	Iterations     int             `json:"iterations"`
	SQLiteDriver   string          `json:"sqlite_driver"`
	SQLitePath     string          `json:"sqlite_path"`
	Summary        Summary         `json:"summary"`
	Results        []Result        `json:"results"`
	Boundary       map[string]bool `json:"authority_boundary"`
	ParityPosture  string          `json:"parity_posture"`
	Benchmarks     []BenchmarkSpec `json:"benchmark_contract"`
}

type Options struct {
	Root       string
	Iterations int
	Driver     string
	SQLitePath string
}

var defaultBenchmarks = []BenchmarkSpec{
	{
		Database: "tmp/workspace-index.sqlite",
		Group:    "workspace-index.sqlite (FTS/retrieval cache)",
		Label:    "FTS5 MATCH entry stop invalidation",
		SQL:      "SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'entry stop invalidation' LIMIT 25",
	},
	{
		Database: "tmp/workspace-index.sqlite",
		Group:    "workspace-index.sqlite (FTS/retrieval cache)",
		Label:    "headings LIKE full scan",
		SQL:      "SELECT * FROM headings WHERE heading LIKE '%Portfolio%'",
	},
	{
		Database: "tmp/workspace-index.sqlite",
		Group:    "workspace-index.sqlite (FTS/retrieval cache)",
		Label:    "freshness subject_key lookup",
		SQL:      "SELECT * FROM freshness WHERE subject_type='document' LIMIT 50",
	},
	{
		Database: "tmp/finance-intelligence-state.sqlite",
		Group:    "finance-intelligence-state.sqlite (42-ticker current state)",
		Label:    "single ticker 4-table join",
		SQL:      "SELECT u.ticker,p.*,e.*,f.* FROM universe u JOIN latest_price_technical p ON p.ticker=u.ticker JOIN entry_stop_reference e ON e.ticker=u.ticker JOIN fundamental_snapshot f ON f.ticker=u.ticker WHERE u.ticker='ETN'",
	},
	{
		Database: "tmp/finance-intelligence-state.sqlite",
		Group:    "finance-intelligence-state.sqlite (42-ticker current state)",
		Label:    "full ticker family status",
		SQL:      "SELECT * FROM ticker_family_status",
	},
	{
		Database: "tmp/finance-intelligence-state.sqlite",
		Group:    "finance-intelligence-state.sqlite (42-ticker current state)",
		Label:    "official evidence index scan",
		SQL:      "SELECT * FROM official_evidence_index",
	},
	{
		Database: "tmp/veritas-artifact-index.sqlite",
		Group:    "veritas-artifact-index.sqlite (proof/index)",
		Label:    "authority_flags scan",
		SQL:      "SELECT * FROM authority_flags",
	},
	{
		Database: "tmp/veritas-artifact-index.sqlite",
		Group:    "veritas-artifact-index.sqlite (proof/index)",
		Label:    "market_events recent",
		SQL:      "SELECT * FROM market_events ORDER BY rowid DESC LIMIT 50",
	},
	{
		Database: "tmp/veritas-artifact-index.sqlite",
		Group:    "veritas-artifact-index.sqlite (proof/index)",
		Label:    "source_field_lineage sample",
		SQL:      "SELECT * FROM source_field_lineage LIMIT 100",
	},
	{
		Database: "tmp/veritas-canon-cache.sqlite",
		Group:    "veritas-canon-cache.sqlite (bounded metadata cache)",
		Label:    "canon_cache_fields full",
		SQL:      "SELECT * FROM canon_cache_fields",
	},
	{
		Database: "tmp/veritas-canon-cache.sqlite",
		Group:    "veritas-canon-cache.sqlite (bounded metadata cache)",
		Label:    "change_ledger scan",
		SQL:      "SELECT * FROM canon_cache_change_ledger",
	},
	{
		Database: "tmp/wf67-paper-position-state.sqlite",
		Group:    "wf67-paper-position-state.sqlite (paper visibility state)",
		Label:    "paper positions",
		SQL:      "SELECT * FROM paper_position_snapshot",
	},
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
	iterations := opts.Iterations
	if iterations < 1 {
		iterations = 1
	}
	results := make([]Result, 0, len(defaultBenchmarks))
	successful := 0
	var maxP95 *float64
	for _, spec := range defaultBenchmarks {
		result := runOne(root, driver, sqlitePath, spec, iterations)
		if result.Status == "ok" {
			successful++
			if result.P95MS != nil && (maxP95 == nil || *result.P95MS > *maxP95) {
				value := *result.P95MS
				maxP95 = &value
			}
		}
		results = append(results, result)
	}
	failed := len(results) - successful
	status := "ok"
	if failed > 0 && successful > 0 {
		status = "warning"
	}
	if successful == 0 {
		status = "critical"
	}
	return Report{
		SchemaVersion:  "go_sql_latency_probe.v1",
		GeneratedAtUTC: reporting.UTCNow(),
		Status:         status,
		Root:           filepath.ToSlash(root),
		Iterations:     iterations,
		SQLiteDriver:   driver,
		SQLitePath:     sqlitePath,
		Summary: Summary{
			Benchmarks:      len(results),
			Successful:      successful,
			FailedOrMissing: failed,
			MaxP95MS:        maxP95,
		},
		Results:       results,
		Boundary:      reporting.ReadOnlyAuthorityBoundary(),
		ParityPosture: "Go read-only latency probe mirrors the Python SQL latency contract for migration readiness; Python remains the primary benchmark owner until parity history is reviewed.",
		Benchmarks:    defaultBenchmarks,
	}
}

func runOne(root, driver, sqlitePath string, spec BenchmarkSpec, iterations int) Result {
	dbPath := filepath.Join(root, filepath.FromSlash(spec.Database))
	result := Result{
		Database: spec.Database,
		Group:    spec.Group,
		Label:    spec.Label,
		Status:   "ok",
	}
	if _, err := os.Stat(dbPath); err != nil {
		result.Status = "missing"
		result.Error = err.Error()
		return result
	}
	coldStarted := time.Now()
	rows, err := sqliteRows(driver, sqlitePath, dbPath, spec.SQL)
	coldMS := float64(time.Since(coldStarted).Microseconds()) / 1000.0
	if err != nil {
		result.Status = "error"
		result.Error = err.Error()
		return result
	}
	result.Rows = &rows
	result.ColdMS = &coldMS
	samples := make([]float64, 0, iterations)
	for i := 0; i < iterations; i++ {
		started := time.Now()
		if _, err := sqliteRows(driver, sqlitePath, dbPath, spec.SQL); err != nil {
			result.Status = "error"
			result.Error = err.Error()
			return result
		}
		samples = append(samples, float64(time.Since(started).Microseconds())/1000.0)
	}
	sort.Float64s(samples)
	p50 := median(samples)
	p95 := percentile(samples, 95)
	result.P50MS = &p50
	result.P95MS = &p95
	return result
}

func sqliteRows(driver string, sqlitePath string, dbPath string, sql string) (int, error) {
	return sqlutil.TextRowCountWithDriver(driver, sqlitePath, dbPath, sql)
}

func median(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	mid := len(values) / 2
	if len(values)%2 == 1 {
		return values[mid]
	}
	return (values[mid-1] + values[mid]) / 2
}

func percentile(values []float64, pct float64) float64 {
	if len(values) == 0 {
		return 0
	}
	index := int(math.Ceil((pct/100.0)*float64(len(values)))) - 1
	if index < 0 {
		index = 0
	}
	if index >= len(values) {
		index = len(values) - 1
	}
	return values[index]
}
