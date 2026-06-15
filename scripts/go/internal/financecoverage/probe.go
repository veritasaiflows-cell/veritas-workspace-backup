package financecoverage

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"

	"veritas.local/wf74/internal/reporting"
)

const schemaVersion = "finance_data_coverage_probe_go.v1"

type AuthorityBoundary struct {
	ReportOnly                  bool `json:"report_only"`
	ReadOnly                    bool `json:"read_only"`
	CanonicalMutationAllowed    bool `json:"canonical_mutation_allowed"`
	PortfolioMutationAllowed    bool `json:"portfolio_mutation_allowed"`
	OwnerApprovalInferred       bool `json:"owner_approval_inferred"`
	TradeExecutionAllowed       bool `json:"trade_execution_allowed"`
	TradeOrAccountActionAllowed bool `json:"trade_or_account_action_allowed"`
	PaperOrderExecutionAllowed  bool `json:"paper_order_execution_allowed"`
	CustomerOrExternalDelivery  bool `json:"customer_or_external_delivery_allowed"`
	ConfigAuthRuntimeMutation   bool `json:"config_auth_runtime_mutation"`
}

type SourceArtifact struct {
	Exists bool   `json:"exists"`
	Status string `json:"status,omitempty"`
	Path   string `json:"path,omitempty"`
	Stale  bool   `json:"stale"`
	Usable bool   `json:"usable_for_values"`
}

type Summary struct {
	SourceArtifactCount                int `json:"source_artifact_count"`
	SourceArtifactsPresent             int `json:"source_artifacts_present"`
	SourceArtifactsMissing             int `json:"source_artifacts_missing"`
	SourceArtifactsStale               int `json:"source_artifacts_stale"`
	SourceArtifactsUnusablePlaceholder int `json:"source_artifacts_unusable_placeholder"`
	TickerCountIndexed                 int `json:"ticker_count_indexed"`
	DataFamilyCount                    int `json:"data_family_count"`
	UniverseTickerCount                int `json:"universe_ticker_count"`
}

type Report struct {
	SchemaVersion     string                    `json:"schema_version"`
	GeneratedAtUTC    string                    `json:"generated_at_utc"`
	Status            string                    `json:"status"`
	SourceReport      string                    `json:"source_report"`
	SourceStatus      string                    `json:"source_status,omitempty"`
	Summary           Summary                   `json:"summary"`
	SourceArtifacts   map[string]SourceArtifact `json:"source_artifacts"`
	AuthorityBoundary AuthorityBoundary         `json:"authority_boundary"`
	Validation        Validation                `json:"validation"`
	NextSafeAction    string                    `json:"next_safe_action"`
}

type Validation struct {
	Status string  `json:"status"`
	Checks []Check `json:"checks"`
	Failed int     `json:"failed"`
}

type Check struct {
	Name   string `json:"name"`
	OK     bool   `json:"ok"`
	Detail any    `json:"detail"`
}

type Options struct {
	Root   string
	Source string
}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	source := opts.Source
	if source == "" {
		source = filepath.Join(root, "tmp", "finance-data-coverage-current.json")
	} else if !filepath.IsAbs(source) {
		source = filepath.Join(root, source)
	}
	report := loadReport(root, source)
	report.Validation = validate(report)
	if report.Validation.Failed > 0 {
		report.Status = "blocked"
	} else if report.SourceStatus == "ok" {
		report.Status = "ok"
	} else {
		report.Status = "warning"
	}
	return report
}

func loadReport(root, source string) Report {
	report := Report{
		SchemaVersion:  schemaVersion,
		GeneratedAtUTC: reporting.UTCNow(),
		SourceReport:   rel(root, source),
		AuthorityBoundary: AuthorityBoundary{
			ReportOnly: true,
			ReadOnly:   true,
		},
		SourceArtifacts: map[string]SourceArtifact{},
		NextSafeAction:  "Use this as a Go fixture validator over finance-data-coverage output; keep registry generation and finance routing semantics in Python.",
	}
	raw, err := os.ReadFile(source)
	if err != nil {
		report.Status = "blocked"
		report.Validation = Validation{Status: "error", Checks: []Check{{Name: "source_report_readable", OK: false, Detail: err.Error()}}, Failed: 1}
		return report
	}
	var payload map[string]any
	if err := json.Unmarshal(raw, &payload); err != nil {
		report.Status = "blocked"
		report.Validation = Validation{Status: "error", Checks: []Check{{Name: "source_report_json", OK: false, Detail: err.Error()}}, Failed: 1}
		return report
	}
	report.SourceStatus, _ = payload["status"].(string)
	report.Summary = parseSummary(asMap(payload["summary"]))
	for key, value := range asMap(payload["source_artifacts"]) {
		item := asMap(value)
		report.SourceArtifacts[key] = SourceArtifact{
			Exists: boolValue(item["exists"]),
			Status: stringValue(item["status"]),
			Path:   stringValue(item["path"]),
			Stale:  stringValue(item["status"]) == "stale",
			Usable: boolDefault(item["usable_for_values"], true),
		}
	}
	return report
}

func validate(report Report) Validation {
	checks := []Check{
		{Name: "source_report_present", OK: report.SourceReport != "", Detail: report.SourceReport},
		{Name: "data_family_count_present", OK: report.Summary.DataFamilyCount > 0, Detail: report.Summary.DataFamilyCount},
		{Name: "ticker_count_indexed_present", OK: report.Summary.TickerCountIndexed > 0, Detail: report.Summary.TickerCountIndexed},
		{Name: "source_artifact_count_matches", OK: report.Summary.SourceArtifactCount == len(report.SourceArtifacts), Detail: map[string]int{"summary": report.Summary.SourceArtifactCount, "go": len(report.SourceArtifacts)}},
		{Name: "authority_boundary_read_only", OK: report.AuthorityBoundary.ReportOnly && report.AuthorityBoundary.ReadOnly, Detail: report.AuthorityBoundary},
		{Name: "owner_approval_not_inferred", OK: !report.AuthorityBoundary.OwnerApprovalInferred, Detail: report.AuthorityBoundary.OwnerApprovalInferred},
		{Name: "trade_execution_not_allowed", OK: !report.AuthorityBoundary.TradeExecutionAllowed && !report.AuthorityBoundary.TradeOrAccountActionAllowed && !report.AuthorityBoundary.PaperOrderExecutionAllowed, Detail: report.AuthorityBoundary},
	}
	failed := 0
	for _, check := range checks {
		if !check.OK {
			failed++
		}
	}
	status := "ok"
	if failed > 0 {
		status = "blocked"
	}
	return Validation{Status: status, Checks: checks, Failed: failed}
}

func parseSummary(summary map[string]any) Summary {
	return Summary{
		SourceArtifactCount:                intValue(summary["source_artifact_count"]),
		SourceArtifactsPresent:             intValue(summary["source_artifacts_present"]),
		SourceArtifactsMissing:             intValue(summary["source_artifacts_missing"]),
		SourceArtifactsStale:               intValue(summary["source_artifacts_stale"]),
		SourceArtifactsUnusablePlaceholder: intValue(summary["source_artifacts_unusable_placeholder"]),
		TickerCountIndexed:                 intValue(summary["ticker_count_indexed"]),
		DataFamilyCount:                    intValue(summary["data_family_count"]),
		UniverseTickerCount:                intValue(summary["universe_ticker_count"]),
	}
}

func asMap(value any) map[string]any {
	if out, ok := value.(map[string]any); ok {
		return out
	}
	return map[string]any{}
}

func stringValue(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	return ""
}

func boolValue(value any) bool {
	if b, ok := value.(bool); ok {
		return b
	}
	return false
}

func boolDefault(value any, fallback bool) bool {
	if b, ok := value.(bool); ok {
		return b
	}
	return fallback
}

func intValue(value any) int {
	switch typed := value.(type) {
	case float64:
		return int(typed)
	case int:
		return typed
	default:
		return 0
	}
}

func rel(root, path string) string {
	if relative, err := filepath.Rel(root, path); err == nil {
		return filepath.ToSlash(relative)
	}
	return filepath.ToSlash(path)
}

func Validate(report Report) error {
	boundary := report.AuthorityBoundary
	if !boundary.ReportOnly ||
		!boundary.ReadOnly ||
		boundary.CanonicalMutationAllowed ||
		boundary.PortfolioMutationAllowed ||
		boundary.OwnerApprovalInferred ||
		boundary.TradeExecutionAllowed ||
		boundary.TradeOrAccountActionAllowed ||
		boundary.PaperOrderExecutionAllowed ||
		boundary.CustomerOrExternalDelivery ||
		boundary.ConfigAuthRuntimeMutation {
		return errors.New("authority boundary widened")
	}
	if report.Validation.Status != "ok" {
		return errors.New("validation not ok")
	}
	return nil
}
