package warningresidue

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_json_proof_warning_residue_lint.v1"

type Options struct {
	Root        string
	ReportPaths []string
	MaxExamples int
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

type ClassifiedResidue struct {
	Validator string `json:"validator"`
	Report    string `json:"report"`
	Path      string `json:"path"`
	Check     string `json:"check"`
	Class     string `json:"class"`
	Detail    any    `json:"detail,omitempty"`
}

type Summary struct {
	Checks                 int            `json:"checks"`
	Critical               int            `json:"critical"`
	Warnings               int            `json:"warnings"`
	ReportCount            int            `json:"report_count"`
	WarningFindingCount    int            `json:"warning_finding_count"`
	ClassifiedWarningCount int            `json:"classified_warning_count"`
	UnclassifiedCount      int            `json:"unclassified_count"`
	CriticalFindingCount   int            `json:"critical_finding_count"`
	ClassCounts            map[string]int `json:"class_counts"`
}

type Report struct {
	SchemaVersion      string              `json:"schema_version"`
	GeneratedAtUTC     string              `json:"generated_at_utc"`
	Status             string              `json:"status"`
	Root               string              `json:"root"`
	AuthorityBoundary  map[string]bool     `json:"authority_boundary"`
	ReportPaths        []string            `json:"report_paths"`
	ClassifiedResidues []ClassifiedResidue `json:"classified_residues"`
	Findings           []Finding           `json:"findings"`
	Summary            Summary             `json:"summary"`
	NextSafeAction     string              `json:"next_safe_action"`
}

var defaultReports = []string{
	"tmp/go-json-proof-contract-lint.json",
	"tmp/go-sql-canon-proof-bundle-lint.json",
	"tmp/go-validator-route-budget-lint.json",
	"tmp/go-cron-contract-json-proof-lint.json",
	"tmp/go-finance-canon-authority-event-lint.json",
	"tmp/go-sql-source-artifact-freshness-lint.json",
	"tmp/go-sql-source-lineage-producer-contract-lint.json",
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	reportPaths := append([]string{}, opts.ReportPaths...)
	if len(reportPaths) == 0 {
		reportPaths = append(reportPaths, defaultReports...)
	}
	maxExamples := opts.MaxExamples
	if maxExamples <= 0 {
		maxExamples = 50
	}

	findings := []Finding{}
	classified := []ClassifiedResidue{}
	classCounts := map[string]int{}
	add := func(path, check, severity string, ok bool, detail any) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	warningFindingCount := 0
	classifiedCount := 0
	unclassifiedCount := 0
	criticalFindingCount := 0
	reportCount := 0

	for _, reportPath := range reportPaths {
		payload, ok := readJSON(root, reportPath, add)
		if !ok {
			unclassifiedCount++
			continue
		}
		reportCount++
		validator := validatorName(reportPath, payload)
		rawFindings, _ := payload["findings"].([]any)
		for _, raw := range rawFindings {
			finding, ok := raw.(map[string]any)
			if !ok || boolValue(finding["ok"]) {
				continue
			}
			severity := strings.ToLower(strings.TrimSpace(text(finding["severity"])))
			path := text(finding["path"])
			check := text(finding["check"])
			detail := finding["detail"]
			if severity == "critical" {
				criticalFindingCount++
				add(path, "critical_finding_visible:"+validator+":"+check, "critical", false, detail)
				continue
			}
			if severity != "warning" {
				continue
			}
			warningFindingCount++
			className, known := classify(validator, path, check, detail)
			if !known {
				unclassifiedCount++
				add(path, "warning_residue_classified:"+validator+":"+check, "warning", false, detail)
				continue
			}
			classifiedCount++
			classCounts[className]++
			if len(classified) < maxExamples {
				classified = append(classified, ClassifiedResidue{
					Validator: validator,
					Report:    filepath.ToSlash(reportPath),
					Path:      filepath.ToSlash(path),
					Check:     check,
					Class:     className,
					Detail:    detail,
				})
			}
			add(path, "warning_residue_classified:"+className, "info", true, map[string]any{"validator": validator, "check": check})
		}
	}

	sort.Slice(classified, func(i, j int) bool {
		if classified[i].Class != classified[j].Class {
			return classified[i].Class < classified[j].Class
		}
		return classified[i].Check < classified[j].Check
	})

	base := reporting.SummarizeFindings(findings)
	status := reporting.StatusFromCounts(base.Critical, base.Warnings)
	return Report{
		SchemaVersion:      SchemaVersion,
		GeneratedAtUTC:     reporting.UTCNow(),
		Status:             status,
		Root:               filepath.ToSlash(root),
		AuthorityBoundary:  reporting.ReadOnlyAuthorityBoundary(),
		ReportPaths:        slashAll(reportPaths),
		ClassifiedResidues: classified,
		Findings:           findings,
		Summary: Summary{
			Checks:                 base.Checks,
			Critical:               base.Critical,
			Warnings:               base.Warnings,
			ReportCount:            reportCount,
			WarningFindingCount:    warningFindingCount,
			ClassifiedWarningCount: classifiedCount,
			UnclassifiedCount:      unclassifiedCount,
			CriticalFindingCount:   criticalFindingCount,
			ClassCounts:            sortedCounts(classCounts),
		},
		NextSafeAction: "Treat status=ok as known residue classified, not residue resolved. Repair classified residue through the owning Python/cron/SQL producers before promoting to blocking gates.",
	}
}

func classify(validator, path, check string, detail any) (string, bool) {
	joined := strings.ToLower(strings.Join([]string{validator, path, check, fmt.Sprint(detail)}, " "))
	switch {
	case strings.Contains(joined, "validation_warnings_empty") && strings.Contains(joined, "sql-canon"):
		return "proof_packet_validation_residue", true
	case strings.Contains(joined, "json_proof_contract_warnings_zero") || strings.Contains(joined, "embedded proof warnings"):
		return "proof_packet_validation_residue", true
	case strings.Contains(joined, "measured_validator_failures_classified") ||
		strings.Contains(joined, "cron_control_packet") ||
		strings.Contains(joined, "fast_path_qa_no_probes"):
		return "timing_ledger_residue", true
	case strings.Contains(joined, "cron-control-packet") ||
		strings.Contains(joined, "freshness_validation_errors_empty") ||
		strings.Contains(joined, "blocked_signals_zero") ||
		strings.Contains(joined, "escalation_signals_zero"):
		return "cron_control_residue", true
	case strings.Contains(joined, "payload_message_present_for_bloat_check") ||
		strings.Contains(joined, "payload_message_within_prompt_char_budget") ||
		strings.Contains(joined, "payload_message_within_line_budget") ||
		strings.Contains(joined, "delivery_none_has_no_channel") ||
		strings.Contains(joined, "delivery_mode_present_for_agent_payload"):
		return "cron_payload_shape_residue", true
	case strings.Contains(joined, "validator_artifact_exists_or_is_legacy") &&
		(strings.Contains(joined, "ticker_card_100_validate_only") || strings.Contains(joined, "ticker-card-wf78-100")):
		return "legacy_validator_artifact_residue", true
	case strings.Contains(joined, "source_artifact_hash_matches_lineage"):
		return "source_artifact_hash_drift", true
	case strings.Contains(joined, "source_artifacts_registry_row_present"):
		return "source_artifact_registry_gap", true
	case strings.Contains(joined, "source_generated_at_present"):
		return "source_artifact_generated_at_gap", true
	case strings.Contains(joined, "source_generated_at_fresh"):
		return "source_artifact_freshness_residue", true
	case strings.Contains(joined, "source-lineage-producer-contract-lint") &&
		(strings.Contains(joined, "producer_contract_present") ||
			strings.Contains(joined, "sql_lineage_repair_route_present") ||
			strings.Contains(joined, "source_artifacts_owner_present")):
		return "source_lineage_producer_contract_gap", true
	case strings.Contains(joined, "entry-stop-band-freshness-validator") &&
		(strings.Contains(joined, "source_hash_matches_disk") ||
			strings.Contains(joined, "generated_at_present") ||
			strings.Contains(joined, "source_fresh_within_max_age")):
		return "entry_stop_source_lineage_residue", true
	case strings.Contains(joined, "json-proof-structural-validator") &&
		(strings.Contains(joined, "status_present") ||
			strings.Contains(joined, "freshness_within_max_age") ||
			strings.Contains(joined, "schema_or_generated_at_present") ||
			strings.Contains(joined, "generated_at_parse")):
		return "bulk_json_shape_residue", true
	case strings.Contains(joined, "workflow-artifact-freshness-gate") &&
		strings.Contains(joined, "file_mtime_within_default_max_age"):
		return "workflow_artifact_freshness_residue", true
	case (strings.Contains(joined, "json-proof-structural-validator") ||
		strings.Contains(joined, "workflow-artifact-freshness-gate")) &&
		strings.Contains(joined, "artifact_sha256_matches_index"):
		return "artifact_index_hash_drift", true
	case strings.Contains(joined, "cross-db-referential-integrity-probe") &&
		strings.Contains(joined, "ticker_set_matches_base"):
		return "optional_cross_db_mirror_drift", true
	case strings.Contains(joined, "pm-queue-authority-lint") &&
		(strings.Contains(joined, "stale_lanes_zero") ||
			strings.Contains(joined, "blocked_lanes_visible") ||
			strings.Contains(joined, "needs_validation_lanes_zero")):
		return "pm_queue_state_residue", true
	case strings.Contains(joined, "paper-trading-guard-preflight") &&
		strings.Contains(joined, "kill_switch_expires_at_present"):
		return "paper_guard_readiness_residue", true
	default:
		return "", false
	}
}

func readJSON(root, relPath string, add func(string, string, string, bool, any)) (map[string]any, bool) {
	bytes, err := os.ReadFile(resolve(root, relPath))
	if err != nil {
		add(relPath, "report_exists", "warning", false, err.Error())
		return nil, false
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "report_parse", "warning", false, err.Error())
		return nil, false
	}
	add(relPath, "report_parse", "info", true, "")
	return payload, true
}

func validatorName(reportPath string, payload map[string]any) string {
	if name := text(payload["validator"]); name != "" {
		return name
	}
	base := strings.TrimSuffix(filepath.Base(reportPath), filepath.Ext(reportPath))
	return strings.TrimPrefix(base, "go-")
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

func boolValue(value any) bool {
	typed, ok := value.(bool)
	return ok && typed
}

func slashAll(values []string) []string {
	out := make([]string, 0, len(values))
	for _, value := range values {
		out = append(out, filepath.ToSlash(value))
	}
	return out
}

func sortedCounts(counts map[string]int) map[string]int {
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := map[string]int{}
	for _, key := range keys {
		out[key] = counts[key]
	}
	return out
}
