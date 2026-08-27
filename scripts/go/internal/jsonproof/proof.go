package jsonproof

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

const SchemaVersion = "go_json_proof_contract_lint.v1"

var defaultPackets = []string{
	"tmp/finance-sql-canon-access-validation.json",
	"tmp/sql-canon-front-door-readiness-packet.json",
	"tmp/sql-canon-consumer-inventory.json",
	"tmp/sql-canon-consumer-registry-guard.json",
	"tmp/sql-canon-migration-completion-runner.json",
	"tmp/sql-canon-owner-decision-packet.json",
	"tmp/sql-canon-answer-path-ab-harness.json",
	"tmp/sql-canon-wf78-routing-parity.json",
	"tmp/reference-levels-sql-native-source-family-proof.json",
}

var forbiddenFlagTerms = []string{
	"answer_path_sql_first_promotion_allowed",
	"archive_delete_apply_allowed",
	"archive_delete_allowed",
	"archive_move_or_delete_performed",
	"archive_moves_performed",
	"brokerage_or_account_action_allowed",
	"capital_deployment_allowed",
	"capital_or_execution_authority",
	"canon_or_portfolio_mutation",
	"consumer_behavior_change_allowed",
	"consumer_file_mutation_allowed",
	"consumer_file_mutation_performed",
	"consumer_files_modified",
	"customer_or_external_delivery",
	"db_mutation",
	"db_row_mutation_performed",
	"delete_performed",
	"duplicate_surface_cleanup_apply_allowed",
	"fallback_retirement_allowed",
	"front_door_promotion_allowed",
	"money_movement_allowed",
	"owner_approval_inferred",
	"paper_or_live_execution_allowed",
	"portfolio_or_canon_mutation_allowed",
	"portfolio_or_canon_note_mutation_performed",
	"python_fallback_retirement_allowed",
	"registry_writer_allowed_now",
	"schema_mutation",
	"source_feeder_retirement_allowed",
	"sql_mutation_performed",
	"sql_write_allowed",
	"sql_writes_performed",
	"ticker_import_performed",
}

type Options struct {
	Root        string
	Packets     []string
	MaxAgeHours int
	Now         time.Time
}

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   string `json:"detail,omitempty"`
}

func (f Finding) IsOK() bool {
	return f.OK
}

func (f Finding) FindingSeverity() string {
	return f.Severity
}

type Summary struct {
	Checks       int `json:"checks"`
	Critical     int `json:"critical"`
	Warnings     int `json:"warnings"`
	Packets      int `json:"packets"`
	StalePackets int `json:"stale_packets"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	MaxAgeHours       int             `json:"max_age_hours"`
	CheckedPackets    []string        `json:"checked_packets"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

func DefaultPackets() []string {
	return append([]string{}, defaultPackets...)
}

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	now := opts.Now
	if now.IsZero() {
		now = time.Now().UTC()
	}
	maxAgeHours := opts.MaxAgeHours
	if maxAgeHours <= 0 {
		maxAgeHours = 96
	}
	packets := opts.Packets
	if len(packets) == 0 {
		packets = DefaultPackets()
	}
	sort.Strings(packets)

	findings := []Finding{}
	stalePackets := 0
	add := func(path, check, severity string, ok bool, detail string) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	for _, packet := range packets {
		rel := filepath.ToSlash(packet)
		path := packet
		if !filepath.IsAbs(path) {
			path = filepath.Join(root, filepath.FromSlash(packet))
		}
		bytes, err := os.ReadFile(path)
		if err != nil {
			add(rel, "packet_exists", "critical", false, err.Error())
			continue
		}
		add(rel, "packet_exists", "info", true, "")
		var payload map[string]any
		if err := json.Unmarshal(bytes, &payload); err != nil {
			add(rel, "json_parse", "critical", false, err.Error())
			continue
		}
		add(rel, "json_parse", "info", true, "")
		status := text(payload["status"])
		add(rel, "status_present", "critical", status != "", status)
		add(rel, "status_not_blocked", "critical", !blockedStatus(status), status)
		generated := text(payload["generated_at_utc"])
		if generated == "" {
			generated = text(payload["generated_at"])
		}
		if generated == "" {
			add(rel, "generated_at_present", "critical", false, "")
		} else if timestamp, err := time.Parse(time.RFC3339, generated); err != nil {
			add(rel, "generated_at_parse", "critical", false, err.Error())
		} else {
			add(rel, "generated_at_parse", "info", true, generated)
			age := now.Sub(timestamp.UTC())
			if age < -5*time.Minute {
				add(rel, "generated_at_not_future", "critical", false, fmt.Sprintf("future_by=%s", -age))
			} else {
				add(rel, "generated_at_not_future", "info", true, "")
			}
			fresh := age <= time.Duration(maxAgeHours)*time.Hour
			if !fresh {
				stalePackets++
			}
			add(rel, "freshness_within_max_age", "warning", fresh, fmt.Sprintf("age_hours=%.1f max_age_hours=%d", age.Hours(), maxAgeHours))
		}
		checkValidation(rel, payload, add)
		checkAuthority(rel, payload, add)
	}

	base := reporting.SummarizeFindings(findings)
	status := reporting.StatusFromCounts(base.Critical, base.Warnings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            status,
		Root:              filepath.ToSlash(root),
		MaxAgeHours:       maxAgeHours,
		CheckedPackets:    packets,
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Findings:          findings,
		Summary: Summary{
			Checks:       base.Checks,
			Critical:     base.Critical,
			Warnings:     base.Warnings,
			Packets:      len(packets),
			StalePackets: stalePackets,
		},
		NextSafeAction: "Use as an advisory read-only proof packet contract lint. Promote to blocking only after repeated clean advisory runs.",
	}
}

func checkValidation(rel string, payload map[string]any, add func(string, string, string, bool, string)) {
	raw, ok := payload["validation"]
	if !ok {
		add(rel, "validation_envelope_present", "warning", false, "missing validation object")
		return
	}
	validation, ok := raw.(map[string]any)
	if !ok {
		add(rel, "validation_envelope_present", "critical", false, "validation is not an object")
		return
	}
	add(rel, "validation_envelope_present", "info", true, "")
	status := strings.ToLower(text(validation["status"]))
	add(rel, "validation_status_not_blocked", "critical", !blockedStatus(status), status)
	errors := arrayLen(validation["errors"])
	warnings := arrayLen(validation["warnings"])
	add(rel, "validation_errors_empty", "critical", errors == 0, fmt.Sprintf("errors=%d", errors))
	add(rel, "validation_warnings_empty", "warning", warnings == 0, fmt.Sprintf("warnings=%d", warnings))
}

func checkAuthority(rel string, payload map[string]any, add func(string, string, string, bool, string)) {
	raw, key := payload["authority_boundary"], "authority_boundary"
	if raw == nil {
		raw, key = payload["authority"], "authority"
	}
	if raw == nil {
		add(rel, "authority_boundary_present", "warning", false, "missing authority_boundary/authority")
		return
	}
	authority, ok := raw.(map[string]any)
	if !ok {
		add(rel, "authority_boundary_present", "critical", false, key+" is not an object")
		return
	}
	add(rel, "authority_boundary_present", "info", true, key)
	violations := []string{}
	for name, value := range authority {
		lower := strings.ToLower(name)
		if !forbiddenFlagName(lower) {
			continue
		}
		if truthy(value) {
			violations = append(violations, name+"="+text(value))
		}
	}
	sort.Strings(violations)
	add(rel, "forbidden_authority_flags_false", "critical", len(violations) == 0, strings.Join(violations, "; "))
}

func forbiddenFlagName(name string) bool {
	for _, term := range forbiddenFlagTerms {
		if strings.Contains(name, term) {
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
		default:
			return false
		}
	default:
		return false
	}
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

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}
