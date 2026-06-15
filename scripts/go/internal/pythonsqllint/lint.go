package pythonsqllint

import (
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

type Summary struct {
	Checks           int `json:"checks"`
	Critical         int `json:"critical"`
	Warnings         int `json:"warnings"`
	PythonFiles      int `json:"python_files"`
	SQLTouchingFiles int `json:"sql_touching_files"`
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

type Options struct {
	Root  string
	Files []string
}

var targetName = regexp.MustCompile(`(?i)(sql|sqlite|finance|canon|portfolio|promotion|artifact_index|intelligence_state)`)
var sqliteTouch = regexp.MustCompile(`(?i)(sqlite3|\.sqlite|sqlite|CREATE\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE)`)
var sqlWrite = regexp.MustCompile(`(?i)\b(CREATE\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE|os\.replace|shutil\.move)\b`)
var durableFinancePath = regexp.MustCompile(`(?i)state[/\\]finance|finance-canon\.sqlite|portfolio-config|Execution Board|03\.\s*Portfolio`)

var forbiddenPositivePatterns = []struct {
	name string
	re   *regexp.Regexp
}{
	{"sql_canon_language", regexp.MustCompile(`(?i)\b(sql|sqlite|database|db)\s+(is|becomes|as|treated\s+as|acts\s+as)\s+(canon|canonical|source\s+of\s+truth|approval\s+surface)\b`)},
	{"approval_inference_language", regexp.MustCompile(`(?i)\b(owner|randall)\s+approval\s+(is\s+)?(inferred|assumed|automatic)\b`)},
	{"execution_language", regexp.MustCompile(`(?i)\b(approved|ready|allowed|authorized)\s+(for\s+)?(trade|trading|execution|order|account\s+action|live\s+brokerage)\b`)},
	{"customer_delivery_language", regexp.MustCompile(`(?i)\b(customer|external|public)\s+(delivery|launch|output)\s+(is\s+)?(approved|allowed|ready|enabled)\b`)},
	{"proposal_apply_language", regexp.MustCompile(`(?i)\b(proposal|packet)\s+(apply|application)\s+(is\s+)?(allowed|approved|ready|automatic)\b`)},
}

var negativeContext = regexp.MustCompile(`(?i)\b(no|not|never|without|blocked|forbidden|prohibited|disallowed|review[- ]only|not\s+canon|not\s+approval|not\s+execution|owner[- ]gated|requires\s+approval|proposal[- ]only|does\s+not|must\s+not|cannot|bounded|exactly|explicit|scoped)\b`)

func Run(opts Options) Report {
	root := opts.Root
	if root == "" {
		root = "."
	}
	files := opts.Files
	if len(files) == 0 {
		files = discoverFiles(root)
	}

	var findings []Finding
	add := func(path, check, severity string, ok bool, detail string) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	var checked []string
	sqlTouching := 0
	for _, rel := range files {
		path := filepath.Join(root, filepath.FromSlash(rel))
		bytes, err := os.ReadFile(path)
		if err != nil {
			add(rel, "python_file_readable", "critical", false, err.Error())
			continue
		}
		text := string(bytes)
		if !sqliteTouch.MatchString(text) && !targetName.MatchString(rel) {
			continue
		}
		checked = append(checked, filepath.ToSlash(rel))
		add(rel, "python_file_readable", "info", true, "")
		if sqliteTouch.MatchString(text) {
			sqlTouching++
			add(rel, "sql_touch_detected", "info", true, "")
		}
		scanForbiddenLanguage(rel, text, add)
		scanContract(rel, text, add)
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
		SchemaVersion:  "python_sql_contract_lint.v1",
		GeneratedAtUTC: time.Now().UTC().Format(time.RFC3339),
		Status:         status,
		Root:           filepath.ToSlash(root),
		CheckedFiles:   checked,
		Findings:       findings,
		Summary: Summary{
			Checks:           len(findings),
			Critical:         critical,
			Warnings:         warnings,
			PythonFiles:      len(files),
			SQLTouchingFiles: sqlTouching,
		},
		Boundary: "Read-only Go validator over Python/SQL script contracts. No script execution, SQL writes, canon/portfolio mutation, customer/external delivery, paper/live/account action, config/runtime mutation, or owner approval inference.",
	}
}

func discoverFiles(root string) []string {
	var out []string
	scripts := filepath.Join(root, "scripts")
	_ = filepath.WalkDir(scripts, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() || filepath.Ext(path) != ".py" {
			return nil
		}
		name := filepath.Base(path)
		rel, relErr := filepath.Rel(root, path)
		if relErr != nil {
			return nil
		}
		if targetName.MatchString(name) {
			out = append(out, filepath.ToSlash(rel))
		}
		return nil
	})
	sort.Strings(out)
	return out
}

func scanForbiddenLanguage(path, raw string, add func(string, string, string, bool, string)) {
	lines := strings.Split(raw, "\n")
	for lineNo, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "#") || strings.HasPrefix(trimmed, "\"\"\"") || strings.HasPrefix(trimmed, "'''") {
			// Comments and docstrings are where stop-line language normally lives.
			continue
		}
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

func scanContract(path, raw string, add func(string, string, string, bool, string)) {
	lower := strings.ToLower(raw)
	if sqliteTouch.MatchString(raw) {
		if strings.Contains(lower, "validate") || strings.Contains(lower, "--validate") {
			add(path, "sql_script_has_validation_surface", "info", true, "")
		} else {
			add(path, "sql_script_has_validation_surface", "warning", false, "SQL-touching script has no obvious validate surface")
		}
		if hasBoundaryLanguage(lower) {
			add(path, "sql_script_has_boundary_language", "info", true, "")
		} else {
			add(path, "sql_script_has_boundary_language", "warning", false, "SQL-touching script has no obvious authority boundary language")
		}
	}
	if sqlWrite.MatchString(raw) && durableFinancePath.MatchString(raw) {
		if strings.Contains(lower, "approval") || strings.Contains(lower, "approval-reference") || strings.Contains(lower, "approval_reference") {
			add(path, "durable_finance_write_mentions_approval", "info", true, "")
		} else {
			add(path, "durable_finance_write_mentions_approval", "warning", false, "durable finance/portfolio write path has no obvious approval reference")
		}
		if strings.Contains(lower, "backup") || strings.Contains(lower, "rollback") {
			add(path, "durable_finance_write_mentions_backup_or_rollback", "info", true, "")
		} else {
			add(path, "durable_finance_write_mentions_backup_or_rollback", "warning", false, "durable finance/portfolio write path has no obvious backup/rollback language")
		}
	}
}

func hasBoundaryLanguage(lower string) bool {
	needles := []string{
		"read-only",
		"review-only",
		"not canon",
		"no canon",
		"no portfolio",
		"no paper/live",
		"no execution",
		"no owner approval",
		"does not authorize",
		"authority",
	}
	for _, needle := range needles {
		if strings.Contains(lower, needle) {
			return true
		}
	}
	return false
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
