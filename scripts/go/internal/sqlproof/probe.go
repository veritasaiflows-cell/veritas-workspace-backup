package sqlproof

import (
	"path/filepath"
	"sort"
	"time"

	"veritas.local/wf74/internal/schemalint"
)

type DBProof struct {
	Path     string `json:"path"`
	Status   string `json:"status"`
	Checks   int    `json:"checks"`
	Critical int    `json:"critical"`
	Warnings int    `json:"warnings"`
	Boundary string `json:"boundary"`
}

type Summary struct {
	Checks     int `json:"checks"`
	Critical   int `json:"critical"`
	Warnings   int `json:"warnings"`
	DBs        int `json:"dbs"`
	BlockedDBs int `json:"blocked_dbs"`
	WarningDBs int `json:"warning_dbs"`
}

type Report struct {
	SchemaVersion    string            `json:"schema_version"`
	GeneratedAtUTC   string            `json:"generated_at_utc"`
	Status           string            `json:"status"`
	SQLiteDriver     string            `json:"sqlite_driver"`
	Root             string            `json:"root"`
	SourceValidator  string            `json:"source_validator"`
	DBs              []DBProof         `json:"dbs"`
	SchemaDriftProof schemalint.Report `json:"schema_drift_proof"`
	Summary          Summary           `json:"summary"`
	Boundary         string            `json:"boundary"`
	MigrationPosture string            `json:"migration_posture"`
}

type Options struct {
	Root       string
	DBFiles    []string
	SQLitePath string
	Driver     string
}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	schemaReport := schemalint.Run(schemalint.Options{
		Root:       root,
		DBFiles:    opts.DBFiles,
		SQLitePath: opts.SQLitePath,
		Driver:     opts.Driver,
	})
	dbs := summarizeDBs(schemaReport)
	blocked, warning := 0, 0
	for _, db := range dbs {
		switch db.Status {
		case "blocked":
			blocked++
		case "warning":
			warning++
		}
	}
	status := "ok"
	if warning > 0 {
		status = "warning"
	}
	if blocked > 0 || schemaReport.Status == "blocked" {
		status = "blocked"
	}
	return Report{
		SchemaVersion:    "sql_proof_probe.v1",
		GeneratedAtUTC:   time.Now().UTC().Format(time.RFC3339),
		Status:           status,
		SQLiteDriver:     schemaReport.SQLiteDriver,
		Root:             filepath.ToSlash(root),
		SourceValidator:  "sql-schema-drift-lint",
		DBs:              dbs,
		SchemaDriftProof: schemaReport,
		Summary: Summary{
			Checks:     schemaReport.Summary.Checks,
			Critical:   schemaReport.Summary.Critical,
			Warnings:   schemaReport.Summary.Warnings,
			DBs:        len(dbs),
			BlockedDBs: blocked,
			WarningDBs: warning,
		},
		Boundary:         "Read-only Go SQL proof probe. No SQL writes, SQL import, canon/portfolio mutation, customer/external delivery, paper/live/account action, config/runtime mutation, or owner approval inference.",
		MigrationPosture: "Go may own read-only SQLite proof aggregation; Python remains owner of generation, orchestration, canon maintenance, and gated apply paths.",
	}
}

func summarizeDBs(report schemalint.Report) []DBProof {
	byPath := map[string]*DBProof{}
	for _, path := range report.CheckedDBs {
		byPath[path] = &DBProof{Path: path, Status: "ok", Boundary: "read_only_sql_proof"}
	}
	for _, finding := range report.Findings {
		path := finding.Path
		if path == "" {
			path = "unknown"
		}
		row := byPath[path]
		if row == nil {
			row = &DBProof{Path: path, Status: "ok", Boundary: "read_only_sql_proof"}
			byPath[path] = row
		}
		row.Checks++
		if finding.OK {
			continue
		}
		if finding.Severity == "critical" {
			row.Critical++
			row.Status = "blocked"
		} else {
			row.Warnings++
			if row.Status != "blocked" {
				row.Status = "warning"
			}
		}
	}
	out := make([]DBProof, 0, len(byPath))
	for _, row := range byPath {
		out = append(out, *row)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	return out
}
