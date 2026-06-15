package sqllatency

import "testing"

func TestMedianAndPercentile(t *testing.T) {
	values := []float64{1, 2, 3, 4, 5}
	if got := median(values); got != 3 {
		t.Fatalf("median=%v", got)
	}
	if got := percentile(values, 95); got != 5 {
		t.Fatalf("p95=%v", got)
	}
}

func TestRunMissingDatabasesIsCritical(t *testing.T) {
	report := Run(Options{Root: t.TempDir(), Iterations: 1, SQLitePath: "sqlite3"})
	if report.Status != "critical" {
		t.Fatalf("expected critical with all DBs missing, got %s", report.Status)
	}
	if report.Summary.Successful != 0 {
		t.Fatalf("expected zero successful probes, got %d", report.Summary.Successful)
	}
	if report.Summary.FailedOrMissing != len(defaultBenchmarks) {
		t.Fatalf("failed_or_missing=%d benchmarks=%d", report.Summary.FailedOrMissing, len(defaultBenchmarks))
	}
	if !report.Boundary["read_only"] || report.Boundary["db_mutation"] {
		t.Fatalf("unexpected authority boundary: %#v", report.Boundary)
	}
}
