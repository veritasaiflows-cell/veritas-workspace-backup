package smblint

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
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

var defaultJSONFiles = []string{
	"tmp/generic-service-run-contract.json",
	"tmp/wf75-smb-workflow-scenario-library.json",
	"tmp/wf75-smb-pivot-pm-decision-packet.json",
	"tmp/wf75-smb-customer-preview.json",
	"tmp/wf75-smb-pilot-decision-packet.json",
	"tmp/wf75-smb-automation-blueprints.json",
}

const customerSurfaceDir = "10. Deliverables/AI Drop-Service OS"

var customerSurfaceCategories = []struct {
	name      string
	nameParts []string
}{
	{"customer_one_pager", []string{"ai workflow clarity sprint - customer one-pager -"}},
	{"ready_to_send_messages", []string{"ai workflow clarity sprint - batch", "ready-to-send messages -"}},
	{"pilot_approval_card", []string{"ai workflow clarity sprint - consolidated pilot approval card -"}},
	{"outreach_tracker", []string{"ai workflow clarity sprint - outreach tracker -"}},
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
	"guaranteed_revenue_or_roi_claim_allowed":               true,
	"legal_tax_compliance_security_readiness_claim_allowed": true,
	"legal_compliance_security_readiness_claim_allowed":     true,
	"personalized_regulated_advice_allowed":                 true,
	"finance_canon_source_of_truth":                         true,
	"finance_canon_mutation_allowed":                        true,
	"finance_canon_write_allowed":                           true,
	"finance_portfolio_or_canon_mutation_allowed":           true,
	"canon_mutation_allowed":                                true,
	"portfolio_mutation_allowed":                            true,
	"portfolio_or_canon_mutation_allowed":                   true,
	"portfolio_mutation_authority":                          true,
	"capital_deployment_allowed":                            true,
	"capital_deployment_approved":                           true,
	"paper_trading_allowed":                                 true,
	"paper_execution_allowed":                               true,
	"paper_order_execution_allowed":                         true,
	"paper_or_live_execution_allowed":                       true,
	"live_trading_allowed":                                  true,
	"live_execution_allowed":                                true,
	"live_trade_or_account_action_allowed":                  true,
	"trade_execution_allowed":                               true,
	"trade_or_execution_approved":                           true,
	"trade_or_account_authority":                            true,
	"trading_account_or_paper_execution_allowed":            true,
	"brokerage_or_account_connection_allowed":               true,
	"brokerage_write_allowed":                               true,
	"account_action_allowed":                                true,
	"money_movement_allowed":                                true,
	"execution_authority":                                   true,
	"execution_authority_granted":                           true,
	"owner_approval_authority":                              true,
	"owner_approval_inferred":                               true,
	"owner_approval_granted":                                true,
}

var forbiddenPositivePatterns = []struct {
	name string
	re   *regexp.Regexp
}{
	{"customer_data_allowed_language", regexp.MustCompile(`(?i)\b(real\s+)?customer\s+data\s+(is\s+)?(allowed|approved|ready|enabled)\b`)},
	{"credential_access_language", regexp.MustCompile(`(?i)\b(credential|api\s+key|token|password|crm\s+login|phone\s+system)\s+access\s+(is\s+)?(allowed|approved|ready|enabled|required)\b`)},
	{"outbound_message_language", regexp.MustCompile(`(?i)\b(?:(?:the\s+)?(?:system|workflow|agent|automation|veritas)|we)\s+(?:will|can|may|is\s+approved\s+to|is\s+allowed\s+to|is\s+ready\s+to)\s+(?:automatically\s+)?(?:send|deliver)\s+(?:calls?|texts?|sms|emails?|outbound\s+messages?|review\s+requests?)\b|\bautomatically\s+(?:send|deliver)\s+(?:calls?|texts?|sms|emails?|outbound\s+messages?|review\s+requests?)\b`)},
	{"customer_writeback_language", regexp.MustCompile(`(?i)\b(write\s*back|writeback|implement|install|activate)\s+(in|into|to|inside)\s+(the\s+)?customer\s+(system|crm|account|environment)\b`)},
	{"guaranteed_roi_language", regexp.MustCompile(`(?i)\b(guaranteed|guarantees)\s+(roi|revenue|sales|leads?|payback|return)\b`)},
	{"public_launch_ready_language", regexp.MustCompile(`(?i)\b(public\s+launch|customer\s+launch|external\s+delivery)\s+(is\s+)?(ready|approved|allowed|enabled)\b`)},
	{"readiness_claim_language", regexp.MustCompile(`(?i)\b(legal|compliance|security)\s+(readiness|ready|approved|cleared|certified)\b`)},
	{"owner_approval_inference_language", regexp.MustCompile(`(?i)\b(owner|randall)\s+approval\s+(is\s+)?(inferred|assumed|granted|automatic)\b`)},
}

var negativeContext = regexp.MustCompile(`(?i)\b(no|not|never|without|blocked|forbidden|prohibited|disallowed|deferred|not\s+in\s+scope|before\s+a\s+future|requires?\s+(?:future|explicit|per-send|human|owner)\s+approval|(?:after|with|subject\s+to)\s+explicit\s+(?:per-send|human|owner)\s+approval|explicit\s+(?:per-send|human|owner)\s+approval|human\s+approval|manual\s+review)\b`)

var uncheckedMarkdownOption = regexp.MustCompile(`^\s*[-*]\s*\[\s*\]`)

var htmlTag = regexp.MustCompile(`<[^>]+>`)

func discoverCustomerSurfaces(root string) (map[string][]string, error) {
	discovered := make(map[string][]string, len(customerSurfaceCategories))
	for _, category := range customerSurfaceCategories {
		discovered[category.name] = nil
	}
	dir := filepath.Join(root, filepath.FromSlash(customerSurfaceDir))
	entries, err := os.ReadDir(dir)
	if err != nil {
		return discovered, err
	}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(entry.Name()))
		if ext != ".md" && ext != ".html" {
			continue
		}
		name := strings.ToLower(entry.Name())
		for _, category := range customerSurfaceCategories {
			matches := true
			for _, part := range category.nameParts {
				if !strings.Contains(name, part) {
					matches = false
					break
				}
			}
			if matches {
				rel := filepath.ToSlash(filepath.Join(filepath.FromSlash(customerSurfaceDir), entry.Name()))
				discovered[category.name] = append(discovered[category.name], rel)
			}
		}
	}
	for category := range discovered {
		sort.Strings(discovered[category])
	}
	return discovered, nil
}

func safePath(root, rel string) (string, error) {
	path := filepath.Clean(filepath.FromSlash(rel))
	if filepath.IsAbs(path) || path == ".." || strings.HasPrefix(path, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("path must remain relative to root: %s", rel)
	}
	return filepath.Join(root, path), nil
}

func Run(root string, files []string) Report {
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
	if len(files) == 0 {
		files = append([]string(nil), defaultJSONFiles...)
		discovered, err := discoverCustomerSurfaces(root)
		if err != nil {
			add(customerSurfaceDir, "customer_surface_discovery", "critical", false, err.Error())
		}
		for _, category := range customerSurfaceCategories {
			matches := discovered[category.name]
			ok := len(matches) > 0
			detail := fmt.Sprintf("category=%s matched=%d", category.name, len(matches))
			add(customerSurfaceDir, "discover_"+category.name, "critical", ok, detail)
			files = append(files, matches...)
		}
	}

	for _, rel := range files {
		path, err := safePath(root, rel)
		if err != nil {
			add(rel, "path_scope", "critical", false, err.Error())
			continue
		}
		bytes, err := os.ReadFile(path)
		if err != nil {
			add(rel, "exists", "critical", false, err.Error())
			continue
		}
		checked = append(checked, filepath.ToSlash(rel))
		add(rel, "exists", "info", true, "")
		ext := strings.ToLower(filepath.Ext(path))
		raw := string(bytes)
		switch ext {
		case ".json":
			var doc any
			if err := json.Unmarshal(bytes, &doc); err != nil {
				add(rel, "json_valid", "critical", false, err.Error())
				continue
			}
			add(rel, "json_valid", "info", true, "")
			scanAuthorityFlags(rel, doc, add)
			if normalized, err := json.MarshalIndent(doc, "", "  "); err == nil {
				raw = string(normalized)
			}
		case ".md":
			add(rel, "text_scanned", "info", true, "markdown")
		case ".html":
			add(rel, "text_scanned", "info", true, "html")
			raw = htmlTag.ReplaceAllString(raw, " ")
		default:
			add(rel, "supported_text_or_json", "critical", false, fmt.Sprintf("unsupported extension: %s", ext))
			continue
		}
		scanPositiveLanguage(rel, raw, add)
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
		return text == "true" || text == "yes" || text == "1" || text == "allowed" || text == "approved" || text == "ready" || text == "enabled" || text == "granted" || text == "authorized"
	default:
		return false
	}
}

func scanPositiveLanguage(path, raw string, add func(string, string, string, bool, string)) {
	lines := strings.Split(raw, "\n")
	for lineNo, line := range lines {
		if uncheckedMarkdownOption.MatchString(line) {
			continue
		}
		for _, pattern := range forbiddenPositivePatterns {
			loc := pattern.re.FindStringIndex(line)
			if loc == nil {
				continue
			}
			window := contextWindow(line, loc[0], loc[1])
			if explicitlyNegativeContext(line, loc[0], loc[1]) {
				continue
			}
			add(path, pattern.name, "critical", false, fmt.Sprintf("line=%d text=%s", lineNo+1, strings.TrimSpace(window)))
		}
	}
}

func explicitlyNegativeContext(line string, start, end int) bool {
	left := 0
	if boundary := strings.LastIndexAny(line[:start], ".;!?|"); boundary >= 0 {
		left = boundary + 1
	}
	right := len(line)
	if boundary := strings.IndexAny(line[end:], ".;!?|"); boundary >= 0 {
		right = end + boundary
	}
	if start-left > 160 {
		left = start - 160
	}
	if right-end > 160 {
		right = end + 160
	}
	window := line[left:right]
	return negativeContext.MatchString(window)
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
