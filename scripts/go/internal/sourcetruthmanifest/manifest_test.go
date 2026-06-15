package sourcetruthmanifest

import "testing"

func TestFalseFlagKeysStable(t *testing.T) {
	keys := FalseFlagKeys()
	if len(keys) != 14 {
		t.Fatalf("expected 14 false flags, got %d", len(keys))
	}
	for i := 1; i < len(keys); i++ {
		if keys[i-1] > keys[i] {
			t.Fatalf("false flag keys not sorted: %q before %q", keys[i-1], keys[i])
		}
	}
}

func TestValidateRejectsWidenedAuthority(t *testing.T) {
	report := Report{
		AuthorityFlags: copyFalseFlags(),
		Summary: Summary{
			DatabaseSurfaces: len(dbSurfaces),
			CanonicalNotes:   len(canonicalOwnerNotes),
		},
	}
	if err := Validate(report); err != nil {
		t.Fatalf("expected clean report: %v", err)
	}
	report.AuthorityFlags["owner_approval_inferred"] = true
	if err := Validate(report); err == nil {
		t.Fatal("expected authority widening error")
	}
}
