package sqlproof

import "testing"

func TestRunFailsClosedForMissingDB(t *testing.T) {
	report := Run(Options{Root: t.TempDir(), DBFiles: []string{"tmp/json-sql-promotion-index.sqlite"}})
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

// The canon cache was retired by the 2026-08-29 alerts-OS pivot; its absence is the expected state.
func TestRunTreatsAbsentRetiredDBAsOK(t *testing.T) {
	report := Run(Options{Root: t.TempDir(), DBFiles: []string{"tmp/veritas-canon-cache.sqlite"}})
	if report.Status == "blocked" || report.Summary.Critical != 0 {
		t.Fatalf("expected absent retired DB to be non-blocking, got status=%s critical=%d", report.Status, report.Summary.Critical)
	}
}
