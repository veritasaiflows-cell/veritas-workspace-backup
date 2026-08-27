package answercheck

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestAnswerCheckCleanAssemblerFixture(t *testing.T) {
	root := t.TempDir()
	writeAnswerFixture(t, root, "tmp/trade-grade-full-answer/AAA.json", fullAnswerPacket(false, nil))
	writeAnswerFixture(t, root, "tmp/ticker-answer-packets/AAA.current.json", map[string]any{"status": "ok"})
	writeAnswerFixture(t, root, "tmp/full-answer-parity/full-answer-parity-rollup.json", map[string]any{
		"status": "ok",
		"summary": map[string]any{
			"ticker_count":                 1,
			"production_answer_path_count": 1,
		},
		"authority_boundary": map[string]any{"capital_deployment_allowed": false, "owner_approval_inferred": false},
	})

	report := Run(Options{
		Root:        root,
		Now:         mustAnswerTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours: 24,
	})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s critical=%d warnings=%d findings=%+v", report.Status, report.Summary.Critical, report.Summary.Warnings, report.Findings)
	}
}

func TestAnswerCheckBlocksMissingSectionAndAuthority(t *testing.T) {
	root := t.TempDir()
	writeAnswerFixture(t, root, "tmp/trade-grade-full-answer/AAA.json", fullAnswerPacket(true, []string{"valuation"}))

	report := Run(Options{
		Root:        root,
		Now:         mustAnswerTime(t, "2026-06-22T01:00:00Z"),
		MaxAgeHours: 24,
	})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.MissingSectionPacketCount == 0 || report.Summary.ForbiddenAuthorityPacketCount == 0 {
		t.Fatalf("expected missing section and authority violation, got %+v", report.Summary)
	}
}

func fullAnswerPacket(forbidden bool, omit []string) map[string]any {
	required := append([]string{}, defaultRequiredSections...)
	sections := map[string]any{}
	for _, section := range required {
		if containsString(omit, section) {
			continue
		}
		sections[section] = map[string]any{"section_id": section, "status": "ok"}
	}
	return map[string]any{
		"schema":           "veritas.trade_grade_full_answer_assembler.v1",
		"status":           "ok",
		"ticker":           "AAA",
		"generated_at_utc": "2026-06-22T00:00:00Z",
		"review_only":      true,
		"canonical_full_answer_contract": map[string]any{
			"required_sections": required,
		},
		"sections": sections,
		"summary": map[string]any{
			"missing_sections": omit,
		},
		"authority_boundary": map[string]any{
			"capital_deployment_allowed":      forbidden,
			"capital_deployment_approved":     false,
			"trade_or_execution_approved":     false,
			"paper_or_live_execution_allowed": false,
			"owner_approval_inferred":         false,
		},
	}
}

func writeAnswerFixture(t *testing.T, root, rel string, value any) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, append(bytes, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}

func mustAnswerTime(t *testing.T, value string) time.Time {
	t.Helper()
	parsed, err := time.Parse(time.RFC3339, value)
	if err != nil {
		t.Fatal(err)
	}
	return parsed
}
