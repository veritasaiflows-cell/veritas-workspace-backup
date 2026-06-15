package boundarylint

import (
	"os"
	"path/filepath"
	"testing"
)

func TestForbiddenPositiveAuthorityLanguageBlocks(t *testing.T) {
	root := t.TempDir()
	writeRequiredFixture(t, root)
	path := filepath.Join(root, "tmp", "wf74-rsi-research-brief.json")
	if err := os.WriteFile(path, []byte(`{"status":"bad","text":"owner approval inferred"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	report := Run(root)
	if report.Status != "blocked" {
		t.Fatalf("expected blocked status, got %s", report.Status)
	}
}

func TestCleanFixturePasses(t *testing.T) {
	root := t.TempDir()
	writeRequiredFixture(t, root)
	report := Run(root)
	if report.Status != "ok" {
		t.Fatalf("expected ok status, got %s: %+v", report.Status, report.Findings)
	}
}

func writeRequiredFixture(t *testing.T, root string) {
	t.Helper()
	files := map[string]string{
		"tmp/wf74-rsi-research-brief.json": `{"status":"review_ready","authority_boundary":{"forbidden":["owner approval inference"]}}`,
		"tmp/wf74-clawhub-rsi-inspection-queue.json": `{"install_allowed":false}`,
		"tmp/wf74-reflection-to-proposal-pipeline.json": `{"pipeline":[{"name":"capture"},{"name":"evaluate"},{"name":"apply_or_defer"}]}`,
		"tmp/wf74-rsi-trend-report.json": `{"status":"review_only","new_canon_created":false}`,
		"tmp/wf74-rsi-evaluation-harness.json": `{"qa_required_before_apply":true}`,
		"tmp/wf74-rsi-validation.json": `{"status":"ok"}`,
		"06. Playbooks/Project Continuity/Workflow 74 - Veritas Recursive Self-Improvement Loop.md": `No owner approval inference. No trade/account authority.`,
	}
	for rel, content := range files {
		path := filepath.Join(root, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}
