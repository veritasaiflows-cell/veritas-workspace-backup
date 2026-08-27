package answercheck

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

const SchemaVersion = "go_finance_answer_completeness_validator.v1"

var defaultRequiredSections = []string{
	"thesis",
	"business_quality_moat",
	"bull_case",
	"bear_case",
	"earnings_guidance",
	"financial_metrics",
	"valuation",
	"technical_setup",
	"catalyst_news_macro",
	"risk_invalidation",
	"portfolio_fit",
	"entry_stop_sizing",
	"decision_state",
	"trade_grade",
	"owner_action",
	"authority_approval_status",
	"evidence_freshness_confidence",
}

var forbiddenAuthorityKeys = []string{
	"archive_delete_apply_allowed",
	"brokerage_or_account_action_allowed",
	"capital_deployment_allowed",
	"capital_deployment_approved",
	"capital_or_execution_authority",
	"canon_or_portfolio_mutation_allowed",
	"customer_or_external_delivery_allowed",
	"db_mutation",
	"execution_authorized",
	"money_movement_allowed",
	"owner_approval_granted",
	"owner_approval_inferred",
	"paper_order_execution_allowed",
	"paper_or_live_execution_allowed",
	"portfolio_mutation_allowed",
	"sql_write_allowed",
	"trade_execution_allowed",
	"trade_or_execution_approved",
}

type Options struct {
	Root             string
	AssemblerDir     string
	LegacyPacketDir  string
	ParityRollupPath string
	MaxPackets       int
	MaxAgeHours      int
	Now              time.Time
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

type PacketSummary struct {
	Path                    string   `json:"path"`
	Ticker                  string   `json:"ticker,omitempty"`
	Status                  string   `json:"status,omitempty"`
	RequiredSectionCount    int      `json:"required_section_count"`
	PresentRequiredSections int      `json:"present_required_sections"`
	MissingSections         []string `json:"missing_sections"`
	ForbiddenAuthorityCount int      `json:"forbidden_authority_count"`
	GeneratedAtUTC          string   `json:"generated_at_utc,omitempty"`
	ReviewOnly              bool     `json:"review_only"`
}

type Summary struct {
	Checks                          int             `json:"checks"`
	Critical                        int             `json:"critical"`
	Warnings                        int             `json:"warnings"`
	AssemblerPacketCount            int             `json:"assembler_packet_count"`
	LegacyPacketCount               int             `json:"legacy_packet_count"`
	CheckedAssemblerPacketCount     int             `json:"checked_assembler_packet_count"`
	ParityRollupPresent             bool            `json:"parity_rollup_present"`
	ParityRollupStatus              string          `json:"parity_rollup_status,omitempty"`
	ParityProductionAnswerPathCount int             `json:"parity_production_answer_path_count"`
	ParityEvaluatedTickerCount      int             `json:"parity_evaluated_ticker_count"`
	MissingSectionPacketCount       int             `json:"missing_section_packet_count"`
	ForbiddenAuthorityPacketCount   int             `json:"forbidden_authority_packet_count"`
	ReviewOnlyViolationCount        int             `json:"review_only_violation_count"`
	StalePacketCount                int             `json:"stale_packet_count"`
	OptionalPacketFamilyWarnings    int             `json:"optional_packet_family_warnings"`
	PacketSummaries                 []PacketSummary `json:"packet_summaries"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	AssemblerDir      string          `json:"assembler_dir"`
	LegacyPacketDir   string          `json:"legacy_packet_dir"`
	ParityRollupPath  string          `json:"parity_rollup_path"`
	MaxAgeHours       int             `json:"max_age_hours"`
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
	root := defaulted(opts.Root, ".")
	assemblerRel := defaulted(opts.AssemblerDir, "tmp/trade-grade-full-answer")
	legacyRel := defaulted(opts.LegacyPacketDir, "tmp/ticker-answer-packets")
	rollupRel := defaulted(opts.ParityRollupPath, "tmp/full-answer-parity/full-answer-parity-rollup.json")
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 168
	}
	maxPackets := opts.MaxPackets
	if maxPackets <= 0 {
		maxPackets = 0
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

	rollup, rollupPresent := readOptionalJSON(root, rollupRel, add)
	productionCount := 0
	evaluatedCount := 0
	rollupStatus := ""
	if rollupPresent {
		rollupStatus = text(rollup.Payload["status"])
		productionCount = firstInt(
			pathInt(rollup.Payload, "summary.production_answer_path_count"),
			pathInt(rollup.Payload, "summary.wf84_legacy_answer_path_count"),
			pathInt(rollup.Payload, "sql_canon_production_answer_count"),
		)
		evaluatedCount = firstInt(pathInt(rollup.Payload, "summary.evaluated_ticker_count"), pathInt(rollup.Payload, "summary.ticker_count"))
		add(rollupRel, "parity_rollup_status_present", "critical", rollupStatus != "", rollupStatus)
		add(rollupRel, "parity_rollup_status_not_blocked", "critical", !blockedStatus(rollupStatus), rollupStatus)
		add(rollupRel, "parity_rollup_authority_false", "critical", len(authorityViolationsFor(rollup)) == 0, firstN(authorityViolationsFor(rollup), 30))
	} else {
		add(rollupRel, "parity_rollup_optional_present", "warning", false, "missing optional assembler/parity rollup")
	}

	assemblerFiles, assemblerExists := jsonFiles(root, assemblerRel)
	if !assemblerExists {
		severity := "warning"
		if productionCount > 0 {
			severity = "critical"
		}
		add(assemblerRel, "assembler_packet_family_present", severity, false, map[string]int{"production_answer_path_count": productionCount})
	} else {
		add(assemblerRel, "assembler_packet_family_present", "info", true, len(assemblerFiles))
	}
	legacyFiles, legacyExists := jsonFiles(root, legacyRel)
	if !legacyExists {
		severity := "warning"
		if productionCount > 0 && len(assemblerFiles) == 0 {
			severity = "critical"
		}
		add(legacyRel, "legacy_answer_packet_family_present", severity, false, map[string]int{"production_answer_path_count": productionCount})
	} else {
		add(legacyRel, "legacy_answer_packet_family_present", "info", true, len(legacyFiles))
	}

	toCheck := assemblerFiles
	if maxPackets > 0 && len(toCheck) > maxPackets {
		toCheck = toCheck[:maxPackets]
		add(assemblerRel, "assembler_packet_check_limited", "warning", false, map[string]int{"checked": len(toCheck), "total": len(assemblerFiles)})
	}

	packetSummaries := []PacketSummary{}
	missingSectionPackets := 0
	forbiddenAuthorityPackets := 0
	reviewOnlyViolations := 0
	stalePackets := 0
	for _, packetRel := range toCheck {
		packet := readRequiredJSON(root, packetRel, add)
		if !packet.OK {
			continue
		}
		summary := validatePacket(packet, maxAgeHours, now, add)
		if len(summary.MissingSections) > 0 {
			missingSectionPackets++
		}
		if summary.ForbiddenAuthorityCount > 0 {
			forbiddenAuthorityPackets++
		}
		if !summary.ReviewOnly {
			reviewOnlyViolations++
		}
		if isStale(summary.GeneratedAtUTC, maxAgeHours, now) {
			stalePackets++
		}
		packetSummaries = append(packetSummaries, summary)
	}

	sort.Slice(packetSummaries, func(i, j int) bool { return packetSummaries[i].Path < packetSummaries[j].Path })
	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		AssemblerDir:      filepath.ToSlash(assemblerRel),
		LegacyPacketDir:   filepath.ToSlash(legacyRel),
		ParityRollupPath:  filepath.ToSlash(rollupRel),
		MaxAgeHours:       maxAgeHours,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:                          base.Checks,
			Critical:                        base.Critical,
			Warnings:                        base.Warnings,
			AssemblerPacketCount:            len(assemblerFiles),
			LegacyPacketCount:               len(legacyFiles),
			CheckedAssemblerPacketCount:     len(toCheck),
			ParityRollupPresent:             rollupPresent,
			ParityRollupStatus:              rollupStatus,
			ParityProductionAnswerPathCount: productionCount,
			ParityEvaluatedTickerCount:      evaluatedCount,
			MissingSectionPacketCount:       missingSectionPackets,
			ForbiddenAuthorityPacketCount:   forbiddenAuthorityPackets,
			ReviewOnlyViolationCount:        reviewOnlyViolations,
			StalePacketCount:                stalePackets,
			OptionalPacketFamilyWarnings:    optionalWarnings(findings),
			PacketSummaries:                 packetSummaries,
		},
		NextSafeAction: "Use as read-only WF85 answer completeness proof. Repair missing sections or authority flags in the assembler/source producers; do not infer approval or mutate finance canon from this validator.",
	}
}

func validatePacket(packet loadedJSON, maxAgeHours int, now time.Time, add func(string, string, string, bool, any)) PacketSummary {
	payload := packet.Payload
	status := text(payload["status"])
	ticker := text(payload["ticker"])
	add(packet.Path, "packet_status_present", "critical", status != "", status)
	add(packet.Path, "packet_status_not_blocked", "critical", !blockedStatus(status), status)
	reviewOnly := truthy(payload["review_only"])
	add(packet.Path, "review_only_true", "critical", reviewOnly, payload["review_only"])
	generated := firstNonEmpty(text(payload["generated_at_utc"]), text(payload["generated_at"]))
	if generated == "" {
		add(packet.Path, "generated_at_present", "warning", false, "")
	} else if parsed, err := parseTime(generated); err != nil {
		add(packet.Path, "generated_at_parse", "warning", false, generated)
	} else {
		stale := now.Sub(parsed) > time.Duration(maxAgeHours)*time.Hour
		add(packet.Path, "freshness_within_max_age", "warning", !stale, map[string]any{"generated_at_utc": generated, "max_age_hours": maxAgeHours})
	}

	required := requiredSections(payload)
	sections := asMap(payload["sections"])
	missing := []string{}
	for _, section := range required {
		if _, ok := sections[section]; !ok {
			missing = append(missing, section)
		}
	}
	for _, section := range stringArray(pathValue(payload, "summary.missing_sections")) {
		if !containsString(missing, section) {
			missing = append(missing, section)
		}
	}
	sort.Strings(missing)
	add(packet.Path, "required_sections_present", "critical", len(missing) == 0, missing)

	violations := authorityViolationsFor(packet)
	add(packet.Path, "forbidden_authority_flags_false", "critical", len(violations) == 0, firstN(violations, 30))
	return PacketSummary{
		Path:                    packet.Path,
		Ticker:                  ticker,
		Status:                  status,
		RequiredSectionCount:    len(required),
		PresentRequiredSections: len(required) - len(missing),
		MissingSections:         missing,
		ForbiddenAuthorityCount: len(violations),
		GeneratedAtUTC:          generated,
		ReviewOnly:              reviewOnly,
	}
}

func requiredSections(payload map[string]any) []string {
	values := stringArray(pathValue(payload, "canonical_full_answer_contract.required_sections"))
	if len(values) == 0 {
		return append([]string{}, defaultRequiredSections...)
	}
	sort.Strings(values)
	return values
}

func jsonFiles(root, relDir string) ([]string, bool) {
	dir := resolve(root, relDir)
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, false
	}
	out := []string{}
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(strings.ToLower(entry.Name()), ".json") {
			continue
		}
		lower := strings.ToLower(entry.Name())
		if strings.Contains(lower, "rollup") || strings.Contains(lower, "summary") || strings.Contains(lower, "delta") {
			continue
		}
		out = append(out, filepath.ToSlash(filepath.Join(relDir, entry.Name())))
	}
	sort.Strings(out)
	return out, true
}

func readOptionalJSON(root, relPath string, add func(string, string, string, bool, any)) (loadedJSON, bool) {
	path := resolve(root, relPath)
	bytes, err := os.ReadFile(path)
	if err != nil {
		return loadedJSON{Path: relPath, Payload: map[string]any{}}, false
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}}, true
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{Path: relPath, Payload: payload, OK: true}, true
}

func readRequiredJSON(root, relPath string, add func(string, string, string, bool, any)) loadedJSON {
	path := resolve(root, relPath)
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(relPath, "json_exists", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}}
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(relPath, "json_parse", "critical", false, err.Error())
		return loadedJSON{Path: relPath, Payload: map[string]any{}}
	}
	add(relPath, "json_parse", "info", true, "")
	return loadedJSON{Path: relPath, Payload: payload, OK: true}
}

func authorityViolationsFor(packet loadedJSON) []string {
	out := []string{}
	walk(packet.Payload, "", func(path string, value any) {
		lower := strings.ToLower(path)
		for _, term := range forbiddenAuthorityKeys {
			if strings.Contains(lower, term) && truthy(value) {
				out = append(out, packet.Path+":"+path+"="+text(value))
				break
			}
		}
	})
	sort.Strings(out)
	return out
}

func walk(value any, path string, visit func(string, any)) {
	switch typed := value.(type) {
	case map[string]any:
		for key, child := range typed {
			next := key
			if path != "" {
				next = path + "." + key
			}
			walk(child, next, visit)
		}
	case []any:
		for index, child := range typed {
			walk(child, fmt.Sprintf("%s[%d]", path, index), visit)
		}
	default:
		visit(path, typed)
	}
}

func parseTime(value string) (time.Time, error) {
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
		if parsed, err := time.Parse(layout, strings.TrimSpace(value)); err == nil {
			return parsed.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported timestamp: %s", value)
}

func isStale(generated string, maxAgeHours int, now time.Time) bool {
	if generated == "" {
		return false
	}
	parsed, err := parseTime(generated)
	if err != nil {
		return false
	}
	return now.Sub(parsed) > time.Duration(maxAgeHours)*time.Hour
}

func optionalWarnings(findings []Finding) int {
	count := 0
	for _, finding := range findings {
		if !finding.OK && finding.Severity == "warning" && strings.Contains(finding.Check, "packet_family") {
			count++
		}
		if !finding.OK && finding.Severity == "warning" && strings.Contains(finding.Check, "rollup_optional") {
			count++
		}
	}
	return count
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

func asMap(value any) map[string]any {
	if out, ok := value.(map[string]any); ok {
		return out
	}
	return map[string]any{}
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

func pathInt(payload map[string]any, dotted string) int {
	return intValue(pathValue(payload, dotted))
}

func firstInt(values ...int) int {
	for _, value := range values {
		if value != 0 {
			return value
		}
	}
	return 0
}

func stringArray(value any) []string {
	raw, ok := value.([]any)
	if !ok {
		if stringsValue, ok := value.([]string); ok {
			out := append([]string{}, stringsValue...)
			sort.Strings(out)
			return out
		}
		return nil
	}
	out := []string{}
	for _, item := range raw {
		itemText := text(item)
		if itemText != "" {
			out = append(out, itemText)
		}
	}
	sort.Strings(out)
	return out
}

func containsString(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}

func firstN(values []string, n int) []string {
	if len(values) <= n {
		return values
	}
	return values[:n]
}

func blockedStatus(value string) bool {
	lower := strings.ToLower(strings.TrimSpace(value))
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
		case "1", "true", "yes", "allowed", "approved", "ok":
			return true
		}
	}
	return false
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
		fmt.Sscanf(strings.TrimSpace(typed), "%d", &out)
		return out
	default:
		return 0
	}
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}
