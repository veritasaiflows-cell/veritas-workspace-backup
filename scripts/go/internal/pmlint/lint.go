package pmlint

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_pm_queue_authority_lint.v1"

type Options struct {
	Root        string
	PacketPath  string
	MaxAgeHours int
	Require     bool
	Now         time.Time
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
	Checks                          int      `json:"checks"`
	Critical                        int      `json:"critical"`
	Warnings                        int      `json:"warnings"`
	PacketMissing                   bool     `json:"packet_missing"`
	StalePacketCount                int      `json:"stale_packet_count"`
	StaleLaneCount                  int      `json:"stale_lane_count"`
	BlockedLaneCount                int      `json:"blocked_lane_count"`
	NeedsValidationLaneCount        int      `json:"needs_validation_lane_count"`
	ReadyJobCount                   int      `json:"ready_job_count"`
	BlockedJobCount                 int      `json:"blocked_job_count"`
	OwnerDecisionJobCount           int      `json:"owner_decision_job_count"`
	AutoMainExecutableJobCount      int      `json:"auto_main_executable_job_count"`
	AutoCronExecutableJobCount      int      `json:"auto_cron_executable_job_count"`
	AutoHeartbeatExecutableJobCount int      `json:"auto_heartbeat_executable_job_count"`
	DetailJobCount                  int      `json:"detail_job_count"`
	ForbiddenAuthorityFlagCount     int      `json:"forbidden_authority_flag_count"`
	AuthorityLanguageViolationCount int      `json:"authority_language_violation_count"`
	UnsafeAutoJobCount              int      `json:"unsafe_auto_job_count"`
	OwnerGateAutoExecutionCount     int      `json:"owner_gate_auto_execution_count"`
	MissingStopLineJobIDs           []string `json:"missing_stop_line_job_ids"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	PacketPath        string          `json:"packet_path"`
	MaxAgeHours       int             `json:"max_age_hours"`
	RequirePacket     bool            `json:"require_packet"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

type loadedJSON struct {
	Payload map[string]any
	OK      bool
	Missing bool
}

var forbiddenAuthorityTerms = []string{
	"brokerage_or_account_action",
	"capital_deployment",
	"canon_or_portfolio_mutation",
	"cleanup_move_delete_archive",
	"config_auth_runtime_mutation",
	"customer_or_external_delivery",
	"executes_work",
	"heartbeat_executes_action",
	"heartbeat_executes_work",
	"heartbeat_spawns_helpers",
	"money_movement",
	"owner_approval_inferred",
	"paper_or_live_execution",
	"public_launch",
	"real_customer_data",
	"spawns_helpers",
	"sql_first_promotion",
	"sql_or_ticker_import",
}

var dangerousLanguage = []string{
	"account action allowed",
	"brokerage action allowed",
	"capital deployment approved",
	"capital deployment allowed",
	"customer delivery allowed",
	"external delivery allowed",
	"live execution allowed",
	"money movement allowed",
	"owner approval inferred",
	"paper execution allowed",
	"paper/live execution allowed",
	"portfolio mutation allowed",
	"public launch allowed",
	"sql import allowed",
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	packetPath := defaulted(opts.PacketPath, "tmp/pm-control-packet.json")
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 6
	}
	now := opts.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}

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

	packet := readJSON(root, packetPath, opts.Require, add)
	summary := Summary{PacketMissing: packet.Missing}
	if !packet.OK {
		base := reporting.SummarizeFindings(findings)
		summary.Checks = base.Checks
		summary.Critical = base.Critical
		summary.Warnings = base.Warnings
		return report(root, packetPath, maxAgeHours, opts.Require, findings, summary, "Refresh or generate tmp/pm-control-packet.json before using PM queue authority state.")
	}

	add(packetPath, "schema_valid", "critical", text(packet.Payload["schema"]) == "veritas.pm_control_packet.v1", text(packet.Payload["schema"]))
	status := text(packet.Payload["status"])
	add(packetPath, "status_present", "critical", status != "", status)
	add(packetPath, "status_not_blocked", "critical", !blockedStatus(status), status)
	if generated := timestampText(packet.Payload); generated == "" {
		add(packetPath, "generated_at_present", "critical", false, "")
	} else if stale, ok := checkFreshness(packetPath, generated, now, maxAgeHours, add); ok && stale {
		summary.StalePacketCount++
	}
	checkValidation(packetPath, packet.Payload, add)
	summary.ForbiddenAuthorityFlagCount += checkAuthority(packetPath, packet.Payload["authority_boundary"], add)
	summary.AuthorityLanguageViolationCount += checkAuthorityLanguage(packetPath, packet.Payload, add)

	pmReadiness := objectAt(packet.Payload, "summary.pm_readiness")
	summary.StaleLaneCount = intAt(pmReadiness, "stale_lanes")
	summary.BlockedLaneCount = intAt(pmReadiness, "blocked_lanes")
	summary.NeedsValidationLaneCount = intAt(pmReadiness, "needs_validation_lanes")
	add(packetPath, "stale_lanes_zero", "warning", summary.StaleLaneCount == 0, summary.StaleLaneCount)
	add(packetPath, "blocked_lanes_visible", "warning", summary.BlockedLaneCount == 0, summary.BlockedLaneCount)
	add(packetPath, "needs_validation_lanes_zero", "warning", summary.NeedsValidationLaneCount == 0, summary.NeedsValidationLaneCount)

	staleDigest := objectAt(packet.Payload, "summary.stale_lane_digest")
	digestCount := intAt(staleDigest, "stale_lane_count")
	add(packetPath, "stale_lane_digest_matches_readiness", "warning", digestCount == summary.StaleLaneCount, map[string]int{"digest": digestCount, "readiness": summary.StaleLaneCount})
	checkStaleLaneDigest(packetPath, staleDigest, add)

	queueSummary := objectAt(packet.Payload, "summary.implementation_queue")
	summary.ReadyJobCount = intAt(queueSummary, "ready_job_count")
	summary.BlockedJobCount = intAt(queueSummary, "blocked_job_count")
	summary.OwnerDecisionJobCount = intAt(queueSummary, "owner_decision_job_count")
	summary.AutoMainExecutableJobCount = intAt(queueSummary, "auto_main_executable_job_count")
	summary.AutoCronExecutableJobCount = intAt(queueSummary, "auto_cron_executable_job_count")
	summary.AutoHeartbeatExecutableJobCount = intAt(queueSummary, "auto_heartbeat_executable_job_count")
	add(packetPath, "blocked_jobs_zero", "warning", summary.BlockedJobCount == 0, summary.BlockedJobCount)
	add(packetPath, "owner_decision_jobs_zero", "warning", summary.OwnerDecisionJobCount == 0, summary.OwnerDecisionJobCount)
	add(packetPath, "heartbeat_auto_execution_zero", "critical", summary.AutoHeartbeatExecutableJobCount == 0, summary.AutoHeartbeatExecutableJobCount)

	checkHandoff(packetPath, packet.Payload, add)
	jobs := objectArray(pathValue(packet.Payload, "sections.pm_implementation_job_queue.jobs"))
	summary.DetailJobCount = len(jobs)
	missingStopLines := []string{}
	for _, job := range jobs {
		jobID := text(job["job_id"])
		if jobID == "" {
			jobID = "<unknown_job>"
		}
		jobPath := packetPath + "#job:" + jobID
		summary.ForbiddenAuthorityFlagCount += checkAuthority(jobPath, job["authority_boundary"], add)
		summary.ForbiddenAuthorityFlagCount += checkAuthority(jobPath, pathValue(job, "helper_packet.authority_boundary"), add)
		summary.ForbiddenAuthorityFlagCount += checkAuthority(jobPath, pathValue(job, "automation_capabilities.authority_boundary"), add)
		summary.AuthorityLanguageViolationCount += checkAuthorityLanguage(jobPath, job, add)
		autoMain := truthy(job["auto_main_may_execute"])
		autoCron := truthy(job["auto_cron_may_execute"])
		autoHeartbeat := truthy(job["auto_heartbeat_may_execute"])
		ownerGate := truthy(job["owner_gate_required"]) || truthy(pathValue(job, "automation_capabilities.owner_gate_required"))
		proofOnly := truthy(job["proof_only"]) || truthy(pathValue(job, "automation_capabilities.proof_only"))
		unsafeCommands := stringArray(pathValue(job, "automation_capabilities.unsafe_proof_commands"))
		if (autoMain || autoCron || autoHeartbeat) && !proofOnly {
			summary.UnsafeAutoJobCount++
		}
		if ownerGate && (autoMain || autoCron || autoHeartbeat) {
			summary.OwnerGateAutoExecutionCount++
		}
		add(jobPath, "auto_jobs_are_proof_only", "critical", !(autoMain || autoCron || autoHeartbeat) || proofOnly, map[string]any{"auto_main": autoMain, "auto_cron": autoCron, "auto_heartbeat": autoHeartbeat, "proof_only": proofOnly})
		add(jobPath, "owner_gated_jobs_not_auto_executable", "critical", !ownerGate || !(autoMain || autoCron || autoHeartbeat), map[string]any{"owner_gate_required": ownerGate, "auto_main": autoMain, "auto_cron": autoCron, "auto_heartbeat": autoHeartbeat})
		add(jobPath, "heartbeat_auto_execution_false", "critical", !autoHeartbeat, autoHeartbeat)
		add(jobPath, "unsafe_proof_commands_empty", "critical", len(unsafeCommands) == 0, unsafeCommands)
		stopLines := stringArray(job["stop_lines"])
		if len(stopLines) == 0 {
			missingStopLines = append(missingStopLines, jobID)
		}
		add(jobPath, "stop_lines_present", "warning", len(stopLines) > 0, len(stopLines))
	}
	sort.Strings(missingStopLines)
	summary.MissingStopLineJobIDs = missingStopLines

	base := reporting.SummarizeFindings(findings)
	summary.Checks = base.Checks
	summary.Critical = base.Critical
	summary.Warnings = base.Warnings
	return report(root, packetPath, maxAgeHours, opts.Require, findings, summary, "Use this read-only PM lint to route stale lanes or unsafe automation flags back through PM control; do not execute, approve, or mutate from the lint.")
}

func report(root, packetPath string, maxAgeHours int, require bool, findings []Finding, summary Summary, next string) Report {
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(summary.Critical, summary.Warnings),
		Root:              filepath.ToSlash(root),
		PacketPath:        filepath.ToSlash(packetPath),
		MaxAgeHours:       maxAgeHours,
		RequirePacket:     require,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary:           summary,
		NextSafeAction:    next,
	}
}

func readJSON(root, relPath string, require bool, add func(string, string, string, bool, any)) loadedJSON {
	bytes, err := os.ReadFile(resolve(root, relPath))
	if err != nil {
		severity := "warning"
		if require {
			severity = "critical"
		}
		add(relPath, "packet_exists", severity, false, err.Error())
		return loadedJSON{Payload: map[string]any{}, Missing: true}
	}
	add(relPath, "packet_exists", "info", true, "")
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", "critical", false, err.Error())
		return loadedJSON{Payload: map[string]any{}}
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{Payload: payload, OK: true}
}

func checkValidation(relPath string, payload map[string]any, add func(string, string, string, bool, any)) {
	validation := objectAt(payload, "validation")
	if len(validation) == 0 {
		add(relPath, "validation_envelope_present", "warning", false, "missing validation object")
		return
	}
	add(relPath, "validation_envelope_present", "info", true, "")
	status := text(validation["status"])
	add(relPath, "validation_status_not_blocked", "critical", !blockedStatus(status), status)
	add(relPath, "validation_errors_empty", "critical", arrayLen(validation["errors"]) == 0, validation["errors"])
	add(relPath, "validation_warnings_visible", "info", true, arrayLen(validation["warnings"]))
}

func checkStaleLaneDigest(relPath string, digest map[string]any, add func(string, string, string, bool, any)) {
	if len(digest) == 0 {
		add(relPath, "stale_lane_digest_present", "warning", false, "missing stale_lane_digest")
		return
	}
	lanes := objectArray(digest["lanes"])
	for _, lane := range lanes {
		laneID := text(lane["lane_id"])
		if laneID == "" {
			laneID = "<unknown_lane>"
		}
		lanePath := relPath + "#stale_lane:" + laneID
		add(lanePath, "stale_lane_has_top_job", "warning", text(lane["top_job_id"]) != "", lane["top_job_id"])
		add(lanePath, "stale_lane_has_proof_commands", "warning", len(stringArray(lane["proof_commands"])) > 0, lane["proof_commands"])
		add(lanePath, "stale_lane_handoff_main_only", "critical", !truthy(lane["inline_execution_allowed"]) && !truthy(lane["heartbeat_may_execute"]), map[string]any{"inline_execution_allowed": lane["inline_execution_allowed"], "heartbeat_may_execute": lane["heartbeat_may_execute"]})
	}
}

func checkHandoff(relPath string, payload map[string]any, add func(string, string, string, bool, any)) {
	handoff := objectAt(payload, "sections.pm_main_session_handoff")
	if len(handoff) == 0 {
		handoff = objectAt(payload, "summary.main_session_handoff")
	}
	if len(handoff) == 0 {
		add(relPath, "main_session_handoff_present", "warning", false, "missing handoff section")
		return
	}
	add(relPath, "main_session_handoff_present", "info", true, text(handoff["status"]))
	selectedAction := objectAt(handoff, "selected_action")
	if len(selectedAction) == 0 {
		selectedAction = objectAt(payload, "summary.top_next_action")
	}
	if len(selectedAction) > 0 {
		actionPath := relPath + "#selected_action"
		add(actionPath, "selected_action_review_only", "critical", strings.EqualFold(text(selectedAction["authority"]), "review_only") || text(selectedAction["authority"]) == "", text(selectedAction["authority"]))
		add(actionPath, "selected_action_not_inline_executable", "critical", !truthy(selectedAction["inline_execution_allowed"]), selectedAction["inline_execution_allowed"])
		add(actionPath, "selected_action_not_heartbeat_executable", "critical", !truthy(selectedAction["heartbeat_may_execute"]), selectedAction["heartbeat_may_execute"])
		add(actionPath, "selected_action_stop_lines_present", "warning", len(stringArray(selectedAction["stop_lines"])) > 0, len(stringArray(selectedAction["stop_lines"])))
	}
	classification := objectAt(handoff, "signal_classification")
	if len(classification) > 0 {
		class := strings.ToUpper(text(classification["class"]))
		ownerDecision := truthy(classification["owner_decision_required"])
		add(relPath+"#signal_classification", "owner_decision_signal_requires_owner", "critical", class != "OWNER_DECISION" || ownerDecision, map[string]any{"class": class, "owner_decision_required": ownerDecision})
		add(relPath+"#signal_classification", "heartbeat_not_executable", "critical", !truthy(classification["heartbeat_may_execute"]), classification["heartbeat_may_execute"])
	}
	checkValidation(relPath+"#pm_main_session_handoff", handoff, add)
	summary := objectAt(handoff, "implementation_queue_summary")
	if len(summary) > 0 {
		add(relPath+"#handoff_queue_summary", "owner_gate_required_jobs_zero", "warning", intAt(summary, "owner_gate_required_job_count") == 0, intAt(summary, "owner_gate_required_job_count"))
	}
}

func checkAuthority(relPath string, raw any, add func(string, string, string, bool, any)) int {
	if raw == nil {
		return 0
	}
	authority, ok := raw.(map[string]any)
	if !ok {
		add(relPath, "authority_boundary_shape", "critical", false, "authority boundary is not an object")
		return 1
	}
	violations := authorityViolations(authority, "")
	add(relPath, "forbidden_authority_flags_false", "critical", len(violations) == 0, violations)
	return len(violations)
}

func authorityViolations(value any, prefix string) []string {
	violations := []string{}
	object, ok := value.(map[string]any)
	if !ok {
		return violations
	}
	for key, raw := range object {
		path := key
		if prefix != "" {
			path = prefix + "." + key
		}
		if child, ok := raw.(map[string]any); ok {
			violations = append(violations, authorityViolations(child, path)...)
			continue
		}
		if forbiddenAuthorityKey(key) && truthy(raw) {
			violations = append(violations, path+"="+text(raw))
		}
	}
	sort.Strings(violations)
	return violations
}

func forbiddenAuthorityKey(key string) bool {
	lower := strings.ToLower(key)
	for _, term := range forbiddenAuthorityTerms {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

func checkAuthorityLanguage(relPath string, value any, add func(string, string, string, bool, any)) int {
	violations := []string{}
	collectDangerousLanguage(value, "", &violations)
	sort.Strings(violations)
	add(relPath, "forbidden_authority_language_absent", "critical", len(violations) == 0, firstN(violations, 12))
	return len(violations)
}

func collectDangerousLanguage(value any, path string, violations *[]string) {
	switch typed := value.(type) {
	case map[string]any:
		for key, raw := range typed {
			childPath := key
			if path != "" {
				childPath = path + "." + key
			}
			collectDangerousLanguage(raw, childPath, violations)
		}
	case []any:
		for idx, raw := range typed {
			collectDangerousLanguage(raw, fmt.Sprintf("%s[%d]", path, idx), violations)
		}
	case string:
		lower := strings.ToLower(typed)
		if languageNegated(lower) {
			return
		}
		for _, phrase := range dangerousLanguage {
			if strings.Contains(lower, phrase) {
				*violations = append(*violations, path+": "+phrase)
			}
		}
	}
}

func languageNegated(value string) bool {
	for _, term := range []string{"no ", "not ", "false", "blocked", "owner-gated", "review-only", "review only", "must not", "without"} {
		if strings.Contains(value, term) {
			return true
		}
	}
	return false
}

func checkFreshness(path, generated string, now time.Time, maxAgeHours int, add func(string, string, string, bool, any)) (bool, bool) {
	timestamp, err := time.Parse(time.RFC3339, generated)
	if err != nil {
		add(path, "generated_at_parse", "critical", false, err.Error())
		return false, false
	}
	age := now.Sub(timestamp.UTC())
	if age < -5*time.Minute {
		add(path, "generated_at_not_future", "critical", false, fmt.Sprintf("future_by=%s", -age))
		return false, true
	}
	stale := age > time.Duration(maxAgeHours)*time.Hour
	add(path, "freshness_within_max_age", "warning", !stale, fmt.Sprintf("age_hours=%.1f max_age_hours=%d", age.Hours(), maxAgeHours))
	return stale, true
}

func timestampText(payload map[string]any) string {
	if value := text(payload["generated_at_utc"]); value != "" {
		return value
	}
	return text(payload["generated_at"])
}

func resolve(root, relPath string) string {
	if filepath.IsAbs(relPath) {
		return relPath
	}
	return filepath.Join(root, filepath.FromSlash(relPath))
}

func objectAt(payload map[string]any, path string) map[string]any {
	value := pathValue(payload, path)
	object, _ := value.(map[string]any)
	if object == nil {
		return map[string]any{}
	}
	return object
}

func pathValue(payload map[string]any, path string) any {
	var current any = payload
	for _, part := range strings.Split(path, ".") {
		object, ok := current.(map[string]any)
		if !ok {
			return nil
		}
		current = object[part]
	}
	return current
}

func intAt(payload map[string]any, path string) int {
	if len(payload) == 0 {
		return 0
	}
	return intValue(pathValue(payload, path))
}

func intValue(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case json.Number:
		value, _ := typed.Int64()
		return int(value)
	case string:
		var parsed int
		fmt.Sscanf(strings.TrimSpace(typed), "%d", &parsed)
		return parsed
	default:
		return 0
	}
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
		if value := text(item); value != "" {
			out = append(out, value)
		}
	}
	return out
}

func arrayLen(value any) int {
	switch typed := value.(type) {
	case []any:
		return len(typed)
	case []string:
		return len(typed)
	case nil:
		return 0
	default:
		return 1
	}
}

func truthy(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case float64:
		return typed != 0
	case int:
		return typed != 0
	case int64:
		return typed != 0
	case string:
		switch strings.ToLower(strings.TrimSpace(typed)) {
		case "1", "true", "yes", "allowed", "ok":
			return true
		}
	}
	return false
}

func blockedStatus(status string) bool {
	lower := strings.ToLower(strings.TrimSpace(status))
	if lower == "" {
		return false
	}
	for _, term := range []string{"blocked", "critical", "error", "failed", "fail_closed"} {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
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

func firstN(values []string, n int) []string {
	if len(values) <= n {
		return values
	}
	return values[:n]
}
