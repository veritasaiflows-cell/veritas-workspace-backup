package sourceproducer

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_sql_source_lineage_producer_contract_lint.v1"

type Options struct {
	Root            string
	FreshnessReport string
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

type ProducerContract struct {
	ArtifactPath             string `json:"artifact_path"`
	ProducerID               string `json:"producer_id"`
	ProducerCommand          string `json:"producer_command"`
	ValidationCommand        string `json:"validation_command"`
	SQLLineageRepairRoute    string `json:"sql_lineage_repair_route"`
	SourceArtifactsOwner     string `json:"source_artifacts_owner"`
	RefreshesSourceArtifacts bool   `json:"refreshes_source_artifacts"`
	RefreshesGeneratedAt     bool   `json:"refreshes_generated_at"`
	RefreshesHash            bool   `json:"refreshes_hash"`
	RepairPosture            string `json:"repair_posture"`
	Notes                    string `json:"notes,omitempty"`
}

type ArtifactProducerStatus struct {
	Path                 string           `json:"path"`
	ProducerID           string           `json:"producer_id,omitempty"`
	KnownProducer        bool             `json:"known_producer"`
	ProducerScriptsExist bool             `json:"producer_scripts_exist"`
	UnsafeCommandTokens  []string         `json:"unsafe_command_tokens,omitempty"`
	OpenRepairTypes      []string         `json:"open_repair_types,omitempty"`
	SourceStatus         string           `json:"source_status,omitempty"`
	ValidatorStatus      string           `json:"validator_status,omitempty"`
	LineageRows          int              `json:"lineage_rows"`
	Contract             ProducerContract `json:"contract,omitempty"`
}

type Summary struct {
	Checks                       int                      `json:"checks"`
	Critical                     int                      `json:"critical"`
	Warnings                     int                      `json:"warnings"`
	ArtifactCount                int                      `json:"artifact_count"`
	ProducerContractCount        int                      `json:"producer_contract_count"`
	MappedArtifactCount          int                      `json:"mapped_artifact_count"`
	UnmappedArtifactCount        int                      `json:"unmapped_artifact_count"`
	ProducerScriptMissingCount   int                      `json:"producer_script_missing_count"`
	UnsafeCommandTokenCount      int                      `json:"unsafe_command_token_count"`
	OpenRepairArtifactCount      int                      `json:"open_repair_artifact_count"`
	SourceArtifactDriftCount     int                      `json:"source_artifact_drift_count"`
	RegistryGapCount             int                      `json:"registry_gap_count"`
	MissingGeneratedAtCount      int                      `json:"missing_generated_at_count"`
	FreshnessReportWarningCount  int                      `json:"freshness_report_warning_count"`
	FreshnessReportCriticalCount int                      `json:"freshness_report_critical_count"`
	ArtifactProducerStatuses     []ArtifactProducerStatus `json:"artifact_producer_statuses"`
}

type Report struct {
	SchemaVersion     string             `json:"schema_version"`
	GeneratedAtUTC    string             `json:"generated_at_utc"`
	Validator         string             `json:"validator"`
	Status            string             `json:"status"`
	Root              string             `json:"root"`
	FreshnessReport   string             `json:"freshness_report"`
	AuthorityBoundary map[string]bool    `json:"authority_boundary"`
	ProducerContracts []ProducerContract `json:"producer_contracts"`
	Findings          []Finding          `json:"findings"`
	Summary           Summary            `json:"summary"`
	NextSafeAction    string             `json:"next_safe_action"`
}

type freshnessPayload struct {
	Status  string `json:"status"`
	Summary struct {
		Warnings                      int `json:"warnings"`
		Critical                      int `json:"critical"`
		HashMismatchCount             int `json:"hash_mismatch_count"`
		MissingSourceArtifactRowCount int `json:"missing_source_artifact_row_count"`
		ArtifactSummaries             []struct {
			Path                string `json:"path"`
			LineageRows         int    `json:"lineage_rows"`
			GeneratedAtUTC      string `json:"generated_at_utc"`
			SourceStatus        string `json:"source_status"`
			ValidatorStatus     string `json:"validator_status"`
			SourceArtifactKnown bool   `json:"source_artifact_known"`
			HashMatchesDisk     bool   `json:"hash_matches_disk"`
		} `json:"artifact_summaries"`
	} `json:"summary"`
	Findings []Finding `json:"findings"`
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	freshnessReport := defaulted(opts.FreshnessReport, "tmp/go-sql-source-artifact-freshness-lint.json")
	catalog := defaultCatalog()

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

	payload, loaded := readFreshnessReport(root, freshnessReport, add)
	statuses := []ArtifactProducerStatus{}
	openRepairArtifactCount := 0
	mappedArtifactCount := 0
	unmappedArtifactCount := 0
	producerScriptMissingCount := 0
	unsafeCommandTokenCount := 0

	repairTypesByPath := repairTypes(payload.Findings)
	if loaded {
		for _, artifact := range payload.Summary.ArtifactSummaries {
			path := filepath.ToSlash(artifact.Path)
			contract, known := catalog[path]
			add(path, "producer_contract_present", "warning", known, map[string]any{"path": path})
			status := ArtifactProducerStatus{
				Path:            path,
				KnownProducer:   known,
				SourceStatus:    artifact.SourceStatus,
				ValidatorStatus: artifact.ValidatorStatus,
				LineageRows:     artifact.LineageRows,
				OpenRepairTypes: sortedStrings(repairTypesByPath[path]),
			}
			if len(status.OpenRepairTypes) > 0 {
				openRepairArtifactCount++
				add(path, "open_source_lineage_repair_visible", "info", true, status.OpenRepairTypes)
			}
			if !known {
				unmappedArtifactCount++
				statuses = append(statuses, status)
				continue
			}
			mappedArtifactCount++
			status.ProducerID = contract.ProducerID
			status.Contract = contract

			allScriptsExist := true
			for _, script := range referencedScripts(contract) {
				exists := fileExists(root, script)
				add(path, "producer_script_exists:"+filepath.ToSlash(script), "critical", exists, "")
				if !exists {
					allScriptsExist = false
					producerScriptMissingCount++
				}
			}
			status.ProducerScriptsExist = allScriptsExist

			unsafe := unsafeTokens(contract)
			status.UnsafeCommandTokens = unsafe
			if len(unsafe) > 0 {
				unsafeCommandTokenCount += len(unsafe)
			}
			add(path, "producer_commands_review_only", "critical", len(unsafe) == 0, unsafe)
			add(path, "sql_lineage_repair_route_present", "warning", strings.TrimSpace(contract.SQLLineageRepairRoute) != "", "")
			add(path, "source_artifacts_owner_present", "warning", strings.TrimSpace(contract.SourceArtifactsOwner) != "", "")
			statuses = append(statuses, status)
		}
	}

	sort.Slice(statuses, func(i, j int) bool { return statuses[i].Path < statuses[j].Path })
	contracts := contractsSlice(catalog)
	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Validator:         "go-sql-source-lineage-producer-contract-lint",
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		FreshnessReport:   filepath.ToSlash(freshnessReport),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		ProducerContracts: contracts,
		Findings:          findings,
		Summary: Summary{
			Checks:                       base.Checks,
			Critical:                     base.Critical,
			Warnings:                     base.Warnings,
			ArtifactCount:                len(statuses),
			ProducerContractCount:        len(contracts),
			MappedArtifactCount:          mappedArtifactCount,
			UnmappedArtifactCount:        unmappedArtifactCount,
			ProducerScriptMissingCount:   producerScriptMissingCount,
			UnsafeCommandTokenCount:      unsafeCommandTokenCount,
			OpenRepairArtifactCount:      openRepairArtifactCount,
			SourceArtifactDriftCount:     payload.Summary.HashMismatchCount,
			RegistryGapCount:             payload.Summary.MissingSourceArtifactRowCount,
			MissingGeneratedAtCount:      countRepairType(repairTypesByPath, "missing_generated_at"),
			FreshnessReportWarningCount:  payload.Summary.Warnings,
			FreshnessReportCriticalCount: payload.Summary.Critical,
			ArtifactProducerStatuses:     statuses,
		},
		NextSafeAction: "Use this map to route SQL source-lineage repair to the owning producers. Do not mutate finance canon or source_artifacts directly from this validator.",
	}
}

func defaultCatalog() map[string]ProducerContract {
	return map[string]ProducerContract{
		"03. Portfolio/Execution Board.md": {
			ArtifactPath:             "03. Portfolio/Execution Board.md",
			ProducerID:               "manual_execution_board_owner_source",
			ProducerCommand:          "manual owner-maintained canonical note",
			ValidationCommand:        "python scripts/execution_board_canon_anchor_drift_validator.py --write --validate",
			SQLLineageRepairRoute:    "python scripts/reference_levels_sql_native_source_family_proof.py --write --validate",
			SourceArtifactsOwner:     "execution_board_reference_level_anchor",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     true,
			RefreshesHash:            true,
			RepairPosture:            "manual_or_gated_source_review",
			Notes:                    "Canonical owner note; repair through source review or gated reference-level source proof, not blind SQL mutation.",
		},
		"tmp/band-proposals.json": {
			ArtifactPath:             "tmp/band-proposals.json",
			ProducerID:               "band_refresh",
			ProducerCommand:          "python scripts/band_refresh.py",
			ValidationCommand:        "python scripts/reference_levels_band_proposals_source_migration.py --write --validate",
			SQLLineageRepairRoute:    "python scripts/reference_levels_targeted_repair_packet.py --write --validate",
			SourceArtifactsOwner:     "sql_canon_reference_levels",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     true,
			RefreshesHash:            true,
			RepairPosture:            "producer_refresh_then_gated_sql_lineage_repair",
		},
		"tmp/finance-intelligence-state.sqlite": {
			ArtifactPath:             "tmp/finance-intelligence-state.sqlite",
			ProducerID:               "finance_intelligence_state",
			ProducerCommand:          "python scripts/finance_intelligence_state.py build",
			ValidationCommand:        "python scripts/finance_intelligence_state.py validate --pretty",
			SQLLineageRepairRoute:    "python scripts/finance_sql_canon_access.py --write --validate",
			SourceArtifactsOwner:     "finance_state_compatibility_cache",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     false,
			RefreshesHash:            true,
			RepairPosture:            "derived_cache_rebuild_then_sql_lineage_refresh_required",
			Notes:                    "Derived compatibility cache currently lacks source_generated_at in lineage; keep as visible repair residue.",
		},
		"tmp/sql-canon-consumer-migration-backlog.json": {
			ArtifactPath:             "tmp/sql-canon-consumer-migration-backlog.json",
			ProducerID:               "sql_canon_consumer_inventory",
			ProducerCommand:          "python scripts/sql_canon_consumer_inventory.py --write --validate",
			ValidationCommand:        "python scripts/sql_canon_consumer_registry_guard.py --write --validate",
			SQLLineageRepairRoute:    "python scripts/sql_canon_consumer_registry_sync.py --write --validate",
			SourceArtifactsOwner:     "sql_canon_consumer_registry",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     true,
			RefreshesHash:            true,
			RepairPosture:            "producer_refresh_then_registry_guard",
		},
		"tmp/wf78-auto-tier-routing.json": {
			ArtifactPath:             "tmp/wf78-auto-tier-routing.json",
			ProducerID:               "wf78_auto_tier_router",
			ProducerCommand:          "python scripts/wf78_auto_tier_router.py --write --validate",
			ValidationCommand:        "python scripts/wf78_auto_tier_router.py --write --validate",
			SQLLineageRepairRoute:    "python scripts/sql_canon_tier_routing_refresh.py --write --validate",
			SourceArtifactsOwner:     "sql_canon_tier_routing_state",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     true,
			RefreshesHash:            true,
			RepairPosture:            "validated_wf78_router_then_gated_tier_routing_refresh",
		},
		"tmp/wf78-missing-band-context-repair.json": {
			ArtifactPath:             "tmp/wf78-missing-band-context-repair.json",
			ProducerID:               "wf78_missing_band_context_repair",
			ProducerCommand:          "python scripts/wf78_missing_band_context_repair.py --write --validate",
			ValidationCommand:        "python scripts/reference_levels_wf78_retirement_migration_exception.py --write --validate",
			SQLLineageRepairRoute:    "python scripts/reference_levels_wf78_retirement_migration_exception.py --write --validate",
			SourceArtifactsOwner:     "sql_canon_reference_levels",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     true,
			RefreshesHash:            true,
			RepairPosture:            "migration_exception_review_then_gated_reference_level_repair",
		},
		"tmp/wf78-tier-weighted-freshness-resolution.json": {
			ArtifactPath:             "tmp/wf78-tier-weighted-freshness-resolution.json",
			ProducerID:               "wf78_tier_weighted_freshness_resolver",
			ProducerCommand:          "python scripts/wf78_tier_weighted_freshness_resolver.py --write --validate",
			ValidationCommand:        "python scripts/wf78_tier_weighted_freshness_resolver.py --write --validate",
			SQLLineageRepairRoute:    "python scripts/sql_canon_tier_routing_refresh.py --write --validate",
			SourceArtifactsOwner:     "sql_canon_tier_routing_state",
			RefreshesSourceArtifacts: false,
			RefreshesGeneratedAt:     true,
			RefreshesHash:            true,
			RepairPosture:            "wf78_freshness_resolver_then_gated_tier_routing_refresh",
		},
	}
}

func readFreshnessReport(root, relPath string, add func(string, string, string, bool, any)) (freshnessPayload, bool) {
	var payload freshnessPayload
	bytes, err := os.ReadFile(resolve(root, relPath))
	if err != nil {
		add(relPath, "freshness_report_exists", "warning", false, err.Error())
		return payload, false
	}
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "freshness_report_parse", "warning", false, err.Error())
		return payload, false
	}
	add(relPath, "freshness_report_parse", "info", true, payload.Status)
	return payload, true
}

func repairTypes(findings []Finding) map[string][]string {
	out := map[string][]string{}
	for _, finding := range findings {
		if finding.OK || finding.Severity != "warning" {
			continue
		}
		repairType := ""
		switch finding.Check {
		case "source_artifact_hash_matches_lineage":
			repairType = "source_artifact_hash_drift"
		case "source_artifacts_registry_row_present":
			repairType = "source_artifacts_registry_gap"
		case "source_generated_at_present":
			repairType = "missing_generated_at"
		}
		if repairType == "" {
			continue
		}
		path := filepath.ToSlash(finding.Path)
		if !contains(out[path], repairType) {
			out[path] = append(out[path], repairType)
		}
	}
	return out
}

func referencedScripts(contract ProducerContract) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, command := range []string{contract.ProducerCommand, contract.ValidationCommand, contract.SQLLineageRepairRoute} {
		for _, field := range strings.Fields(command) {
			field = strings.Trim(field, `"'`)
			if !(strings.HasPrefix(field, "scripts/") || strings.HasPrefix(field, "scripts\\")) || !strings.HasSuffix(field, ".py") {
				continue
			}
			field = filepath.ToSlash(field)
			if !seen[field] {
				seen[field] = true
				out = append(out, field)
			}
		}
	}
	sort.Strings(out)
	return out
}

func unsafeTokens(contract ProducerContract) []string {
	commands := strings.Join([]string{contract.ProducerCommand, contract.ValidationCommand, contract.SQLLineageRepairRoute}, " ")
	lower := strings.ToLower(commands)
	tokens := []string{}
	for _, token := range []string{"--apply", "--submit", "--approve", "--delete", "--archive", "--execute", "--live"} {
		if strings.Contains(lower, token) {
			tokens = append(tokens, token)
		}
	}
	return tokens
}

func contractsSlice(catalog map[string]ProducerContract) []ProducerContract {
	keys := make([]string, 0, len(catalog))
	for key := range catalog {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := make([]ProducerContract, 0, len(keys))
	for _, key := range keys {
		out = append(out, catalog[key])
	}
	return out
}

func fileExists(root, relPath string) bool {
	_, err := os.Stat(resolve(root, relPath))
	return err == nil
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

func sortedStrings(values []string) []string {
	out := append([]string{}, values...)
	sort.Strings(out)
	return out
}

func contains(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}

func countRepairType(typesByPath map[string][]string, repairType string) int {
	count := 0
	for _, values := range typesByPath {
		if contains(values, repairType) {
			count++
		}
	}
	return count
}

func errorText(err error) string {
	if err == nil {
		return ""
	}
	return fmt.Sprint(err)
}
