package paperguard

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

const SchemaVersion = "go_paper_trading_guard_preflight.v1"

type Options struct {
	Root            string
	GuardPaths      []string
	KillSwitchPaths []string
	RequireReady    bool
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

type ArtifactStatus struct {
	Path             string   `json:"path"`
	Exists           bool     `json:"exists"`
	Parseable        bool     `json:"parseable"`
	Status           string   `json:"status,omitempty"`
	GeneratedAtUTC   string   `json:"generated_at_utc,omitempty"`
	ReadyForPaper    *bool    `json:"ready_for_paper_submit_cancel,omitempty"`
	UnsafeTrueFlags  []string `json:"unsafe_true_flags,omitempty"`
	LiveEndpointHits []string `json:"live_endpoint_hits,omitempty"`
}

type KillSwitchStatus struct {
	Path         string   `json:"path"`
	Exists       bool     `json:"exists"`
	Parseable    bool     `json:"parseable"`
	ExpiresAtUTC string   `json:"expires_at_utc,omitempty"`
	Fresh        *bool    `json:"fresh,omitempty"`
	PaperOnly    *bool    `json:"paper_only,omitempty"`
	Endpoint     string   `json:"endpoint,omitempty"`
	LiveFlags    []string `json:"live_flags,omitempty"`
}

type Summary struct {
	Checks               int  `json:"checks"`
	Critical             int  `json:"critical"`
	Warnings             int  `json:"warnings"`
	GuardArtifactCount   int  `json:"guard_artifact_count"`
	GuardArtifactMissing int  `json:"guard_artifact_missing"`
	KillSwitchCount      int  `json:"kill_switch_count"`
	KillSwitchMissing    int  `json:"kill_switch_missing"`
	FreshKillSwitchCount int  `json:"fresh_kill_switch_count"`
	UnsafeTrueFlagCount  int  `json:"unsafe_true_flag_count"`
	LiveEndpointHitCount int  `json:"live_endpoint_hit_count"`
	ReadyArtifactCount   int  `json:"ready_artifact_count"`
	BlockedArtifactCount int  `json:"blocked_artifact_count"`
	RequireReady         bool `json:"require_ready"`
}

type Report struct {
	SchemaVersion     string             `json:"schema_version"`
	GeneratedAtUTC    string             `json:"generated_at_utc"`
	Status            string             `json:"status"`
	Root              string             `json:"root"`
	AuthorityBoundary map[string]bool    `json:"authority_boundary"`
	GuardArtifacts    []ArtifactStatus   `json:"guard_artifacts"`
	KillSwitches      []KillSwitchStatus `json:"kill_switches"`
	Findings          []Finding          `json:"findings"`
	Summary           Summary            `json:"summary"`
	NextSafeAction    string             `json:"next_safe_action"`
}

var defaultGuardPaths = []string{
	"tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
	"tmp/alpaca-paper-readiness/paper-execution-guard-report.json",
	"tmp/paper-autotrader/guard-readiness.json",
}

var defaultKillSwitchPaths = []string{
	"tmp/alpaca-paper-readiness/kill-switch.json",
	"tmp/alpaca-paper-readiness/kill-switch-fresh.json",
}

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	guardPaths := append([]string{}, opts.GuardPaths...)
	if len(guardPaths) == 0 {
		guardPaths = append(guardPaths, defaultGuardPaths...)
	}
	killPaths := append([]string{}, opts.KillSwitchPaths...)
	if len(killPaths) == 0 {
		killPaths = append(killPaths, defaultKillSwitchPaths...)
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
	readySeverity := "warning"
	if opts.RequireReady {
		readySeverity = "critical"
	}

	guardStatuses := []ArtifactStatus{}
	guardMissing := 0
	unsafeTrueFlags := 0
	liveEndpointHits := 0
	readyArtifacts := 0
	blockedArtifacts := 0

	for _, rel := range guardPaths {
		payload, ok := readJSON(root, rel, readySeverity, add)
		status := ArtifactStatus{Path: filepath.ToSlash(rel), Exists: ok, Parseable: ok}
		if !ok {
			guardMissing++
			guardStatuses = append(guardStatuses, status)
			continue
		}
		status.Status = text(payload["status"])
		status.GeneratedAtUTC = text(payload["generated_at_utc"])
		if ready, present := boolPresent(payload["ready_for_paper_submit_cancel"]); present {
			status.ReadyForPaper = &ready
			if ready {
				readyArtifacts++
			}
			add(rel, "ready_for_paper_submit_cancel_true_when_present", readySeverity, ready || !opts.RequireReady, ready)
		}
		if blockedStatus(status.Status) {
			blockedArtifacts++
			add(rel, "guard_status_not_blocked", readySeverity, !opts.RequireReady, status.Status)
		} else {
			add(rel, "guard_status_not_blocked", "info", true, status.Status)
		}
		status.UnsafeTrueFlags = unsafeTrueAuthorityFlags(payload)
		status.LiveEndpointHits = liveEndpointValues(payload)
		unsafeTrueFlags += len(status.UnsafeTrueFlags)
		liveEndpointHits += len(status.LiveEndpointHits)
		add(rel, "no_live_or_owner_authority_true_flags", "critical", len(status.UnsafeTrueFlags) == 0, status.UnsafeTrueFlags)
		add(rel, "no_live_endpoint_selected", "critical", len(status.LiveEndpointHits) == 0, status.LiveEndpointHits)
		guardStatuses = append(guardStatuses, status)
	}

	killStatuses := []KillSwitchStatus{}
	killMissing := 0
	freshKillSwitches := 0
	for _, rel := range killPaths {
		payload, ok := readJSON(root, rel, readySeverity, add)
		status := KillSwitchStatus{Path: filepath.ToSlash(rel), Exists: ok, Parseable: ok}
		if !ok {
			killMissing++
			killStatuses = append(killStatuses, status)
			continue
		}
		status.ExpiresAtUTC = text(payload["expires_at_utc"])
		status.Endpoint = text(payload["endpoint"])
		if paperOnly, present := boolPresent(payload["paper_only"]); present {
			status.PaperOnly = &paperOnly
			add(rel, "kill_switch_paper_only_when_present", "critical", paperOnly, paperOnly)
		}
		status.LiveFlags = unsafeTrueAuthorityFlags(payload)
		unsafeTrueFlags += len(status.LiveFlags)
		add(rel, "kill_switch_no_live_or_owner_authority_true_flags", "critical", len(status.LiveFlags) == 0, status.LiveFlags)
		endpointHits := liveEndpointValues(payload)
		liveEndpointHits += len(endpointHits)
		add(rel, "kill_switch_no_live_endpoint_selected", "critical", len(endpointHits) == 0, endpointHits)
		if status.ExpiresAtUTC == "" {
			add(rel, "kill_switch_expires_at_present", readySeverity, false, "expires_at_utc missing")
		} else if expires, err := parseTime(status.ExpiresAtUTC); err != nil {
			add(rel, "kill_switch_expires_at_parse", readySeverity, false, err.Error())
		} else {
			fresh := expires.After(now)
			status.Fresh = &fresh
			if fresh {
				freshKillSwitches++
			}
			add(rel, "kill_switch_fresh", readySeverity, fresh || !opts.RequireReady, map[string]any{"expires_at_utc": status.ExpiresAtUTC, "now_utc": now.Format(time.RFC3339)})
		}
		killStatuses = append(killStatuses, status)
	}
	if freshKillSwitches == 0 {
		add("tmp/alpaca-paper-readiness/kill-switch.json", "fresh_kill_switch_present", readySeverity, !opts.RequireReady, "no fresh kill switch found")
	} else {
		add("tmp/alpaca-paper-readiness/kill-switch.json", "fresh_kill_switch_present", "info", true, freshKillSwitches)
	}

	sort.Slice(guardStatuses, func(i, j int) bool { return guardStatuses[i].Path < guardStatuses[j].Path })
	sort.Slice(killStatuses, func(i, j int) bool { return killStatuses[i].Path < killStatuses[j].Path })
	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		GuardArtifacts:    guardStatuses,
		KillSwitches:      killStatuses,
		Findings:          findings,
		Summary: Summary{
			Checks:               base.Checks,
			Critical:             base.Critical,
			Warnings:             base.Warnings,
			GuardArtifactCount:   len(guardPaths),
			GuardArtifactMissing: guardMissing,
			KillSwitchCount:      len(killPaths),
			KillSwitchMissing:    killMissing,
			FreshKillSwitchCount: freshKillSwitches,
			UnsafeTrueFlagCount:  unsafeTrueFlags,
			LiveEndpointHitCount: liveEndpointHits,
			ReadyArtifactCount:   readyArtifacts,
			BlockedArtifactCount: blockedArtifacts,
			RequireReady:         opts.RequireReady,
		},
		NextSafeAction: "Use as read-only WF67/WF86 guard preflight. This validator never submits, cancels, sells, mutates brokerage/account state, refreshes credentials, or infers owner approval.",
	}
}

func readJSON(root, rel, missingSeverity string, add func(string, string, string, bool, any)) (map[string]any, bool) {
	path := resolve(root, rel)
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(rel, "artifact_exists", missingSeverity, false, err.Error())
		return nil, false
	}
	add(rel, "artifact_exists", "info", true, "")
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		add(rel, "artifact_parse", missingSeverity, false, err.Error())
		return nil, false
	}
	add(rel, "artifact_parse", "info", true, "")
	return payload, true
}

func unsafeTrueAuthorityFlags(value any) []string {
	out := []string{}
	var walk func(path string, current any)
	walk = func(path string, current any) {
		switch typed := current.(type) {
		case map[string]any:
			for key, child := range typed {
				childPath := key
				if path != "" {
					childPath = path + "." + key
				}
				if truthy(child) && unsafeTrueKey(key) {
					out = append(out, childPath)
				}
				walk(childPath, child)
			}
		case []any:
			for index, child := range typed {
				walk(fmt.Sprintf("%s[%d]", path, index), child)
			}
		}
	}
	walk("", value)
	sort.Strings(out)
	return out
}

func unsafeTrueKey(key string) bool {
	lower := strings.ToLower(strings.TrimSpace(key))
	switch lower {
	case "live_trading_allowed", "live_trade_allowed", "live_submit_allowed", "live_cancel_enabled",
		"live_endpoint_allowed", "live_endpoint_detected", "live_order_allowed",
		"money_movement_allowed", "account_settings_mutation_allowed",
		"brokerage_or_account_action_allowed", "paper_or_live_execution_allowed",
		"owner_approval_inferred":
		return true
	default:
		return false
	}
}

func liveEndpointValues(value any) []string {
	out := []string{}
	var walk func(path string, current any)
	walk = func(path string, current any) {
		switch typed := current.(type) {
		case map[string]any:
			for key, child := range typed {
				childPath := key
				if path != "" {
					childPath = path + "." + key
				}
				walk(childPath, child)
			}
		case []any:
			for index, child := range typed {
				walk(fmt.Sprintf("%s[%d]", path, index), child)
			}
		case string:
			lowerPath := strings.ToLower(path)
			lowerValue := strings.ToLower(typed)
			if strings.Contains(lowerPath, "endpoint") &&
				!strings.Contains(lowerPath, "forbidden") &&
				strings.Contains(lowerValue, "https://api.alpaca.markets") {
				out = append(out, path+"="+typed)
			}
		}
	}
	walk("", value)
	sort.Strings(out)
	return out
}

func boolPresent(value any) (bool, bool) {
	typed, ok := value.(bool)
	return typed, ok
}

func truthy(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		switch strings.ToLower(strings.TrimSpace(typed)) {
		case "true", "yes", "allowed", "approved", "ok":
			return true
		}
	case float64:
		return typed != 0
	case int:
		return typed != 0
	}
	return false
}

func blockedStatus(status string) bool {
	lower := strings.ToLower(strings.TrimSpace(status))
	return strings.Contains(lower, "blocked") || strings.Contains(lower, "error") || strings.Contains(lower, "failed")
}

func parseTime(value string) (time.Time, error) {
	for _, layout := range []string{time.RFC3339Nano, time.RFC3339, "2006-01-02"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported timestamp: %s", value)
}

func text(value any) string {
	if value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
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
