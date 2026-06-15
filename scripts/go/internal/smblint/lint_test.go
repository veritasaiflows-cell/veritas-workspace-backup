package smblint

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCleanSMBFixturePasses(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{})
	report := Run(root, nil)
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %+v", report.Status, report.Findings)
	}
}

func TestTruthyCustomerDataFlagBlocks(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{
		"tmp/wf75-smb-customer-preview.json": `{"status":"bad","authority_boundary":{"real_customer_data_allowed":true}}`,
	})
	report := Run(root, nil)
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "forbidden_truthy_authority_flag") {
		t.Fatalf("expected truthy authority finding: %+v", report.Findings)
	}
}

func TestCredentialPositiveLanguageBlocks(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{
		"tmp/wf75-smb-automation-blueprints.json": `{"status":"bad","plan":"CRM credential access is approved for the pilot."}`,
	})
	report := Run(root, nil)
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "credential_access_language") {
		t.Fatalf("expected credential language finding: %+v", report.Findings)
	}
}

func TestNegativeBoundaryLanguageDoesNotBlock(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{
		"tmp/wf75-smb-automation-blueprints.json": `{"status":"ok","not_in_scope":["credential access is blocked","no outbound messages are sent"]}`,
	})
	report := Run(root, nil)
	if report.Status != "ok" {
		t.Fatalf("expected ok, got %s: %+v", report.Status, report.Findings)
	}
}

func TestPositiveOutboundLanguageBlocks(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{
		"tmp/wf75-smb-automation-blueprints.json": `{"status":"bad","claim":"The workflow will send texts to customers."}`,
	})
	report := Run(root, nil)
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "outbound_message_language") {
		t.Fatalf("expected outbound message finding: %+v", report.Findings)
	}
}

func TestGuaranteedROILanguageBlocks(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{
		"tmp/wf75-smb-pivot-pm-decision-packet.json": `{"status":"bad","claim":"This guarantees ROI for the owner."}`,
	})
	report := Run(root, nil)
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "guaranteed_roi_language") {
		t.Fatalf("expected ROI finding: %+v", report.Findings)
	}
}

func TestPublicLaunchReadyLanguageBlocks(t *testing.T) {
	root := t.TempDir()
	writeSMBFixtures(t, root, map[string]string{
		"tmp/generic-service-run-contract.json": `{"status":"bad","claim":"Public launch is ready."}`,
	})
	report := Run(root, nil)
	if report.Status != "blocked" {
		t.Fatalf("expected blocked, got %s", report.Status)
	}
	if !hasCheck(report, "public_launch_ready_language") {
		t.Fatalf("expected public launch finding: %+v", report.Findings)
	}
}

func writeSMBFixtures(t *testing.T, root string, overrides map[string]string) {
	t.Helper()
	clean := `{
	  "status": "ok",
	  "purpose": "internal review-only SMB workflow clarity packet",
	  "not_in_scope": [
	    "no real customer data",
	    "no credential access",
	    "no outbound messages",
	    "no public launch",
	    "no legal/compliance/security readiness claim"
	  ],
	  "authority_boundary": {
	    "real_customer_data_allowed": false,
	    "customer_identity_allowed": false,
	    "customer_data_retention_allowed": false,
	    "external_delivery_allowed": false,
	    "public_launch_allowed": false,
	    "customer_outreach_allowed": false,
	    "message_sending_allowed": false,
	    "phone_system_or_crm_credential_access_allowed": false,
	    "payment_pos_payroll_account_access_allowed": false,
	    "implementation_in_customer_systems_allowed": false,
	    "legal_tax_compliance_security_readiness_claim_allowed": false,
	    "guaranteed_roi_or_revenue_claim_allowed": false,
	    "owner_approval_inferred": false
	  }
	}`
	files := []string{
		"tmp/generic-service-run-contract.json",
		"tmp/wf75-smb-workflow-scenario-library.json",
		"tmp/wf75-smb-pivot-pm-decision-packet.json",
		"tmp/wf75-smb-customer-preview.json",
		"tmp/wf75-smb-pilot-decision-packet.json",
		"tmp/wf75-smb-automation-blueprints.json",
	}
	for _, rel := range files {
		content := clean
		if override, ok := overrides[rel]; ok {
			content = override
		}
		path := filepath.Join(root, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(strings.TrimSpace(content)+"\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}

func hasCheck(report Report, check string) bool {
	for _, finding := range report.Findings {
		if finding.Check == check && !finding.OK {
			return true
		}
	}
	return false
}
