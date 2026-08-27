package closeoutledger

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_implementation_closeout_ledger_lint.v1"
const defaultLocalTimezone = "America/Phoenix"

type Options struct {
	Root                  string
	LaneRegister          string
	ChangedRouter         string
	ValidatorBundle       string
	WrapperProof          string
	WarningResidue        string
	ReleaseContract       string
	MemoryPath            string
	AllowSingleActiveLane bool
	SkipWrapperProof      bool
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

type Summary struct {
	Checks                     int    `json:"checks"`
	Critical                   int    `json:"critical"`
	Warnings                   int    `json:"warnings"`
	ActiveLaneCount            int    `json:"active_lane_count"`
	ChangedRouterStatus        string `json:"changed_router_status"`
	ValidatorBundleStatus      string `json:"validator_bundle_status"`
	ValidatorBundleFailed      int    `json:"validator_bundle_failed"`
	WrapperStatus              string `json:"wrapper_status"`
	WrapperFailed              int    `json:"wrapper_failed"`
	WrapperCritical            int    `json:"wrapper_critical"`
	WarningResidueStatus       string `json:"warning_residue_status"`
	UnclassifiedWarningResidue int    `json:"unclassified_warning_residue"`
	ReleaseContractStatus      string `json:"release_contract_status"`
	ReleaseContractReady       bool   `json:"release_contract_ready"`
	ReleaseContractMissing     int    `json:"release_contract_missing_gates"`
	ReleaseContractUnknown     int    `json:"release_contract_unknown_warnings"`
	ReleaseContractBlocking    int    `json:"release_contract_blocking_warnings"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	laneRegister := defaulted(opts.LaneRegister, "tmp/concurrent-lane-register.json")
	changedRouter := defaulted(opts.ChangedRouter, "tmp/changed-file-validator-router.json")
	validatorBundle := defaulted(opts.ValidatorBundle, "tmp/validator-bundle-router.json")
	wrapperProof := defaulted(opts.WrapperProof, "tmp/go-fast-proof-validators.json")
	warningResidue := defaulted(opts.WarningResidue, "tmp/go-json-proof-warning-residue-lint.json")
	releaseContract := defaulted(opts.ReleaseContract, "tmp/implementation-release-contract.json")
	memoryPath := defaulted(opts.MemoryPath, defaultMemoryPath())
	allowSingleActiveLane := opts.AllowSingleActiveLane

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

	lanePayload := readJSON(root, laneRegister, "critical", add)
	activeLaneCount := activeCount(lanePayload)
	activeOK := activeLaneCount == 0 || (allowSingleActiveLane && activeLaneCount == 1)
	add(laneRegister, "active_lane_count_bounded", "warning", activeOK, activeLaneCount)

	changedPayload := readJSON(root, changedRouter, "critical", add)
	changedStatus := text(changedPayload["status"])
	add(changedRouter, "changed_file_router_status_ok", "critical", changedStatus == "ok", changedStatus)
	add(changedRouter, "changed_file_router_budget_present", "warning", text(pathValue(changedPayload, "summary.recommended_budget")) != "", pathValue(changedPayload, "summary.recommended_budget"))

	bundlePayload := readJSON(root, validatorBundle, "critical", add)
	bundleStatus := text(bundlePayload["status"])
	bundleFailed := intValue(pathValue(bundlePayload, "summary.failed_command_count"))
	add(validatorBundle, "validator_bundle_status_ok", "critical", bundleStatus == "ok", bundleStatus)
	add(validatorBundle, "validator_bundle_failed_zero", "critical", bundleFailed == 0, bundleFailed)

	warningPayload := readJSON(root, warningResidue, "warning", add)
	warningStatus := text(warningPayload["status"])
	unclassified := intValue(pathValue(warningPayload, "summary.unclassified_count"))
	add(warningResidue, "warning_residue_unclassified_zero", "critical", unclassified == 0, unclassified)

	wrapperStatus := "skipped_current_wrapper_run"
	wrapperFailed := 0
	wrapperCritical := 0
	releasePayload := readJSON(root, releaseContract, "critical", add)
	releaseStatus := text(releasePayload["status"])
	releaseReady := boolValue(pathValue(releasePayload, "summary.ready_to_close"))
	releaseMissing := intValue(pathValue(releasePayload, "summary.missing_gate_count"))
	releaseUnknown := intValue(pathValue(releasePayload, "summary.unknown_warning_count"))
	releaseBlocking := intValue(pathValue(releasePayload, "summary.blocking_warning_count"))
	if opts.SkipWrapperProof {
		add(wrapperProof, "wrapper_current_run_checked_after_wrapper_write", "info", true, "skipped inside wrapper to avoid self-reference")
		add(releaseContract, "implementation_release_contract_checked_after_wrapper_write", "info", true, map[string]any{
			"status":            releaseStatus,
			"ready_to_close":    releaseReady,
			"missing_gates":     releaseMissing,
			"unknown_warnings":  releaseUnknown,
			"blocking_warnings": releaseBlocking,
		})
	} else {
		add(releaseContract, "implementation_release_contract_status_ok", "critical", releaseStatus == "ok", releaseStatus)
		add(releaseContract, "implementation_release_contract_ready_to_close", "critical", releaseReady, releaseReady)
		add(releaseContract, "implementation_release_contract_missing_gates_zero", "critical", releaseMissing == 0, releaseMissing)
		add(releaseContract, "implementation_release_contract_unknown_warnings_zero", "critical", releaseUnknown == 0, releaseUnknown)
		add(releaseContract, "implementation_release_contract_blocking_warnings_zero", "critical", releaseBlocking == 0, releaseBlocking)
		wrapperPayload := readJSON(root, wrapperProof, "warning", add)
		wrapperStatus = text(wrapperPayload["status"])
		wrapperFailed = intValue(wrapperPayload["failed_count"])
		wrapperCritical = intValue(wrapperPayload["critical_count"])
		add(wrapperProof, "wrapper_failed_zero", "critical", wrapperFailed == 0, wrapperFailed)
		add(wrapperProof, "wrapper_critical_zero", "critical", wrapperCritical == 0, wrapperCritical)
	}

	memoryBytes, err := os.ReadFile(resolve(root, memoryPath))
	if err != nil {
		add(memoryPath, "memory_note_readable", "warning", false, err.Error())
	} else {
		text := string(memoryBytes)
		add(memoryPath, "memory_mentions_go_validator_closeout", "warning", strings.Contains(text, "GO-WARNING-SOURCE-CLOSEOUT") || strings.Contains(text, "go-json-proof-warning-residue-lint"), "")
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                     base.Checks,
			Critical:                   base.Critical,
			Warnings:                   base.Warnings,
			ActiveLaneCount:            activeLaneCount,
			ChangedRouterStatus:        changedStatus,
			ValidatorBundleStatus:      bundleStatus,
			ValidatorBundleFailed:      bundleFailed,
			WrapperStatus:              wrapperStatus,
			WrapperFailed:              wrapperFailed,
			WrapperCritical:            wrapperCritical,
			WarningResidueStatus:       warningStatus,
			UnclassifiedWarningResidue: unclassified,
			ReleaseContractStatus:      releaseStatus,
			ReleaseContractReady:       releaseReady,
			ReleaseContractMissing:     releaseMissing,
			ReleaseContractUnknown:     releaseUnknown,
			ReleaseContractBlocking:    releaseBlocking,
		},
		NextSafeAction: "Use as a final implementation closeout proof check after routers, wrapper proof, warning classifier, release contract, memory, and lane register are refreshed.",
	}
}

func readJSON(root, relPath, missingSeverity string, add func(string, string, string, bool, any)) map[string]any {
	bytes, err := os.ReadFile(resolve(root, relPath))
	if err != nil {
		add(relPath, "json_exists", missingSeverity, false, err.Error())
		return map[string]any{}
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", missingSeverity, false, err.Error())
		return map[string]any{}
	}
	add(relPath, "json_parse", "info", true, "")
	return payload
}

func activeCount(payload map[string]any) int {
	if count := intValue(pathValue(payload, "summary.active_lane_count")); count > 0 {
		return count
	}
	lanes, _ := payload["lanes"].([]any)
	active := 0
	for _, raw := range lanes {
		lane, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		switch text(lane["status"]) {
		case "planned", "leased", "running":
			active++
		}
	}
	return active
}

func pathValue(payload map[string]any, dotted string) any {
	var current any = payload
	for _, part := range strings.Split(dotted, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return nil
		}
		current = object[part]
	}
	return current
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

func defaultMemoryPath() string {
	return memoryPathForTime(time.Now().UTC())
}

func memoryPathForTime(now time.Time) string {
	local := now.In(localLocation())
	return filepath.ToSlash(filepath.Join("memory", local.Format("2006-01-02")+".md"))
}

func localLocation() *time.Location {
	location, err := time.LoadLocation(defaultLocalTimezone)
	if err == nil {
		return location
	}
	return time.FixedZone(defaultLocalTimezone, -7*60*60)
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

func boolValue(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		switch strings.ToLower(strings.TrimSpace(typed)) {
		case "true", "yes", "1", "ok":
			return true
		}
	}
	return false
}
