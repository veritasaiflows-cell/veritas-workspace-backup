package closeoutledger

import (
	"testing"
	"time"
)

func TestDefaultMemoryPathUsesPhoenixDateAfterUTCMidnight(t *testing.T) {
	now := time.Date(2026, 6, 30, 1, 59, 0, 0, time.UTC)
	got := memoryPathForTime(now)
	want := "memory/2026-06-29.md"
	if got != want {
		t.Fatalf("memory path = %q, want %q", got, want)
	}
}

func TestDefaultMemoryPathUsesPhoenixDateAfterLocalMidnight(t *testing.T) {
	now := time.Date(2026, 6, 30, 8, 0, 0, 0, time.UTC)
	got := memoryPathForTime(now)
	want := "memory/2026-06-30.md"
	if got != want {
		t.Fatalf("memory path = %q, want %q", got, want)
	}
}
