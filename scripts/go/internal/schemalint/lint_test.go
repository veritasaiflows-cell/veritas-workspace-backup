package schemalint

import "testing"

func TestFilterContracts(t *testing.T) {
	contracts := filterContracts([]string{"tmp/pm-program-state.sqlite"})
	if len(contracts) != 1 {
		t.Fatalf("expected one contract, got %d", len(contracts))
	}
	if contracts[0].Path != "tmp/pm-program-state.sqlite" {
		t.Fatalf("unexpected contract: %s", contracts[0].Path)
	}
}

func TestMissingDBBlocks(t *testing.T) {
	report := Run(Options{Root: t.TempDir(), DBFiles: []string{"tmp/pm-program-state.sqlite"}, SQLitePath: "sqlite3"})
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if report.Summary.Critical == 0 {
		t.Fatal("expected critical finding")
	}
}
