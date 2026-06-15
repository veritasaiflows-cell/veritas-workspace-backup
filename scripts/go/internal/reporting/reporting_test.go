package reporting

import "testing"

type fakeFinding struct {
	ok       bool
	severity string
}

func (f fakeFinding) IsOK() bool {
	return f.ok
}

func (f fakeFinding) FindingSeverity() string {
	return f.severity
}

func TestStatusFromCounts(t *testing.T) {
	if got := StatusFromCounts(0, 0); got != "ok" {
		t.Fatalf("got %q", got)
	}
	if got := StatusFromCounts(0, 1); got != "warning" {
		t.Fatalf("got %q", got)
	}
	if got := StatusFromCounts(1, 0); got != "blocked" {
		t.Fatalf("got %q", got)
	}
}

func TestSummarizeFindings(t *testing.T) {
	summary := SummarizeFindings([]fakeFinding{
		{ok: true, severity: "info"},
		{ok: false, severity: "warning"},
		{ok: false, severity: "critical"},
	})
	if summary.Checks != 3 || summary.Warnings != 1 || summary.Critical != 1 {
		t.Fatalf("unexpected summary: %#v", summary)
	}
}
