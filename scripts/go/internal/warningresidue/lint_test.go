package warningresidue

import "testing"

func TestClassifyCronPayloadShapeResidue(t *testing.T) {
	cases := []string{
		"payload_message_present_for_bloat_check",
		"payload_message_within_prompt_char_budget",
		"payload_message_within_line_budget",
		"delivery_none_has_no_channel",
		"delivery_mode_present_for_agent_payload",
	}
	for _, check := range cases {
		className, ok := classify("cron-contract-json-proof-lint", "state/cron-contracts/example.json", check, "fixture")
		if !ok {
			t.Fatalf("expected classification for %s", check)
		}
		if className != "cron_payload_shape_residue" {
			t.Fatalf("expected cron payload class for %s, got %s", check, className)
		}
	}
}

func TestClassifyAuditGapWarningResidue(t *testing.T) {
	cases := []struct {
		validator string
		check     string
		want      string
	}{
		{"entry-stop-band-freshness-validator", "canon_reference_source_hash_matches_disk", "entry_stop_source_lineage_residue"},
		{"entry-stop-band-freshness-validator", "canon_reference_generated_at_present", "entry_stop_source_lineage_residue"},
		{"entry-stop-band-freshness-validator", "canon_reference_source_fresh_within_max_age", "entry_stop_source_lineage_residue"},
		{"json-proof-structural-validator", "status_present", "bulk_json_shape_residue"},
		{"json-proof-structural-validator", "schema_or_generated_at_present", "bulk_json_shape_residue"},
		{"workflow-artifact-freshness-gate", "file_mtime_within_default_max_age", "workflow_artifact_freshness_residue"},
		{"workflow-artifact-freshness-gate", "artifact_sha256_matches_index", "artifact_index_hash_drift"},
		{"cross-db-referential-integrity-probe", "ticker_set_matches_base:finance_state.latest_valid_entry_stop_refs", "optional_cross_db_mirror_drift"},
		{"pm-queue-authority-lint", "stale_lanes_zero", "pm_queue_state_residue"},
		{"paper-trading-guard-preflight", "kill_switch_expires_at_present", "paper_guard_readiness_residue"},
		{"sql-source-artifact-freshness-lint", "source_generated_at_fresh", "source_artifact_freshness_residue"},
	}
	for _, tc := range cases {
		className, ok := classify(tc.validator, "tmp/example.json", tc.check, "fixture")
		if !ok {
			t.Fatalf("expected classification for %s %s", tc.validator, tc.check)
		}
		if className != tc.want {
			t.Fatalf("expected %s for %s %s, got %s", tc.want, tc.validator, tc.check, className)
		}
	}
}
