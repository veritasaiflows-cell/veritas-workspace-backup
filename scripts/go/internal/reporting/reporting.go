package reporting

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

type FindingLike interface {
	IsOK() bool
	FindingSeverity() string
}

type FindingSummary struct {
	Checks   int `json:"checks"`
	Critical int `json:"critical"`
	Warnings int `json:"warnings"`
}

func UTCNow() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func StatusFromCounts(critical, warnings int) string {
	switch {
	case critical > 0:
		return "blocked"
	case warnings > 0:
		return "warning"
	default:
		return "ok"
	}
}

func StatusFromBlockedWarnings(blocked, warnings int) string {
	return StatusFromCounts(blocked, warnings)
}

func SummarizeFindings[T FindingLike](findings []T) FindingSummary {
	summary := FindingSummary{Checks: len(findings)}
	for _, finding := range findings {
		if finding.IsOK() {
			continue
		}
		if finding.FindingSeverity() == "critical" {
			summary.Critical++
		} else {
			summary.Warnings++
		}
	}
	return summary
}

func ReadOnlyAuthorityBoundary() map[string]bool {
	return map[string]bool{
		"read_only":                     true,
		"sql_write_or_import_allowed":   false,
		"db_mutation":                   false,
		"canon_or_portfolio_mutation":   false,
		"customer_or_external_delivery": false,
		"paper_or_live_execution":       false,
		"owner_approval_inferred":       false,
		"config_auth_runtime_mutation":  false,
	}
}

func WriteJSON(path string, value any) error {
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, append(bytes, '\n'), 0o644)
}
