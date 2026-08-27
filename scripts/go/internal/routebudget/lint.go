package routebudget

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_validator_route_budget_lint.v1"

var budgetRank = map[string]int{
	"micro":  0,
	"narrow": 1,
	"shared": 2,
	"major":  3,
}

type Options struct {
	Root              string
	ChangedRoutePath  string
	BundlePath        string
	TimingPath        string
	AllowTimingWarns  bool
	RequireExecution  bool
	RequireFullBudget bool
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
	Checks                        int      `json:"checks"`
	Critical                      int      `json:"critical"`
	Warnings                      int      `json:"warnings"`
	ChangedPathCount              int      `json:"changed_path_count"`
	RecommendedBudget             string   `json:"recommended_budget"`
	SelectedBudget                string   `json:"selected_budget"`
	SelectedCommandCount          int      `json:"selected_command_count"`
	ExecutedCommandCount          int      `json:"executed_command_count"`
	FailedCommandCount            int      `json:"failed_command_count"`
	MissingRequiredCommandCount   int      `json:"missing_required_command_count"`
	MissingRequiredCommands       []string `json:"missing_required_commands"`
	BlockedSafetyCommandCount     int      `json:"blocked_safety_command_count"`
	MeasuredValidatorFailureCount int      `json:"measured_validator_failure_count"`
	TimingCollectionFailureCount  int      `json:"timing_collection_failure_count"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	ChangedRoutePath  string          `json:"changed_route_path"`
	BundlePath        string          `json:"bundle_path"`
	TimingPath        string          `json:"timing_path"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

type loadedJSON struct {
	Path    string
	Payload map[string]any
	OK      bool
}

func Run(opts Options) Report {
	root := opts.Root
	if strings.TrimSpace(root) == "" {
		root = "."
	}
	changedRel := defaulted(opts.ChangedRoutePath, "tmp/changed-file-validator-router.json")
	bundleRel := defaulted(opts.BundlePath, "tmp/validator-bundle-router.json")
	timingRel := defaulted(opts.TimingPath, "tmp/validator-timing-ledger.json")

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

	changed := readJSON(root, changedRel, add)
	bundle := readJSON(root, bundleRel, add)
	timing := readJSON(root, timingRel, add)

	routePayload := changed.Payload
	if embedded := objectAt(bundle.Payload, "changed_file_route"); len(embedded) > 0 {
		routePayload = embedded
		add(bundleRel, "bundle_embeds_changed_file_route", "info", true, "")
	} else {
		add(bundleRel, "bundle_embeds_changed_file_route", "warning", false, "falling back to standalone changed-file route")
	}

	changedSummary := objectAt(routePayload, "summary")
	bundleSummary := objectAt(bundle.Payload, "summary")
	timingSummary := objectAt(timing.Payload, "summary")

	add(changedRel, "changed_route_status_ok", "critical", text(changed.Payload["status"]) == "ok", text(changed.Payload["status"]))
	add(bundleRel, "effective_changed_route_status_ok", "critical", text(routePayload["status"]) == "ok", text(routePayload["status"]))
	add(bundleRel, "effective_changed_route_authority_review_only", "critical", boolAt(routePayload, "authority_boundary.review_only"), boolAt(routePayload, "authority_boundary.review_only"))
	add(bundleRel, "effective_changed_route_does_not_execute", "critical", boolAt(routePayload, "authority_boundary.executes_validators") == false, boolAt(routePayload, "authority_boundary.executes_validators"))

	recommendedBudget := text(changedSummary["recommended_budget"])
	selectedBudget := text(bundleSummary["selected_budget"])
	add(changedRel, "recommended_budget_known", "critical", budgetKnown(recommendedBudget), recommendedBudget)
	add(bundleRel, "selected_budget_known", "critical", budgetKnown(selectedBudget), selectedBudget)
	if budgetKnown(recommendedBudget) && budgetKnown(selectedBudget) {
		ok := budgetRank[selectedBudget] >= budgetRank[recommendedBudget]
		severity := "critical"
		if !opts.RequireFullBudget && budgetRank[selectedBudget] < budgetRank[recommendedBudget] {
			severity = "warning"
		}
		add(bundleRel, "selected_budget_covers_recommended_budget", severity, ok, map[string]string{"recommended": recommendedBudget, "selected": selectedBudget})
	}

	changedPaths := stringArray(routePayload["changed_paths"])
	selectedValidators := objectArray(bundle.Payload["selected_validators"])
	recommendations := objectArray(routePayload["recommendations"])
	required := requiredCommands(changedPaths, recommendations, recommendedBudget)
	selectedCommands := selectedCommandSet(selectedValidators)
	missing := []string{}
	for _, command := range required {
		if !selectedCommands[command] {
			missing = append(missing, command)
		}
	}
	sort.Strings(missing)
	add(bundleRel, "required_closeout_commands_selected", "critical", len(missing) == 0, missing)

	blockedSafety := blockedSafetyCommands(bundle.Payload)
	add(bundleRel, "selected_commands_safety_allowed", "critical", len(blockedSafety) == 0, blockedSafety)
	mode := text(bundle.Payload["mode"])
	executed := intAt(bundle.Payload, "summary.executed_command_count")
	failed := intAt(bundle.Payload, "summary.failed_command_count")
	add(bundleRel, "bundle_failed_command_count_zero", "critical", failed == 0, failed)
	if opts.RequireExecution {
		add(bundleRel, "bundle_executed_when_required", "critical", mode == "execute" && executed > 0, map[string]any{"mode": mode, "executed": executed})
	} else {
		add(bundleRel, "bundle_plan_or_execute_mode_known", "info", mode == "plan" || mode == "execute", mode)
	}

	timingStatus := text(timing.Payload["status"])
	timingFailures := stringArray(timingSummary["measured_validator_failures"])
	timingCollectionFailures := stringArray(timingSummary["timing_collection_failures"])
	add(timingRel, "timing_status_not_blocked", "critical", !blockedStatus(timingStatus), timingStatus)
	add(timingRel, "timing_collection_failures_zero", "critical", len(timingCollectionFailures) == 0, timingCollectionFailures)
	if opts.AllowTimingWarns {
		add(timingRel, "measured_validator_failures_classified", "warning", len(timingFailures) == 0, timingFailures)
	} else {
		add(timingRel, "measured_validator_failures_zero", "critical", len(timingFailures) == 0, timingFailures)
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		ChangedRoutePath:  filepath.ToSlash(changedRel),
		BundlePath:        filepath.ToSlash(bundleRel),
		TimingPath:        filepath.ToSlash(timingRel),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                        base.Checks,
			Critical:                      base.Critical,
			Warnings:                      base.Warnings,
			ChangedPathCount:              intAt(routePayload, "summary.changed_path_count"),
			RecommendedBudget:             recommendedBudget,
			SelectedBudget:                selectedBudget,
			SelectedCommandCount:          intAt(bundle.Payload, "summary.selected_command_count"),
			ExecutedCommandCount:          executed,
			FailedCommandCount:            failed,
			MissingRequiredCommandCount:   len(missing),
			MissingRequiredCommands:       missing,
			BlockedSafetyCommandCount:     len(blockedSafety),
			MeasuredValidatorFailureCount: len(timingFailures),
			TimingCollectionFailureCount:  len(timingCollectionFailures),
		},
		NextSafeAction: "Use this as read-only closeout-budget proof. If blocked, rerun the changed-file route and selected bundle at the honest budget; do not claim implementation closure from an under-scoped proof bundle.",
	}
}

func requiredCommands(paths []string, recommendations []map[string]any, recommendedBudget string) []string {
	required := map[string]bool{}
	for _, rec := range recommendations {
		command := text(rec["command"])
		budget := text(rec["budget"])
		if command == "" {
			continue
		}
		if strings.Contains(command, "go_binary_freshness_guard.py") ||
			strings.Contains(command, "test_go_fast_proof_validators.py") ||
			strings.Contains(command, "go_fast_proof_validators.py") {
			required[command] = true
		}
		if strings.Contains(command, "py_compile") && touchesPython(paths) {
			required[command] = true
		}
		if budgetKnown(recommendedBudget) && budgetKnown(budget) && budgetRank[budget] <= budgetRank[recommendedBudget] && strings.Contains(command, "repeatable_work_closeout.py") {
			required[command] = true
		}
	}
	out := make([]string, 0, len(required))
	for command := range required {
		out = append(out, command)
	}
	sort.Strings(out)
	return out
}

func selectedCommandSet(validators []map[string]any) map[string]bool {
	out := map[string]bool{}
	for _, item := range validators {
		command := text(item["command"])
		if command != "" {
			out[command] = true
		}
	}
	return out
}

func blockedSafetyCommands(payload map[string]any) []string {
	out := []string{}
	for _, item := range objectArray(payload["command_safety"]) {
		if !truthy(item["allowed"]) {
			out = append(out, text(item["command"])+":"+text(item["reason"]))
		}
	}
	sort.Strings(out)
	return out
}

func readJSON(root, relPath string, add func(string, string, string, bool, any)) loadedJSON {
	path := relPath
	if !filepath.IsAbs(path) {
		path = filepath.Join(root, filepath.FromSlash(relPath))
	}
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(relPath, "json_exists", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_exists", "info", true, "")
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{Path: relPath, Payload: payload, OK: true}
}

func budgetKnown(value string) bool {
	_, ok := budgetRank[value]
	return ok
}

func touchesPython(paths []string) bool {
	for _, path := range paths {
		if strings.HasSuffix(path, ".py") {
			return true
		}
	}
	return false
}

func objectAt(payload map[string]any, path string) map[string]any {
	var current any = payload
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return map[string]any{}
		}
		current = object[part]
	}
	object, _ := current.(map[string]any)
	if object == nil {
		return map[string]any{}
	}
	return object
}

func intAt(payload map[string]any, path string) int {
	var current any = payload
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return 0
		}
		current = object[part]
	}
	switch typed := current.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case json.Number:
		value, _ := typed.Int64()
		return int(value)
	default:
		return 0
	}
}

func boolAt(payload map[string]any, path string) bool {
	var current any = payload
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return false
		}
		current = object[part]
	}
	return truthy(current)
}

func objectArray(value any) []map[string]any {
	raw, ok := value.([]any)
	if !ok {
		return nil
	}
	out := []map[string]any{}
	for _, item := range raw {
		object, ok := item.(map[string]any)
		if ok {
			out = append(out, object)
		}
	}
	return out
}

func stringArray(value any) []string {
	raw, ok := value.([]any)
	if !ok {
		return nil
	}
	out := []string{}
	for _, item := range raw {
		value := text(item)
		if value != "" {
			out = append(out, value)
		}
	}
	sort.Strings(out)
	return out
}

func truthy(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case float64:
		return typed != 0
	case int:
		return typed != 0
	case string:
		switch strings.ToLower(strings.TrimSpace(typed)) {
		case "1", "true", "yes", "ok", "allowed":
			return true
		}
	}
	return false
}

func blockedStatus(status string) bool {
	lower := strings.ToLower(strings.TrimSpace(status))
	return strings.Contains(lower, "blocked") || strings.Contains(lower, "error") || strings.Contains(lower, "failed")
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func defaulted(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}
