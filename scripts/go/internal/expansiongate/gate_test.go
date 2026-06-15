package expansiongate

import "testing"

func TestAuthorityDefaults(t *testing.T) {
	report := Report{AuthorityBoundary: AuthorityBoundary{ReportOnly: true}, Validation: Validation{Status: "ok"}}
	if err := Validate(report); err != nil {
		t.Fatalf("expected authority defaults to validate: %v", err)
	}
	report.AuthorityBoundary.BroadTickerImportAllowed = true
	if err := Validate(report); err == nil {
		t.Fatal("expected authority widening to fail")
	}
}
