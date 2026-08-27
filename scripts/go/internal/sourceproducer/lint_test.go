package sourceproducer

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestRunMapsKnownFreshnessArtifactsWithoutDowngradingDrift(t *testing.T) {
	root := t.TempDir()
	for _, path := range []string{
		"scripts/band_refresh.py",
		"scripts/reference_levels_band_proposals_source_migration.py",
		"scripts/reference_levels_targeted_repair_packet.py",
	} {
		mustWriteText(t, filepath.Join(root, filepath.FromSlash(path)), "# test\n")
	}
	mustWriteJSON(t, filepath.Join(root, "tmp", "freshness.json"), map[string]any{
		"status": "warning",
		"summary": map[string]any{
			"warnings":                          2,
			"critical":                          0,
			"hash_mismatch_count":               1,
			"missing_source_artifact_row_count": 1,
			"artifact_summaries": []any{
				map[string]any{
					"path":                  "tmp/band-proposals.json",
					"lineage_rows":          12,
					"source_status":         "ok_current_band_values_match_sql_reference",
					"validator_status":      "ok",
					"source_artifact_known": false,
					"hash_matches_disk":     false,
				},
			},
		},
		"findings": []any{
			map[string]any{"path": "tmp/band-proposals.json", "check": "source_artifact_hash_matches_lineage", "severity": "warning", "ok": false},
			map[string]any{"path": "tmp/band-proposals.json", "check": "source_artifacts_registry_row_present", "severity": "warning", "ok": false},
		},
	})

	report := Run(Options{Root: root, FreshnessReport: "tmp/freshness.json"})
	if report.Status != "ok" {
		t.Fatalf("expected mapped producer contract to be ok, got %s: %#v", report.Status, report.Summary)
	}
	if report.Summary.MappedArtifactCount != 1 || report.Summary.OpenRepairArtifactCount != 1 {
		t.Fatalf("unexpected repair summary: %#v", report.Summary)
	}
	if report.Summary.SourceArtifactDriftCount != 1 || report.Summary.RegistryGapCount != 1 {
		t.Fatalf("expected freshness drift to remain visible: %#v", report.Summary)
	}
}

func TestRunWarnsOnUnknownFreshnessArtifact(t *testing.T) {
	root := t.TempDir()
	mustWriteJSON(t, filepath.Join(root, "tmp", "freshness.json"), map[string]any{
		"status": "warning",
		"summary": map[string]any{
			"warnings": 1,
			"critical": 0,
			"artifact_summaries": []any{
				map[string]any{"path": "tmp/unknown.json", "lineage_rows": 1},
			},
		},
	})

	report := Run(Options{Root: root, FreshnessReport: "tmp/freshness.json"})
	if report.Status != "warning" {
		t.Fatalf("expected warning for unknown producer, got %s", report.Status)
	}
	if report.Summary.UnmappedArtifactCount != 1 {
		t.Fatalf("expected one unmapped artifact: %#v", report.Summary)
	}
}

func mustWriteJSON(t *testing.T, path string, value any) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	bytes, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, bytes, 0o644); err != nil {
		t.Fatal(err)
	}
}

func mustWriteText(t *testing.T, path, value string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(value), 0o644); err != nil {
		t.Fatal(err)
	}
}
