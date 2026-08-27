package cronproof

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

const SchemaVersion = "go_cron_contract_json_proof_lint.v1"

type Options struct {
	Root            string
	ContractsDir    string
	ControlPacket   string
	MaxAgeHours     int
	MaxPromptChars  int
	MaxMessageLines int
	Now             time.Time
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
	Checks                               int `json:"checks"`
	Critical                             int `json:"critical"`
	Warnings                             int `json:"warnings"`
	ContractCount                        int `json:"contract_count"`
	EnabledContractCount                 int `json:"enabled_contract_count"`
	DisabledContractCount                int `json:"disabled_contract_count"`
	MissingExpectedArtifactContractCount int `json:"missing_expected_artifact_contract_count"`
	ControlValidationErrorCount          int `json:"control_validation_error_count"`
	ControlBlockedSignalCount            int `json:"control_blocked_signal_count"`
	ControlEscalationSignalCount         int `json:"control_escalation_signal_count"`
	StalePacketCount                     int `json:"stale_packet_count"`
	PromptBloatContractCount             int `json:"prompt_bloat_contract_count"`
	MessageLineBloatContractCount        int `json:"message_line_bloat_contract_count"`
	DeliveryMismatchCount                int `json:"delivery_mismatch_count"`
	ControlDeliveryMismatchCount         int `json:"control_delivery_mismatch_count"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	ContractsDir      string          `json:"contracts_dir"`
	ControlPacket     string          `json:"control_packet"`
	MaxAgeHours       int             `json:"max_age_hours"`
	MaxPromptChars    int             `json:"max_prompt_chars"`
	MaxMessageLines   int             `json:"max_message_lines"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

type loadedJSON struct {
	RelPath string
	Payload map[string]any
	OK      bool
}

var forbiddenAuthorityTerms = []string{
	"brokerage_or_account_action",
	"capital_deployment",
	"canon_or_portfolio_mutation",
	"config_auth_runtime_mutation",
	"cron_schedule_mutation",
	"cron_state_mutation",
	"customer_or_external_delivery",
	"db_mutation",
	"money_movement",
	"owner_approval_inferred",
	"paper_or_live_execution",
	"repair_execution_allowed",
	"runtime_config_mutation",
	"sql_write_or_import",
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	contractsDir := defaulted(opts.ContractsDir, "state/cron-contracts")
	controlPacket := defaulted(opts.ControlPacket, "tmp/cron-control-packet.json")
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 96
	}
	maxPromptChars := opts.MaxPromptChars
	if maxPromptChars <= 0 {
		maxPromptChars = 1800
	}
	maxMessageLines := opts.MaxMessageLines
	if maxMessageLines <= 0 {
		maxMessageLines = 30
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

	contractCount := 0
	enabledCount := 0
	disabledCount := 0
	missingExpectedArtifactContracts := 0
	stalePackets := 0
	promptBloatContracts := 0
	messageLineBloatContracts := 0
	deliveryMismatches := 0
	controlDeliveryMismatches := 0

	contractPaths, err := filepath.Glob(resolve(root, filepath.ToSlash(filepath.Join(contractsDir, "*.json"))))
	if err != nil {
		add(contractsDir, "contracts_glob", "critical", false, err.Error())
	} else if len(contractPaths) == 0 {
		add(contractsDir, "contracts_present", "critical", false, "no cron contract JSON files found")
	} else {
		sort.Strings(contractPaths)
		add(contractsDir, "contracts_present", "info", true, len(contractPaths))
	}

	for _, path := range contractPaths {
		relPath := rel(root, path)
		contract := readJSON(root, relPath, add)
		if !contract.OK {
			continue
		}
		contractCount++
		enabled, enabledOK := boolValue(contract.Payload["enabled"])
		add(relPath, "enabled_bool_present", "critical", enabledOK, fmt.Sprint(contract.Payload["enabled"]))
		if enabled {
			enabledCount++
		} else {
			disabledCount++
		}
		add(relPath, "schema_valid", "critical", text(contract.Payload["schema"]) == "veritas.cron_contract.v1", text(contract.Payload["schema"]))
		add(relPath, "job_id_present", "critical", text(contract.Payload["job_id"]) != "", "")
		add(relPath, "name_present", "critical", text(contract.Payload["name"]) != "", "")
		add(relPath, "schedule_shape", "critical", scheduleOK(contract.Payload["schedule"]), contract.Payload["schedule"])
		expectedArtifacts := stringArray(contract.Payload["expected_artifacts"])
		if enabled && len(expectedArtifacts) == 0 {
			missingExpectedArtifactContracts++
		}
		add(relPath, "enabled_contract_has_expected_artifacts", "warning", !enabled || len(expectedArtifacts) > 0, len(expectedArtifacts))
		missingArtifacts := []string{}
		for _, artifact := range expectedArtifacts {
			if strings.TrimSpace(artifact) == "" {
				missingArtifacts = append(missingArtifacts, "<blank>")
				continue
			}
			if _, err := os.Stat(resolve(root, artifact)); err != nil {
				missingArtifacts = append(missingArtifacts, artifact)
			}
		}
		add(relPath, "expected_artifacts_exist_or_are_reviewable", "warning", len(missingArtifacts) == 0, firstN(missingArtifacts, 12))
		checkAuthority(relPath, contract.Payload["authority_boundary"], add)
		promptBloated, lineBloated := checkPromptBloat(relPath, contract.Payload, maxPromptChars, maxMessageLines, add)
		if promptBloated {
			promptBloatContracts++
		}
		if lineBloated {
			messageLineBloatContracts++
		}
		deliveryMismatches += checkDeliveryContract(relPath, contract.Payload, add)
	}

	control := readJSON(root, controlPacket, add)
	controlErrors := 0
	blockedSignals := 0
	escalationSignals := 0
	if control.OK {
		controlStatus := text(control.Payload["status"])
		add(controlPacket, "control_status_not_blocked", "warning", !blockedStatus(controlStatus), controlStatus)
		if generated := timestampText(control.Payload); generated == "" {
			add(controlPacket, "generated_at_present", "warning", false, "")
		} else if stale, ok := checkFreshness(controlPacket, generated, now, maxAgeHours, add); ok && stale {
			stalePackets++
		}
		checkAuthority(controlPacket, control.Payload["authority_boundary"], add)
		controlErrors = arrayLen(pathValue(control.Payload, "validation.errors"))
		add(controlPacket, "control_validation_errors_empty", "warning", controlErrors == 0, controlErrors)
		add(controlPacket, "control_validation_warnings_visible", "info", true, arrayLen(pathValue(control.Payload, "validation.warnings")))
		blockedSignals = intValue(pathValue(control.Payload, "summary.blocked_count"))
		escalationSignals = intValue(pathValue(control.Payload, "summary.escalation_signal_count"))
		add(controlPacket, "blocked_signals_zero", "warning", blockedSignals == 0, blockedSignals)
		add(controlPacket, "escalation_signals_zero", "warning", escalationSignals == 0, escalationSignals)
		freshnessStatus := text(pathValue(control.Payload, "freshness.status"))
		add(controlPacket, "freshness_status_not_blocked", "warning", !blockedStatus(freshnessStatus), freshnessStatus)
		add(controlPacket, "freshness_validation_errors_empty", "warning", arrayLen(pathValue(control.Payload, "freshness.validation.errors")) == 0, pathValue(control.Payload, "freshness.validation.errors"))
		controlDeliveryMismatches = checkControlDeliverySignals(controlPacket, control.Payload, add)
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		ContractsDir:      filepath.ToSlash(contractsDir),
		ControlPacket:     filepath.ToSlash(controlPacket),
		MaxAgeHours:       maxAgeHours,
		MaxPromptChars:    maxPromptChars,
		MaxMessageLines:   maxMessageLines,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                               base.Checks,
			Critical:                             base.Critical,
			Warnings:                             base.Warnings,
			ContractCount:                        contractCount,
			EnabledContractCount:                 enabledCount,
			DisabledContractCount:                disabledCount,
			MissingExpectedArtifactContractCount: missingExpectedArtifactContracts,
			ControlValidationErrorCount:          controlErrors,
			ControlBlockedSignalCount:            blockedSignals,
			ControlEscalationSignalCount:         escalationSignals,
			StalePacketCount:                     stalePackets,
			PromptBloatContractCount:             promptBloatContracts,
			MessageLineBloatContractCount:        messageLineBloatContracts,
			DeliveryMismatchCount:                deliveryMismatches,
			ControlDeliveryMismatchCount:         controlDeliveryMismatches,
		},
		NextSafeAction: "Use as advisory cron contract/control proof. Repair owner cron artifacts through cron control routes; do not mutate schedules from this validator.",
	}
}

func readJSON(root, relPath string, add func(string, string, string, bool, any)) loadedJSON {
	bytes, err := os.ReadFile(resolve(root, relPath))
	if err != nil {
		add(relPath, "json_exists", "critical", false, err.Error())
		return loadedJSON{RelPath: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_exists", "info", true, "")
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", "critical", false, err.Error())
		return loadedJSON{RelPath: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{RelPath: relPath, Payload: payload, OK: true}
}

func scheduleOK(value any) bool {
	schedule, ok := value.(map[string]any)
	if !ok {
		return false
	}
	kind := text(schedule["kind"])
	switch kind {
	case "cron":
		return text(schedule["expr"]) != "" && text(schedule["tz"]) != ""
	case "at":
		return text(schedule["at"]) != ""
	default:
		return false
	}
}

func checkAuthority(relPath string, raw any, add func(string, string, string, bool, any)) {
	if raw == nil {
		add(relPath, "authority_boundary_present", "critical", false, "missing authority_boundary")
		return
	}
	authority, ok := raw.(map[string]any)
	if !ok {
		add(relPath, "authority_boundary_present", "critical", false, "authority_boundary is not an object")
		return
	}
	add(relPath, "authority_boundary_present", "info", true, "")
	violations := authorityViolations(authority, "")
	add(relPath, "forbidden_authority_flags_false", "critical", len(violations) == 0, violations)
}

func checkPromptBloat(relPath string, payload map[string]any, maxPromptChars, maxMessageLines int, add func(string, string, string, bool, any)) (bool, bool) {
	message := payloadMessage(payload)
	if message == "" {
		if commandPayloadHasArgv(payload) {
			add(relPath, "payload_command_argv_present_for_bloat_check", "info", true, "direct command payload has no prompt text")
			return false, false
		}
		add(relPath, "payload_message_present_for_bloat_check", "warning", false, "missing payload.message/payload.text")
		return false, false
	}
	charCount := len([]rune(message))
	lineCount := 1
	if message != "" {
		lineCount = strings.Count(message, "\n") + 1
	}
	promptOK := charCount <= maxPromptChars
	lineOK := lineCount <= maxMessageLines
	add(relPath, "payload_message_within_prompt_char_budget", "warning", promptOK, map[string]int{"chars": charCount, "max": maxPromptChars})
	add(relPath, "payload_message_within_line_budget", "warning", lineOK, map[string]int{"lines": lineCount, "max": maxMessageLines})
	return !promptOK, !lineOK
}

func commandPayloadHasArgv(payload map[string]any) bool {
	if strings.ToLower(text(pathValue(payload, "payload.kind"))) != "command" {
		return false
	}
	raw := pathValue(payload, "payload.argv")
	values, ok := raw.([]any)
	if !ok {
		return false
	}
	for _, value := range values {
		if text(value) != "" {
			return true
		}
	}
	return false
}

func checkDeliveryContract(relPath string, payload map[string]any, add func(string, string, string, bool, any)) int {
	mismatches := 0
	message := strings.ToLower(payloadMessage(payload))
	delivery := objectAt(payload, "delivery")
	mode := strings.ToLower(text(delivery["mode"]))
	channel := strings.TrimSpace(text(delivery["channel"]))
	payloadKind := strings.ToLower(text(pathValue(payload, "payload.kind")))
	hasNoReplyContract := strings.Contains(message, "no_reply")
	impliesSend := containsAny(message, []string{"--send", "telegram", "notifier", "send ", "sends ", "delivery"})
	if payloadKind == "agentturn" || payloadMessage(payload) != "" {
		ok := mode != ""
		add(relPath, "delivery_mode_present_for_agent_payload", "warning", ok, map[string]string{"payload_kind": payloadKind, "delivery_mode": mode})
		if !ok {
			mismatches++
		}
	}
	if mode == "none" && channel != "" {
		mismatches++
		add(relPath, "delivery_none_has_no_channel", "warning", false, map[string]string{"mode": mode, "channel": channel})
	} else {
		add(relPath, "delivery_none_has_no_channel", "info", true, map[string]string{"mode": mode, "channel": channel})
	}
	if mode == "none" && impliesSend && !hasNoReplyContract {
		mismatches++
		add(relPath, "delivery_none_send_language_has_no_reply_contract", "warning", false, "send/telegram/notifier language without NO_REPLY contract")
	} else {
		add(relPath, "delivery_none_send_language_has_no_reply_contract", "info", true, "")
	}
	if mode != "" && mode != "none" && hasNoReplyContract && !impliesSend {
		mismatches++
		add(relPath, "delivery_enabled_matches_reply_contract", "warning", false, map[string]string{"mode": mode, "detail": "NO_REPLY-only prompt with non-none delivery"})
	} else {
		add(relPath, "delivery_enabled_matches_reply_contract", "info", true, mode)
	}
	return mismatches
}

func checkControlDeliverySignals(relPath string, payload map[string]any, add func(string, string, string, bool, any)) int {
	mismatches := 0
	sendsMessages := truthy(pathValue(payload, "authority_boundary.sends_messages"))
	add(relPath, "control_packet_does_not_send_messages", "critical", !sendsMessages, sendsMessages)
	if sendsMessages {
		mismatches++
	}
	for _, job := range objectArray(pathValue(payload, "freshness.jobs")) {
		jobName := text(job["name"])
		if jobName == "" {
			jobName = text(job["id"])
		}
		jobPath := relPath + "#cron_job:" + jobName
		signalClass := strings.ToUpper(text(job["signal_class"]))
		if signalClass == "" {
			signalClass = strings.ToUpper(text(job["underlying_signal_class"]))
		}
		expectedWarningQuiet := truthy(job["expected_warning_quiet"]) || truthy(job["standing_review_quiet"])
		hiddenHandoffs := []string{}
		for _, artifact := range objectArray(job["expected_artifacts"]) {
			action := strings.ToUpper(text(artifact["operator_action"]))
			if action == "MAIN_HANDOFF_REQUIRED" && !truthy(artifact["expected_warning_quiet"]) {
				hiddenHandoffs = append(hiddenHandoffs, text(artifact["path"]))
			}
		}
		sort.Strings(hiddenHandoffs)
		ok := !(signalClass == "NO_REPLY" && len(hiddenHandoffs) > 0 && !expectedWarningQuiet)
		if !ok {
			mismatches++
		}
		add(jobPath, "no_reply_does_not_hide_unquiet_handoff", "warning", ok, firstN(hiddenHandoffs, 8))
	}
	return mismatches
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

func checkFreshness(path, generated string, now time.Time, maxAgeHours int, add func(string, string, string, bool, any)) (bool, bool) {
	timestamp, err := time.Parse(time.RFC3339, generated)
	if err != nil {
		add(path, "generated_at_parse", "warning", false, err.Error())
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

func payloadMessage(payload map[string]any) string {
	if value := text(pathValue(payload, "payload.message")); value != "" {
		return value
	}
	return text(pathValue(payload, "payload.text"))
}

func resolve(root, relPath string) string {
	if filepath.IsAbs(relPath) {
		return relPath
	}
	return filepath.Join(root, filepath.FromSlash(relPath))
}

func rel(root, path string) string {
	if value, err := filepath.Rel(root, path); err == nil {
		return filepath.ToSlash(value)
	}
	return filepath.ToSlash(path)
}

func defaulted(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func boolValue(value any) (bool, bool) {
	typed, ok := value.(bool)
	return typed, ok
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

func stringArray(value any) []string {
	raw, ok := value.([]any)
	if !ok {
		return nil
	}
	out := []string{}
	for _, item := range raw {
		if object, ok := item.(map[string]any); ok {
			out = append(out, text(object["path"]))
			continue
		}
		out = append(out, text(item))
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

func intValue(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case int64:
		return int(typed)
	case float64:
		return int(typed)
	case string:
		var parsed int
		fmt.Sscanf(strings.TrimSpace(typed), "%d", &parsed)
		return parsed
	default:
		return 0
	}
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

func objectAt(payload map[string]any, path string) map[string]any {
	value := pathValue(payload, path)
	object, _ := value.(map[string]any)
	if object == nil {
		return map[string]any{}
	}
	return object
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

func firstN(values []string, n int) []string {
	sort.Strings(values)
	if len(values) <= n {
		return values
	}
	return values[:n]
}

func containsAny(value string, needles []string) bool {
	for _, needle := range needles {
		if strings.Contains(value, needle) {
			return true
		}
	}
	return false
}
