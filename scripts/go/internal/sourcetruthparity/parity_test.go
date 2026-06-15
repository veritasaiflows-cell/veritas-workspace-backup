package sourcetruthparity

import "testing"

func TestParseBand(t *testing.T) {
	low, high := parseBand("150.00-160.50")
	if low == nil || high == nil || *low != 150.00 || *high != 160.50 {
		t.Fatalf("unexpected hyphen band: low=%v high=%v", low, high)
	}
	low, high = parseBand("150.00–160.50")
	if low == nil || high == nil || *low != 150.00 || *high != 160.50 {
		t.Fatalf("unexpected en dash band: low=%v high=%v", low, high)
	}
}

func TestCloseEnough(t *testing.T) {
	left := 100.001
	if !closeEnough(&left, "100.003") {
		t.Fatal("expected string numeric value within tolerance")
	}
	if closeEnough(&left, "100.02") {
		t.Fatal("expected value outside tolerance")
	}
}
