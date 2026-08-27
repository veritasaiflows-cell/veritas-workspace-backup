package boardlint

import (
	"os"
	"path/filepath"
	"testing"
)

func TestRunAcceptsThinExecutionBoard(t *testing.T) {
	root := t.TempDir()
	writeBoard(t, root, `<!-- THIN HUMAN SURFACE
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
Authority: human routing page only; no owner approval, portfolio mutation, order authority, archive/delete/apply authority, or execution.
-->

# Execution Board

## Purpose
Human path.

## Current Route
- tmp/trade-grade-decision-cards.json

## Owner Boundary
No owner approval is inferred. No execution.

## Human Policy Notes
- Do not chase.

## Historical Trail
- Backup exists.
`)
	report := Run(Options{Root: root})
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %#v", report.Status, report.Summary)
	}
	if !report.Summary.ThinSurface || report.Summary.TickerRowCount != 0 {
		t.Fatalf("unexpected summary: %#v", report.Summary)
	}
}

func TestRunBlocksMalformedTickerTableBand(t *testing.T) {
	root := t.TempDir()
	writeBoard(t, root, `<!-- THIN HUMAN SURFACE
Structured owner: state/finance/finance-canon.sqlite.
Authority: no owner approval, portfolio mutation, order authority, archive/delete/apply authority, or execution.
-->

# Execution Board

## Purpose
Human path.

## Current Route
Route.

## Owner Boundary
No owner approval. No execution.

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker condition | Authority note | Source freshness |
|---|---|---|---|---|---|---|---|---|---|
| NVDA | ready | review | 150 / 2026-06-22 | not-a-band | stop text | ok | none |  | fresh |

## Human Policy Notes
Notes.

## Historical Trail
Trail.
`)
	report := Run(Options{Root: root})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.NumericFieldFailures != 2 {
		t.Fatalf("expected two numeric failures, got %#v", report.Summary)
	}
	if report.Summary.Warnings == 0 {
		t.Fatalf("expected optional field warning for empty authority note")
	}
}

func TestRunBlocksMissingCanonicalSection(t *testing.T) {
	root := t.TempDir()
	writeBoard(t, root, "# Execution Board\n\n## Purpose\nx\n\n## Current Route\nx\n\n## Owner Boundary\nx\n")
	report := Run(Options{Root: root})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
}

func writeBoard(t *testing.T, root string, value string) {
	t.Helper()
	path := filepath.Join(root, "03. Portfolio", "Execution Board.md")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(value), 0o644); err != nil {
		t.Fatal(err)
	}
}
