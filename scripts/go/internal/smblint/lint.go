package smblint

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   string `json:"detail,omitempty"`
}

type Report struct {
	SchemaVersion  string    `json:"schema_version"`
	GeneratedAtUTC string    `json:"generated_at_utc"`
	Status         string    `json:"status"`
	Root           string    `json:"root"`
	CheckedFiles   []string  `json:"checked_files"`
	Findings       []Finding `json:"findings"`
	Summary        Summary   `json:"summary"`
	Boundary       string    `json:"boundary"`
}

type Summary struct {
	Checks   int `json:"checks"`
	Critical int `json:"critical"`
	Warnings int `json:"warnings"`
}

var defaultFiles = []string{
	"tmp/generic-service-run-contract.json",
	"tmp/wf75-smb-workflow-scenario-library.json",
	"tmp/wf75-smb-pivot-pm-decision-packet.json",
	"tmp/wf75-smb-customer-preview.json",
	"tmp/wf75-smb-pilot-decision-packet.json",
	"tmp/wf75-smb-automation-blueprints.json",
}

var forbiddenTruthyKeys = map[string]bool{
	"real_customer_data_allowed":                            true,
	"customer_identity_allowed":                             true,
	"customer_data_retention_allowed":                       true,
	"customer_data_import_allowed":                          true,
	"customer_outreach_allowed":                             true,
	"message_sending_allowed":                               true,
	"outbound_message_allowed":                              true,
	"external_delivery_allowed":                             true,
	"public_launch_allowed":                                 true,
	"public_launch_ready":                                   true,
	"phone_system_or_crm_credential_access_allowed":         true,
	"payment_pos_payroll_account_access_allowed":            true,
	"credential_access_allowed":                             true,
	"implementation_in_customer_systems_allowed":            true,
	"customer_system_writeback_allowed":                     true,
	"guaranteed_roi_or_revenue_claim_allowed":               true,
	"legal_tax_compliance_security_readiness_claim_allowed": true,
	"legal_compliance_security_readiness_claim_allowed":     true,
	"owner_approval_inferred":                               true,
	"owner_approval_granted":                                true,
}

var forbiddenPositivePatterns = []struct {
	name string
	re   *regexp.Regexp
}{
	{"customer_data_allowed_language", regexp.MustCompile(`(?i)\b(real\s+)?customer\s+data\s+(is\s+)?(allowed|approved|ready|enabled)\b`)},
	{"credential_access_language", regexp.MustCompile(`(?i)\b(credential|api\s+key|token|password|crm\s+login|phone\s+system)\s+access\s+(is\s+)?(allowed|approved|ready|enabled|required)\b`)},
	{"outbound_message_language", regexp.MustCompile(`(?i)\b(will|can|may|approved\s+to|allowed\s+to|ready\s+to|automatically)\s+(send|deliver)\s+(calls?|texts?|sms|emails?|outbound\s+messages?|review\s+requests?)\b`)},
	{"customer_writeback_language", regexp.MustCompile(`(?i)\b(write\s*back|writeback|implement|install|activate)\s+(in|into|to|inside)\s+(the\s+)?customer\s+(system|crm|account|environment)\b`)},
	{"guaranteed_roi_language", regexp.MustCompile(`(?i)\b(guaranteed|guarantees)\s+(roi|revenue|sales|leads?|payback|return)\b`)},
	{"public_launch_ready_language", regexp.MustCompile(`(?i)\b(public\s+launch|customer\s+launch|external\s+delivery)\s+(is\s+)?(ready|approved|allowed|enabled)\b`)},
	{"readiness_claim_language", regexp.MustCompile(`(?i)\b(legal|compliance|security)\s+(readiness|ready|approved|cleared|certified)\b`)},
	{"owner_approval_inference_language", regexp.MustCompile(`(?i)\b(owner|randall)\s+approval\s+(is\s+)?(inferred|assumed|granted|automatic)\b`)},
}

var negativeContext = regexp.MustCompile(`(?i)\b(no|not|never|without|blocked|forbidden|prohibited|disallowed|not\s+in\s+scope|before\s+a\s+future|requires\s+future|human\s+approval|manual\s+review)\b`)

func Run(root string, files []string) Report {
	if len(files) == 0 {
		files = defaultFiles
	}
	var findings []Finding
	var checked []string
	add := func(path, check, severity string, ok bool, detail string) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	for _, rel := range files {
		path := filepath.Join(root, filepath.FromSlash(rel))
		bytes, err := os.ReadFile(path)
		if err != nil {
			add(rel, "exists", "critical", false, err.Error())
			continue
		}
		checked = append(checked, filepath.ToSlash(rel))
		add(rel, "exists", "info", true, "")
		var doc any
		if err := json.Unmarshal(bytes, &doc); err != nil {
			add(rel, "json_valid", "critical", false, err.Error())
			continue
		}
		add(rel, "json_valid", "info", true, "")
		scanAuthorityFlags(rel, doc, add)
		scanPositiveLanguage(rel, string(bytes), add)
	}

	critical, warnings := 0, 0
	for _, finding := range findings {
		if finding.OK {
			continue
		}
		if finding.Severity == "critical" {
			critical++
		} else {
			warnings++
		}
	}
	status := "ok"
	if warnings > 0 {
		status = "warning"
	}
	if critical > 0 {
		status = "blocked"
	}
	return Report{
		SchemaVersion:  "wf75_smb_boundary_lint.v1",
		GeneratedAtUTC: time.Now().UTC().Format(time.RFC3339),
		Status:         status,
		Root:           filepath.ToSlash(root),
		CheckedFiles:   checked,
		Findings:       findings,
		Summary:        Summary{Checks: len(findings), Critical: critical, Warnings: warnings},
		Boundary:       "Read-only Go validator. No artifact generation, customer action, SQL/canon mutation, portfolio mutation, paper/live/account action, external delivery, or owner approval inference.",
	}
}

func scanAuthorityFlags(path string, value any, add func(string, string, string, bool, string)) {
	var walk func(any, string)
	walk = func(v any, prefix string) {
		switch node := v.(type) {
		case map[string]any:
			for key, child := range node {
				next := key
				if prefix != "" {
					next = prefix + "." + key
				}
				if forbiddenTruthyKeys[key] && isTruthy(child) {
					add(path, "forbidden_truthy_authority_flag", "critical", false, fmt.Sprintf("%s=%v", next, child))
				}
				walk(child, next)
			}
		case []any:
			for i, child := range node {
				walk(child, fmt.Sprintf("%s[%d]", prefix, i))
			}
		}
	}
	walk(value, "")
}

func isTruthy(value any) bool {
	switch v := value.(type) {
	case bool:
		return v
	case float64:
		return v != 0
	case string:
		text := strings.TrimSpace(strings.ToLower(v))
		return text == "true" || text == "allowed" || text == "approved" || text == "ready" || text == "enabled"
	default:
		return false
	}
}

func scanPositiveLanguage(path, raw string, add func(string, string, string, bool, string)) {
	lines := strings.Split(raw, "\n")
	for lineNo, line := range lines {
		for _, pattern := range forbiddenPositivePatterns {
			loc := pattern.re.FindStringIndex(line)
			if loc == nil {
				continue
			}
			window := contextWindow(line, loc[0], loc[1])
			if negativeContext.MatchString(window) {
				continue
			}
			add(path, pattern.name, "critical", false, fmt.Sprintf("line=%d text=%s", lineNo+1, strings.TrimSpace(window)))
		}
	}
}

func contextWindow(line string, start, end int) string {
	left := start - 80
	if left < 0 {
		left = 0
	}
	right := end + 80
	if right > len(line) {
		right = len(line)
	}
	return line[left:right]
}
