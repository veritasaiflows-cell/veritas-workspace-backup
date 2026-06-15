package financehuman

import "testing"

func ptr(value int64) *int64 {
	return &value
}

func TestValidateSQLCanon(t *testing.T) {
	check := SQLCanonCheck{
		Status:                "ok",
		Exists:                true,
		Integrity:             "ok",
		ActiveTickerCount:     ptr(100),
		LegacyAnswerPathCount: ptr(42),
		ReviewMonitorCount:    ptr(58),
	}
	validation := validateSQLCanon(check)
	if validation.Status != "ok" || validation.Failed != 0 {
		t.Fatalf("expected ok validation: %+v", validation)
	}
	check.ReviewMonitorCount = ptr(57)
	validation = validateSQLCanon(check)
	if validation.Status != "blocked" || validation.Failed == 0 {
		t.Fatalf("expected blocked validation: %+v", validation)
	}
}

func TestAuthorityBoundary(t *testing.T) {
	report := Report{AuthorityBoundary: AuthorityBoundary{ReportOnly: true, ReadOnly: true}, Validation: Validation{Status: "ok"}}
	if err := Validate(report); err != nil {
		t.Fatalf("expected boundary to validate: %v", err)
	}
	report.AuthorityBoundary.DeleteAllowed = true
	if err := Validate(report); err == nil {
		t.Fatal("expected delete authority widening to fail")
	}
}
