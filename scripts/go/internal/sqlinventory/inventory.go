package sqlinventory

import (
	"os"
	"path/filepath"
	"sort"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

type DBSpec struct {
	Path           string   `json:"path"`
	Group          string   `json:"group"`
	ExpectedTables []string `json:"expected_tables,omitempty"`
}

type TableInventory struct {
	Name  string `json:"name"`
	Type  string `json:"type"`
	Rows  *int64 `json:"rows,omitempty"`
	Error string `json:"error,omitempty"`
}

type DBInventory struct {
	Path           string           `json:"path"`
	Group          string           `json:"group"`
	Status         string           `json:"status"`
	Exists         bool             `json:"exists"`
	IntegrityCheck string           `json:"integrity_check,omitempty"`
	TableCount     int              `json:"table_count"`
	ViewCount      int              `json:"view_count"`
	TotalRows      int64            `json:"total_rows"`
	ExpectedTables []string         `json:"expected_tables,omitempty"`
	MissingTables  []string         `json:"missing_tables,omitempty"`
	Tables         []TableInventory `json:"tables,omitempty"`
	Error          string           `json:"error,omitempty"`
}

type Summary struct {
	Databases      int   `json:"databases"`
	Present        int   `json:"present"`
	Missing        int   `json:"missing"`
	WarningDBs     int   `json:"warning_dbs"`
	BlockedDBs     int   `json:"blocked_dbs"`
	Tables         int   `json:"tables"`
	Views          int   `json:"views"`
	TotalRows      int64 `json:"total_rows"`
	MissingTables  int   `json:"missing_tables"`
	RowCountErrors int   `json:"row_count_errors"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	SQLiteDriver      string          `json:"sqlite_driver"`
	SQLitePath        string          `json:"sqlite_path"`
	Summary           Summary         `json:"summary"`
	Databases         []DBInventory   `json:"databases"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	MigrationPosture  string          `json:"migration_posture"`
	InventoryContract []DBSpec        `json:"inventory_contract"`
}

type Options struct {
	Root       string
	Driver     string
	SQLitePath string
	DBFiles    []string
}

var defaultDBs = []DBSpec{
	{
		Path:           "tmp/workspace-index.sqlite",
		Group:          "workspace_retrieval_index",
		ExpectedTables: []string{"documents", "documents_fts", "freshness", "artifacts"},
	},
	{
		Path:           "tmp/finance-intelligence-state.sqlite",
		Group:          "finance_state_cache",
		ExpectedTables: []string{"universe", "latest_price_technical", "entry_stop_reference", "fundamental_snapshot", "official_evidence_index"},
	},
	{
		Path:           "tmp/veritas-artifact-index.sqlite",
		Group:          "artifact_proof_index",
		ExpectedTables: []string{"artifact_file_state", "authority_flags", "source_artifacts", "validator_runs"},
	},
	{
		Path:           "tmp/veritas-canon-cache.sqlite",
		Group:          "bounded_finance_metadata_cache",
		ExpectedTables: []string{"canon_cache_fields", "canon_cache_change_ledger"},
	},
	{
		Path:           "tmp/json-sql-promotion-index.sqlite",
		Group:          "json_sql_promotion_index",
		ExpectedTables: []string{"json_documents", "promotion_registry", "wf75_service_runs"},
	},
	{
		Path:           "tmp/pm-program-state.sqlite",
		Group:          "pm_control_index",
		ExpectedTables: []string{"pm_runs", "pm_lanes", "pm_artifacts", "pm_next_actions"},
	},
	{
		Path:           "tmp/wf67-paper-position-state.sqlite",
		Group:          "paper_position_visibility",
		ExpectedTables: []string{"paper_position_snapshot"},
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
	specs := specsFromOptions(opts.DBFiles)
	dbs := make([]DBInventory, 0, len(specs))
	summary := Summary{Databases: len(specs)}
	for _, spec := range specs {
		db := inventoryDB(root, driver, sqlitePath, spec)
		dbs = append(dbs, db)
		applySummary(&summary, db)
	}
	warnings := 0
	if summary.WarningDBs > 0 || summary.Missing > 0 || summary.MissingTables > 0 || summary.RowCountErrors > 0 {
		warnings = 1
	}
	status := reporting.StatusFromBlockedWarnings(summary.BlockedDBs, warnings)
	return Report{
		SchemaVersion:     "go_sql_inventory_helper.v1",
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            status,
		Root:              filepath.ToSlash(root),
		SQLiteDriver:      driver,
		SQLitePath:        sqlitePath,
		Summary:           summary,
		Databases:         dbs,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		MigrationPosture:  "First reusable Go SQL helper for fixed read-only inventory, row-count, and readiness summary. Python remains owner of SQL writes, artifact generation, finance judgment, and gated apply paths.",
		InventoryContract: specs,
	}
}

func specsFromOptions(inputs []string) []DBSpec {
	if len(inputs) == 0 {
		return defaultDBs
	}
	specs := make([]DBSpec, 0, len(inputs))
	for _, path := range inputs {
		specs = append(specs, DBSpec{Path: filepath.ToSlash(path), Group: "custom_read_only_inventory"})
	}
	return specs
}

func inventoryDB(root, driver, sqlitePath string, spec DBSpec) DBInventory {
	dbPath := filepath.Join(root, filepath.FromSlash(spec.Path))
	db := DBInventory{
		Path:           spec.Path,
		Group:          spec.Group,
		Status:         "ok",
		ExpectedTables: sortedCopy(spec.ExpectedTables),
	}
	if _, err := os.Stat(dbPath); err != nil {
		db.Status = "missing"
		db.Error = err.Error()
		return db
	}
	db.Exists = true
	integrity, err := scalar(driver, sqlitePath, dbPath, "PRAGMA integrity_check")
	if err != nil {
		db.Status = "blocked"
		db.Error = err.Error()
		return db
	}
	db.IntegrityCheck = integrity
	if integrity != "ok" {
		db.Status = "blocked"
		return db
	}
	tables, err := sqliteObjects(driver, sqlitePath, dbPath)
	if err != nil {
		db.Status = "blocked"
		db.Error = err.Error()
		return db
	}
	tableNames := map[string]bool{}
	for _, table := range tables {
		if table.Type == "table" {
			db.TableCount++
			tableNames[table.Name] = true
			count, err := tableRowCount(driver, sqlitePath, dbPath, table.Name)
			if err != nil {
				table.Error = err.Error()
				if db.Status != "blocked" {
					db.Status = "warning"
				}
			} else {
				table.Rows = &count
				db.TotalRows += count
			}
		} else if table.Type == "view" {
			db.ViewCount++
		}
		db.Tables = append(db.Tables, table)
	}
	for _, expected := range spec.ExpectedTables {
		if !tableNames[expected] {
			db.MissingTables = append(db.MissingTables, expected)
		}
	}
	if len(db.MissingTables) > 0 && db.Status == "ok" {
		db.Status = "warning"
	}
	sort.Slice(db.Tables, func(i, j int) bool {
		if db.Tables[i].Type == db.Tables[j].Type {
			return db.Tables[i].Name < db.Tables[j].Name
		}
		return db.Tables[i].Type < db.Tables[j].Type
	})
	sort.Strings(db.MissingTables)
	return db
}

func applySummary(summary *Summary, db DBInventory) {
	if db.Exists {
		summary.Present++
	} else {
		summary.Missing++
	}
	switch db.Status {
	case "blocked":
		summary.BlockedDBs++
	case "warning", "missing":
		summary.WarningDBs++
	}
	summary.Tables += db.TableCount
	summary.Views += db.ViewCount
	summary.TotalRows += db.TotalRows
	summary.MissingTables += len(db.MissingTables)
	for _, table := range db.Tables {
		if table.Error != "" {
			summary.RowCountErrors++
		}
	}
}

func sqliteObjects(driver, sqlitePath, dbPath string) ([]TableInventory, error) {
	rows, err := jsonRows(driver, sqlitePath, dbPath, "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name")
	if err != nil {
		return nil, err
	}
	out := make([]TableInventory, 0, len(rows))
	for _, row := range rows {
		name, _ := row["name"].(string)
		typ, _ := row["type"].(string)
		if name == "" || typ == "" {
			continue
		}
		out = append(out, TableInventory{Name: name, Type: typ})
	}
	return out, nil
}

func scalar(driver, sqlitePath, dbPath, query string) (string, error) {
	return sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, query)
}

func jsonRows(driver, sqlitePath, dbPath, query string) ([]map[string]any, error) {
	return sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, query)
}

func tableRowCount(driver, sqlitePath, dbPath, table string) (int64, error) {
	return sqlutil.TableRowCountWithDriver(driver, sqlitePath, dbPath, table)
}

func sortedCopy(values []string) []string {
	out := append([]string(nil), values...)
	sort.Strings(out)
	return out
}
