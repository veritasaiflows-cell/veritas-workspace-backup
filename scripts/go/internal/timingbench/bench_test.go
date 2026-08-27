package timingbench

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

func TestRunExecutesOnlyAllowlistedValidator(t *testing.T) {
	root := t.TempDir()
	binDir := filepath.Join(root, "scripts", "go", "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatal(err)
	}
	binaryName := "go-json-proof-contract-lint"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}
	if err := os.WriteFile(filepath.Join(binDir, binaryName), []byte("fixture"), 0o755); err != nil {
		t.Fatal(err)
	}

	called := false
	report := Run(Options{
		Root:       root,
		Validators: []string{"go-json-proof-contract-lint"},
		Timeout:    time.Second,
		Runner: func(ctx context.Context, path string, args []string) CommandResult {
			called = true
			if args[0] != "--root" || args[1] != root {
				t.Fatalf("unexpected args: %#v", args)
			}
			return CommandResult{ExitCode: 0, Output: "status=ok"}
		},
	})
	if !called {
		t.Fatal("expected runner to be called")
	}
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s", report.Status)
	}
	if report.Summary.ExecutedCount != 1 || report.Summary.FailedCount != 0 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
	if report.Results[0].ElapsedMS == nil {
		t.Fatalf("expected elapsed timing")
	}
}

func TestRunBlocksUnknownValidatorRequest(t *testing.T) {
	root := t.TempDir()
	called := false
	report := Run(Options{
		Root:       root,
		Validators: []string{"go-json-proof-contract-lint;Remove-Item"},
		Runner: func(ctx context.Context, path string, args []string) CommandResult {
			called = true
			return CommandResult{}
		},
	})
	if called {
		t.Fatal("unsafe request should not execute runner")
	}
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.UnsafeRequestCount != 1 {
		t.Fatalf("expected unsafe request count 1, got %#v", report.Summary)
	}
}

func TestRunInspectOnlyReportsMissingAsWarning(t *testing.T) {
	report := Run(Options{
		Root:        t.TempDir(),
		Validators:  []string{"go-sql-canon-proof-bundle-lint"},
		InspectOnly: true,
	})
	if report.Status != "warning" {
		t.Fatalf("expected warning, got %s", report.Status)
	}
	if report.Summary.MissingCount != 1 {
		t.Fatalf("expected missing count 1, got %#v", report.Summary)
	}
}
