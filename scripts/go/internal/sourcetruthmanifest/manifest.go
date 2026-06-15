package sourcetruthmanifest

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"sort"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

type DBSurfaceSpec struct {
	Name           string
	Path           string
	AuthorityClass string
	MayRoute       bool
	MaySourceOpen  bool
	MayApply       bool
	CurrentOwner   string
	Description    string
}

type SQLiteObject struct {
	Name string `json:"name"`
	Type string `json:"type"`
}

type DBSurface struct {
	Path                string            `json:"path"`
	Exists              bool              `json:"exists"`
	AuthorityClass      string            `json:"authority_class"`
	CurrentOwner        string            `json:"current_owner"`
	MayRoute            bool              `json:"may_route"`
	MaySourceOpen       bool              `json:"may_source_open"`
	MayApply            bool              `json:"may_apply"`
	Description         string            `json:"description"`
	SHA256              string            `json:"sha256,omitempty"`
	Bytes               *int64            `json:"bytes,omitempty"`
	IntegrityCheck      string            `json:"integrity_check,omitempty"`
	ForeignKeyCheckRows int               `json:"foreign_key_check_rows,omitempty"`
	Objects             []SQLiteObject    `json:"objects,omitempty"`
	TableCounts         map[string]*int64 `json:"table_counts,omitempty"`
	Status              string            `json:"status"`
	Error               string            `json:"error,omitempty"`
}

type NoteState struct {
	Path               string `json:"path"`
	Exists             bool   `json:"exists"`
	SHA256             string `json:"sha256,omitempty"`
	Bytes              *int64 `json:"bytes,omitempty"`
	AuthorityClass     string `json:"authority_class"`
	SourceOfTruthToday bool   `json:"source_of_truth_today"`
}

type Summary struct {
	DatabaseSurfaces   int      `json:"database_surfaces"`
	CanonicalNotes     int      `json:"canonical_owner_notes"`
	Errors             []string `json:"errors"`
	SourceOfTruthToday string   `json:"source_of_truth_today"`
	SQLToday           string   `json:"sql_today"`
	NextSafePhase      string   `json:"next_safe_phase"`
}

type Report struct {
	SchemaVersion       string               `json:"schema_version"`
	GeneratedAtUTC      string               `json:"generated_at_utc"`
	Status              string               `json:"status"`
	SQLiteDriver        string               `json:"sqlite_driver"`
	AuthorityBoundary   string               `json:"authority_boundary"`
	AuthorityFlags      map[string]bool      `json:"authority_flags"`
	Summary             Summary              `json:"summary"`
	DatabaseSurfaces    map[string]DBSurface `json:"database_surfaces"`
	CanonicalOwnerNotes []NoteState          `json:"canonical_owner_notes"`
	FieldFamilyPlan     []map[string]any     `json:"field_family_plan"`
	PromotionPhases     []map[string]any     `json:"promotion_phases"`
	StopLines           []string             `json:"stop_lines"`
}

type Options struct {
	Root       string
	SQLitePath string
	Driver     string
}

var falseFlags = map[string]bool{
	"source_of_truth_promotion_allowed_by_this_artifact": false,
	"sql_first_consumer_migration_allowed":               false,
	"sql_canon_expansion_allowed":                        false,
	"ticker_import_allowed":                              false,
	"production_answer_path_change_allowed":              false,
	"canonical_markdown_mutation_allowed":                false,
	"portfolio_mutation_allowed":                         false,
	"owner_approval_inferred":                            false,
	"paper_or_live_execution_allowed":                    false,
	"brokerage_or_account_action_allowed":                false,
	"money_movement_allowed":                             false,
	"customer_or_external_delivery_allowed":              false,
	"destructive_cleanup_allowed":                        false,
	"config_auth_channel_runtime_mutation_allowed":       false,
}

var dbSurfaces = []DBSurfaceSpec{
	{
		Name: "artifact_index", Path: "tmp/veritas-artifact-index.sqlite",
		AuthorityClass: "derived_proof_index_staging_only", MayRoute: true,
		CurrentOwner: "scripts/artifact_index.py",
		Description:  "Fast artifact/proof cockpit and lineage index. It routes to source artifacts; it is not canon.",
	},
	{
		Name: "canon_cache", Path: "tmp/veritas-canon-cache.sqlite",
		AuthorityClass: "bounded_metadata_mirror_cache_only", MayRoute: true,
		CurrentOwner: "WF72 SQL-canon/cache guarded metadata boundary",
		Description:  "Bounded metadata mirror/cache with fallback/source-open requirements. It is not broad SQL truth.",
	},
	{
		Name: "finance_intelligence_state", Path: "tmp/finance-intelligence-state.sqlite",
		AuthorityClass: "current_state_query_and_pilot_staging_only", MayRoute: true,
		CurrentOwner: "scripts/finance_intelligence_state.py and WF78 pilot state",
		Description:  "Ticker-card and entry/stop query surface; production path remains 42-card/file-backed.",
	},
	{
		Name: "paper_position_state", Path: "tmp/wf67-paper-position-state.sqlite",
		AuthorityClass: "paper_position_visibility_only", MayRoute: true,
		CurrentOwner: "WF67 paper-position read-only visibility",
		Description:  "Read-only paper position visibility. It grants no submit, cancel, sell, live, or account authority.",
	},
}

var canonicalOwnerNotes = []string{
	"03. Portfolio/Execution Board.md",
	"03. Portfolio/Portfolio Snapshot.md",
	"04. Research/Coverage and Watchlist.md",
	"02. Markets/Macro Regime Dashboard.md",
	"07. Risk/Risk Rules.md",
	"06. Playbooks/Active Workflows.md",
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
	dbs := map[string]DBSurface{}
	errs := []string{}
	for _, spec := range dbSurfaces {
		state := inspectDB(root, driver, sqlitePath, spec)
		dbs[spec.Name] = state
		if !state.Exists {
			errs = append(errs, spec.Name+":missing")
		} else if state.IntegrityCheck != "" && state.IntegrityCheck != "ok" {
			errs = append(errs, spec.Name+":integrity:"+state.IntegrityCheck)
		} else if state.Status == "error" {
			errs = append(errs, spec.Name+":error")
		}
	}
	notes := make([]NoteState, 0, len(canonicalOwnerNotes))
	for _, path := range canonicalOwnerNotes {
		state := noteState(root, path)
		notes = append(notes, state)
		if !state.Exists {
			errs = append(errs, state.Path+":missing")
		}
	}
	status := "ready_for_phase2_parity_scaffold"
	if len(errs) > 0 {
		status = "blocked_for_sql_source_truth_promotion"
	}
	return Report{
		SchemaVersion:     "sql_source_truth_authority_manifest_go.v1",
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            status,
		SQLiteDriver:      driver,
		AuthorityBoundary: "report_only_no_sql_writes_no_source_of_truth_promotion_no_consumer_migration_no_canon_or_portfolio_mutation_no_customer_or_execution_authority",
		AuthorityFlags:    copyFalseFlags(),
		Summary: Summary{
			DatabaseSurfaces:   len(dbs),
			CanonicalNotes:     len(notes),
			Errors:             errs,
			SourceOfTruthToday: "canonical_markdown_owner_notes",
			SQLToday:           "derived_proof_query_staging_and_bounded_metadata_mirror_only",
			NextSafePhase:      "phase2_markdown_to_sql_parity_mirror",
		},
		DatabaseSurfaces:    dbs,
		CanonicalOwnerNotes: notes,
		FieldFamilyPlan:     fieldFamilyPlan(),
		PromotionPhases:     promotionPhases(),
		StopLines: []string{
			"Do not promote SQL to source of truth from row counts or green proof packets alone.",
			"Do not add tickers, expand SQL-canon/cache, or change production answer paths from this manifest.",
			"Do not migrate consumers to SQL-first until field-family parity, drift, fallback, and A/B proofs are green.",
			"Do not treat SQL route/proof/index artifacts as owner approval, canon mutation authority, or trade/account authority.",
		},
	}
}

func inspectDB(root, driver, sqlitePath string, spec DBSurfaceSpec) DBSurface {
	relPath := filepath.ToSlash(spec.Path)
	dbPath := filepath.Join(root, filepath.FromSlash(spec.Path))
	state := DBSurface{
		Path: relPath, AuthorityClass: spec.AuthorityClass, CurrentOwner: spec.CurrentOwner,
		MayRoute: spec.MayRoute, MaySourceOpen: spec.MaySourceOpen, MayApply: spec.MayApply,
		Description: spec.Description, Status: "ok",
	}
	info, err := os.Stat(dbPath)
	if err != nil {
		state.Exists = false
		state.Status = "missing"
		return state
	}
	state.Exists = true
	size := info.Size()
	state.Bytes = &size
	if hash, err := fileSHA256(dbPath); err == nil {
		state.SHA256 = hash
	}
	integrity, err := sqlutil.ScalarWithDriver(driver, sqlitePath, dbPath, "PRAGMA integrity_check")
	if err != nil {
		state.Status = "error"
		state.Error = err.Error()
		return state
	}
	state.IntegrityCheck = integrity
	fkRows, err := sqlutil.TextRowCountWithDriver(driver, sqlitePath, dbPath, "PRAGMA foreign_key_check")
	if err == nil {
		state.ForeignKeyCheckRows = fkRows
	}
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name")
	if err != nil {
		state.Status = "error"
		state.Error = err.Error()
		return state
	}
	state.TableCounts = map[string]*int64{}
	for _, row := range rows {
		name, _ := row["name"].(string)
		typ, _ := row["type"].(string)
		if name == "" || typ == "" {
			continue
		}
		state.Objects = append(state.Objects, SQLiteObject{Name: name, Type: typ})
		if typ == "table" {
			count, err := sqlutil.TableRowCountWithDriver(driver, sqlitePath, dbPath, name)
			if err != nil {
				state.TableCounts[name] = nil
			} else {
				value := count
				state.TableCounts[name] = &value
			}
		}
	}
	if state.IntegrityCheck != "ok" {
		state.Status = "integrity_warning"
	}
	return state
}

func noteState(root, relPath string) NoteState {
	path := filepath.Join(root, filepath.FromSlash(relPath))
	state := NoteState{
		Path: relPath, AuthorityClass: "canonical_markdown_owner_surface", SourceOfTruthToday: true,
	}
	info, err := os.Stat(path)
	if err != nil {
		return state
	}
	state.Exists = true
	size := info.Size()
	state.Bytes = &size
	if hash, err := fileSHA256(path); err == nil {
		state.SHA256 = hash
	}
	return state
}

func fileSHA256(path string) (string, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(bytes)
	return hex.EncodeToString(sum[:]), nil
}

func copyFalseFlags() map[string]bool {
	out := map[string]bool{}
	keys := make([]string, 0, len(falseFlags))
	for key := range falseFlags {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		out[key] = falseFlags[key]
	}
	return out
}

func FalseFlagKeys() []string {
	keys := make([]string, 0, len(falseFlags))
	for key := range falseFlags {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func Validate(report Report) error {
	for _, key := range FalseFlagKeys() {
		if report.AuthorityFlags[key] {
			return errors.New("authority false flag widened: " + key)
		}
	}
	if report.Summary.DatabaseSurfaces != len(dbSurfaces) {
		return errors.New("database surface count mismatch")
	}
	if report.Summary.CanonicalNotes != len(canonicalOwnerNotes) {
		return errors.New("canonical note count mismatch")
	}
	return nil
}

func fieldFamilyPlan() []map[string]any {
	return []map[string]any{
		{"family": "proof_freshness_lifecycle_metadata", "current_status": "bounded_sql_cache_allowed_with_fallback", "promotion_candidate": "low_risk_after_parity_and_source_open_gate", "blocked_authority": []string{"recommendation", "deployment", "execution", "customer delivery"}},
		{"family": "entry_stop_reference_metadata", "current_status": "bounded_sql_cache_allowed_as_display_reference_only", "promotion_candidate": "first_phase_parity_mirror_candidate", "blocked_authority": []string{"action state", "sizing", "sleeve", "cash", "order terms", "execution"}},
		{"family": "artifact_routing_and_lineage", "current_status": "derived_index_route_allowed", "promotion_candidate": "routing_truth_candidate_after index_rebuild_and_source_open_proof", "blocked_authority": []string{"content claims without source-open", "canon mutation"}},
		{"family": "ticker_action_state", "current_status": "markdown_owner_only", "promotion_candidate": "blocked_until_bidirectional_drift_and_owner_decision_gate", "blocked_authority": []string{"deployable-now promotion", "recommendation", "paper/live order authority"}},
		{"family": "sizing_sleeve_cash_risk_rules", "current_status": "markdown_owner_only", "promotion_candidate": "blocked_higher_consequence", "blocked_authority": []string{"portfolio mutation", "cash/risk-rule change", "execution entitlement"}},
		{"family": "retail_customer_output", "current_status": "fixture_validation_only", "promotion_candidate": "blocked_until_privacy_source_legal_export_gates", "blocked_authority": []string{"real customer data", "external delivery", "regulated personalized advice"}},
		{"family": "paper_live_account_execution", "current_status": "not_sql_truth_candidate", "promotion_candidate": "blocked", "blocked_authority": []string{"paper submit/cancel/sell without exact approval", "live account action", "money movement"}},
	}
}

func promotionPhases() []map[string]any {
	return []map[string]any{
		{"phase": 0, "name": "freeze_current_truth_boundary", "status": "active", "acceptance": "SQL remains proof/query/staging; Markdown owner notes remain canonical."},
		{"phase": 1, "name": "authority_manifest", "status": "implemented_by_this_script", "acceptance": "All SQL surfaces have authority class, false flags, owners, and stop lines."},
		{"phase": 2, "name": "markdown_to_sql_parity_mirror", "status": "next_active_phase", "acceptance": "Exact owner-note extraction compares cleanly to SQL mirror for one approved field family."},
		{"phase": 3, "name": "bidirectional_drift_validator", "status": "pending", "acceptance": "Markdown->SQL and SQL->Markdown drift are both fail-closed and source-hashed."},
		{"phase": 4, "name": "consumer_ab_sql_first_read_with_markdown_fallback", "status": "pending", "acceptance": "A/B outputs are identical for production 42 and fail back to Markdown on any SQL gap."},
		{"phase": 5, "name": "field_family_promotion_decision_packet", "status": "pending_owner_decision", "acceptance": "Randall approves exact field family, scope, rollback, validator, and consumer behavior."},
		{"phase": 6, "name": "source_of_truth_promotion_readiness", "status": "blocked_until_prior_phases_green", "acceptance": "Promotion packet proves no drift, no authority widening, rollback, and downstream validators."},
	}
}
