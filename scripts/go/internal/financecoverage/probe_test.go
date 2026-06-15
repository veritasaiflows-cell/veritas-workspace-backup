package financecoverage

import "testing"

func TestParseSummary(t *testing.T) {
	summary := parseSummary(map[string]any{
		"source_artifact_count": float64(12),
		"ticker_count_indexed":  float64(100),
		"data_family_count":     float64(24),
		"universe_ticker_count": float64(100),
	})
	if summary.SourceArtifactCount != 12 || summary.TickerCountIndexed != 100 || summary.DataFamilyCount != 24 || summary.UniverseTickerCount != 100 {
		t.Fatalf("unexpected summary: %+v", summary)
	}
}

func TestValidateAuthority(t *testing.T) {
	report := Report{
		SourceReport:      "tmp/finance-data-coverage-current.json",
		Summary:           Summary{SourceArtifactCount: 1, TickerCountIndexed: 1, DataFamilyCount: 1},
		SourceArtifacts:   map[string]SourceArtifact{"x": {Exists: true, Usable: true}},
		AuthorityBoundary: AuthorityBoundary{ReportOnly: true, ReadOnly: true},
	}
	report.Validation = validate(report)
	if err := Validate(report); err != nil {
		t.Fatalf("expected report to validate: %v", err)
	}
	report.AuthorityBoundary.OwnerApprovalInferred = true
	if err := Validate(report); err == nil {
		t.Fatal("expected authority widening to fail")
	}
}
