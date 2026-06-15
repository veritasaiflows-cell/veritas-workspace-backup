package boundarylint

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

type Finding struct {
	Path    string `json:"path"`
	Check   string `json:"check"`
	OK      bool   `json:"ok"`
	Detail  string `json:"detail,omitempty"`
}

type Report struct {
	SchemaVersion string    `json:"schema_version"`
	Status        string    `json:"status"`
	Root          string    `json:"root"`
	Findings      []Finding `json:"findings"`
	Summary       Summary   `json:"summary"`
}

type Summary struct {
	Checks int `json:"checks"`
	Failed int `json:"failed"`
}

var forbiddenPositive = regexp.MustCompile(`(?i)(owner approval inferred|trade execution allowed|paper trade allowed|live trade allowed|automatic install allowed|autonomous authority expansion allowed|config/auth/channel/service mutation allowed|second memory tree allowed)`)

var requiredFiles = []string{
	"tmp/wf74-rsi-research-brief.json",
	"tmp/wf74-clawhub-rsi-inspection-queue.json",
	"tmp/wf74-reflection-to-proposal-pipeline.json",
	"tmp/wf74-rsi-trend-report.json",
	"tmp/wf74-rsi-evaluation-harness.json",
	"tmp/wf74-rsi-validation.json",
	"06. Playbooks/Project Continuity/Workflow 74 - Veritas Recursive Self-Improvement Loop.md",
}

func Run(root string) Report {
	var findings []Finding
	add := func(path, check string, ok bool, detail string) {
		findings = append(findings, Finding{Path: filepath.ToSlash(path), Check: check, OK: ok, Detail: detail})
	}

	combined := strings.Builder{}
	for _, rel := range requiredFiles {
		path := filepath.Join(root, filepath.FromSlash(rel))
		bytes, err := os.ReadFile(path)
		if err != nil {
			add(rel, "exists", false, err.Error())
			continue
		}
		add(rel, "exists", true, "")
		combined.Write(bytes)
		combined.WriteString("\n")
	}

	add("wf74_combined", "no_forbidden_positive_authority_language", !forbiddenPositive.MatchString(combined.String()), "")
	checkJSONBool(root, "tmp/wf74-clawhub-rsi-inspection-queue.json", "install_allowed", false, add)
	checkJSONBool(root, "tmp/wf74-rsi-evaluation-harness.json", "qa_required_before_apply", true, add)
	checkTrendReviewOnly(root, add)
	checkPipelineOrder(root, add)
	checkInspectionResultsIfPresent(root, add)

	failed := 0
	for _, finding := range findings {
		if !finding.OK {
			failed++
		}
	}
	status := "ok"
	if failed > 0 {
		status = "blocked"
	}
	return Report{
		SchemaVersion: "wf74_boundary_lint.v1",
		Status:        status,
		Root:          filepath.ToSlash(root),
		Findings:      findings,
		Summary:       Summary{Checks: len(findings), Failed: failed},
	}
}

func checkJSONBool(root, rel, field string, expected bool, add func(string, string, bool, string)) {
	path := filepath.Join(root, filepath.FromSlash(rel))
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(rel, "read_"+field, false, err.Error())
		return
	}
	var doc map[string]any
	if err := json.Unmarshal(bytes, &doc); err != nil {
		add(rel, "json_valid", false, err.Error())
		return
	}
	value, ok := doc[field].(bool)
	add(rel, field+fmt.Sprintf("=%v", expected), ok && value == expected, fmt.Sprintf("actual=%v", doc[field]))
}

func checkTrendReviewOnly(root string, add func(string, string, bool, string)) {
	rel := "tmp/wf74-rsi-trend-report.json"
	path := filepath.Join(root, filepath.FromSlash(rel))
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(rel, "read_trend", false, err.Error())
		return
	}
	var doc map[string]any
	if err := json.Unmarshal(bytes, &doc); err != nil {
		add(rel, "json_valid", false, err.Error())
		return
	}
	status, _ := doc["status"].(string)
	newCanon, _ := doc["new_canon_created"].(bool)
	add(rel, "trend_report_review_only_no_new_canon", status == "review_only" && !newCanon, fmt.Sprintf("status=%s new_canon=%v", status, newCanon))
}

func checkPipelineOrder(root string, add func(string, string, bool, string)) {
	rel := "tmp/wf74-reflection-to-proposal-pipeline.json"
	path := filepath.Join(root, filepath.FromSlash(rel))
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(rel, "read_pipeline", false, err.Error())
		return
	}
	var doc struct {
		Pipeline []struct { Name string `json:"name"` } `json:"pipeline"`
	}
	if err := json.Unmarshal(bytes, &doc); err != nil {
		add(rel, "json_valid", false, err.Error())
		return
	}
	evalIdx, applyIdx := -1, -1
	for i, stage := range doc.Pipeline {
		if stage.Name == "evaluate" { evalIdx = i }
		if stage.Name == "apply_or_defer" { applyIdx = i }
	}
	add(rel, "evaluate_before_apply_or_defer", evalIdx >= 0 && applyIdx >= 0 && evalIdx < applyIdx, fmt.Sprintf("evaluate=%d apply=%d", evalIdx, applyIdx))
}

func checkInspectionResultsIfPresent(root string, add func(string, string, bool, string)) {
	rel := "tmp/wf74-clawhub-inspection-results.json"
	path := filepath.Join(root, filepath.FromSlash(rel))
	bytes, err := os.ReadFile(path)
	if err != nil {
		add(rel, "optional_inspection_results_present", true, "not present yet")
		return
	}
	var doc map[string]any
	if err := json.Unmarshal(bytes, &doc); err != nil {
		add(rel, "json_valid", false, err.Error())
		return
	}
	installAllowed, _ := doc["install_allowed"].(bool)
	mutations, _ := doc["mutations_performed"].(bool)
	lockUnchanged, _ := doc["lock_unchanged"].(bool)
	add(rel, "clawhub_inspection_review_only", !installAllowed && !mutations && lockUnchanged, fmt.Sprintf("install_allowed=%v mutations=%v lock_unchanged=%v", installAllowed, mutations, lockUnchanged))
}
