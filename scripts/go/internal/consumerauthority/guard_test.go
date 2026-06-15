package consumerauthority

import (
	"os"
	"path/filepath"
	"testing"
)

func TestValidateRejectsWidenedAuthority(t *testing.T) {
	report := Report{
		Status:            "ok",
		AuthorityBoundary: AuthorityBoundary{ReportOnly: true, ReadOnly: true, OwnerApprovalInferred: true},
	}
	if err := Validate(report); err == nil {
		t.Fatal("expected widened authority to fail validation")
	}
}

func TestDiffKeys(t *testing.T) {
	extra, missing := diffKeys([]string{"a", "b", "c"}, []string{"b", "d"})
	if len(extra) != 2 || extra[0] != "a" || extra[1] != "c" {
		t.Fatalf("unexpected extra keys: %#v", extra)
	}
	if len(missing) != 1 || missing[0] != "d" {
		t.Fatalf("unexpected missing keys: %#v", missing)
	}
}

func TestContainsForbiddenTerm(t *testing.T) {
	if !containsForbiddenTerm("target_weight") {
		t.Fatal("target_weight should be forbidden")
	}
	if containsForbiddenTerm("source_freshness_classification") {
		t.Fatal("source freshness should not be forbidden")
	}
}

func TestFallbackValueLookup(t *testing.T) {
	values := map[string]any{
		"NVDA:earnings_lifecycle_status":             "fresh",
		"last_earnings_date":                         "2026-05-01",
		"deployment:source_freshness_classification": "current",
	}
	if value, ok := fallbackValue(values, "NVDA:earnings_lifecycle_status"); !ok || value != "fresh" {
		t.Fatalf("expected exact key fallback, got %#v ok=%v", value, ok)
	}
	if value, ok := fallbackValue(values, "NVDA:last_earnings_date"); !ok || value != "2026-05-01" {
		t.Fatalf("expected field-name fallback, got %#v ok=%v", value, ok)
	}
	if value, ok := fallbackValue(values, "deployment:source_freshness_classification"); !ok || value != "current" {
		t.Fatalf("expected scoped fallback, got %#v ok=%v", value, ok)
	}
}

func TestActiveEntryStopReferenceKeys(t *testing.T) {
	root := t.TempDir()
	tmpDir := filepath.Join(root, "tmp")
	if err := os.MkdirAll(tmpDir, 0o755); err != nil {
		t.Fatal(err)
	}
	payload := `{
		"status": "activation_ready",
		"active_entry_stop_reference_keys": [
			"VRT:reference_price_high",
			"NVDA:reference_level_source_sha256",
			"VRT:reference_price_high",
			"NVDA:reference_price_low"
		]
	}`
	if err := os.WriteFile(filepath.Join(tmpDir, "wf72-entry-stop-sql-activation-state.json"), []byte(payload), 0o644); err != nil {
		t.Fatal(err)
	}

	keys := activeEntryStopReferenceKeys(root)
	expected := []string{
		"NVDA:reference_level_source_sha256",
		"NVDA:reference_price_low",
		"VRT:reference_price_high",
	}
	if len(keys) != len(expected) {
		t.Fatalf("unexpected key count: %#v", keys)
	}
	for i := range expected {
		if keys[i] != expected[i] {
			t.Fatalf("unexpected keys: %#v", keys)
		}
	}
}

func TestActiveEntryStopReferenceKeysFailClosedOnInvalidField(t *testing.T) {
	root := t.TempDir()
	tmpDir := filepath.Join(root, "tmp")
	if err := os.MkdirAll(tmpDir, 0o755); err != nil {
		t.Fatal(err)
	}
	payload := `{
		"status": "activation_ready",
		"active_entry_stop_reference_keys": ["NVDA:target_weight"]
	}`
	if err := os.WriteFile(filepath.Join(tmpDir, "wf72-entry-stop-sql-activation-state.json"), []byte(payload), 0o644); err != nil {
		t.Fatal(err)
	}

	if keys := activeEntryStopReferenceKeys(root); len(keys) != 0 {
		t.Fatalf("invalid active key should fail closed, got %#v", keys)
	}
}
