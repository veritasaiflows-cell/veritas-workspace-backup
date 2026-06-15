package sqlproof

import "testing"

func TestRunFailsClosedForMissingDB(t *testing.T) {
	report := Run(Options{Root: t.TempDir(), DBFiles: []string{"tmp/veritas-canon-cache.sqlite"}})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked for missing DB, got %s", report.Status)
	}
	if report.Summary.Critical == 0 {
		t.Fatalf("expected critical finding for missing DB")
	}
	if report.Summary.BlockedDBs == 0 {
		t.Fatalf("expected blocked DB count")
	}
	if report.Boundary == "" || report.MigrationPosture == "" {
		t.Fatalf("expected boundary and migration posture")
	}
}
