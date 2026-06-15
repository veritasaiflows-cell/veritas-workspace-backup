package sourcetruthparity

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"veritas.local/wf74/internal/reporting"
	"veritas.local/wf74/internal/sqlutil"
)

const (
	schemaVersion = "sql_source_truth_parity_validation_go.v1"
	tolerance     = 0.005
)

type ExecutionRow struct {
	Ticker           string   `json:"ticker"`
	Lane             string   `json:"lane"`
	ActionState      string   `json:"action_state"`
	Close            *float64 `json:"close"`
	CloseDate        *string  `json:"close_date"`
	BandLow          *float64 `json:"band_low"`
	BandHigh         *float64 `json:"band_high"`
	Stop             *float64 `json:"stop"`
	TechnicalPosture string   `json:"technical_posture"`
	BlockerCondition string   `json:"blocker_condition"`
	AuthorityNote    string   `json:"authority_note"`
	SourceFreshness  string   `json:"source_freshness"`
	LineNumber       int      `json:"line_number"`
}

type SourceNote struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type FieldFamily struct {
	Name            string   `json:"name"`
	SourceOwnerNote string   `json:"source_owner_note"`
	FinanceSQLView  string   `json:"finance_sql_view"`
	CanonCacheTable string   `json:"canon_cache_table"`
	IncludedFields  []string `json:"included_fields"`
	ExcludedFields  []string `json:"excluded_fields"`
}

type Summary struct {
	MarkdownRows       int `json:"markdown_rows"`
	FinanceSQLRows     int `json:"finance_sql_rows"`
	CanonCacheTickers  int `json:"canon_cache_tickers"`
	ReadyRows          int `json:"ready_rows"`
	MismatchRows       int `json:"mismatch_rows"`
	MissingFinanceRows int `json:"missing_finance_rows"`
	MissingCanonRows   int `json:"missing_canon_rows"`
	FinanceExtraRows   int `json:"finance_extra_rows"`
	CanonExtraRows     int `json:"canon_extra_rows"`
}

type Mismatch struct {
	Ticker     string   `json:"ticker"`
	LineNumber int      `json:"line_number"`
	Mismatches []string `json:"mismatches"`
}

type BlockedFieldObservation struct {
	Ticker        string `json:"ticker"`
	ActionState   string `json:"action_state"`
	Lane          string `json:"lane"`
	BlockedReason string `json:"blocked_reason"`
}

type Comparison struct {
	Ticker                         string                    `json:"ticker"`
	LineNumber                     int                       `json:"line_number"`
	Markdown                       ExecutionRow              `json:"markdown"`
	FinanceSQL                     map[string]any            `json:"finance_sql,omitempty"`
	CanonCacheSQL                  map[string]map[string]any `json:"canon_cache_sql,omitempty"`
	Checks                         map[string]bool           `json:"checks"`
	CandidateFamilyReadyForThisRow bool                      `json:"candidate_family_ready_for_this_row"`
}

type Report struct {
	SchemaVersion     string `json:"schema_version"`
	GeneratedAtUTC    string `json:"generated_at_utc"`
	Status            string `json:"status"`
	SQLiteDriver      string `json:"sqlite_driver"`
	AuthorityBoundary string `json:"authority_boundary"`

	SourceOfTruthPromotionAllowedByThisArtifact bool `json:"source_of_truth_promotion_allowed_by_this_artifact"`
	SQLFirstConsumerMigrationAllowed            bool `json:"sql_first_consumer_migration_allowed"`
	SQLWritesAllowed                            bool `json:"sql_writes_allowed"`
	MarkdownMutationAllowed                     bool `json:"markdown_mutation_allowed"`
	PortfolioMutationAllowed                    bool `json:"portfolio_mutation_allowed"`
	OwnerApprovalInferred                       bool `json:"owner_approval_inferred"`
	RecommendationOrDeploymentAuthorityAllowed  bool `json:"recommendation_or_deployment_authority_allowed"`
	PaperOrLiveExecutionAllowed                 bool `json:"paper_or_live_execution_allowed"`
	CustomerOrExternalDeliveryAllowed           bool `json:"customer_or_external_delivery_allowed"`

	CandidateFieldFamily     FieldFamily               `json:"candidate_field_family"`
	SourceNote               SourceNote                `json:"source_note"`
	Summary                  Summary                   `json:"summary"`
	MissingFinanceTickers    []string                  `json:"missing_finance_tickers"`
	MissingCanonTickers      []string                  `json:"missing_canon_tickers"`
	FinanceExtraTickers      []string                  `json:"finance_extra_tickers"`
	CanonExtraTickers        []string                  `json:"canon_extra_tickers"`
	Mismatches               []Mismatch                `json:"mismatches"`
	BlockedFieldObservations []BlockedFieldObservation `json:"blocked_field_observations"`
	Comparisons              []Comparison              `json:"comparisons"`
	NextRequiredGates        []string                  `json:"next_required_gates"`
}

type Options struct {
	Root       string
	SQLitePath string
	Driver     string
}

var (
	closePattern  = regexp.MustCompile(`(-?\d+(?:\.\d+)?)\s*/\s*(\d{4}-\d{2}-\d{2})`)
	numberPattern = regexp.MustCompile(`-?\d+(?:\.\d+)?`)
	bandPattern   = regexp.MustCompile(`(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)`)
)

func Run(opts Options) (Report, error) {
	root := opts.Root
	if root == "" {
		root = "."
	}
	sqlitePath := opts.SQLitePath
	if sqlitePath == "" {
		sqlitePath = "sqlite3"
	}
	driver := opts.Driver
	if driver == "" {
		driver = sqlutil.DriverCLI
	}
	boardPath := filepath.Join(root, "03. Portfolio", "Execution Board.md")
	rows, err := parseExecutionBoard(boardPath)
	if err != nil {
		return Report{}, err
	}
	financeRefs, err := loadFinanceRefs(driver, sqlitePath, filepath.Join(root, "tmp", "finance-intelligence-state.sqlite"))
	if err != nil {
		return Report{}, err
	}
	canonRefs, err := loadCanonRefs(driver, sqlitePath, filepath.Join(root, "tmp", "veritas-canon-cache.sqlite"))
	if err != nil {
		return Report{}, err
	}
	report := buildReport(root, boardPath, driver, rows, financeRefs, canonRefs)
	return report, nil
}

func buildReport(root, boardPath, driver string, rows []ExecutionRow, financeRefs map[string]map[string]any, canonRefs map[string]map[string]map[string]any) Report {
	comparisons := []Comparison{}
	missingFinance := []string{}
	missingCanon := []string{}
	mismatches := []Mismatch{}
	blocked := []BlockedFieldObservation{}
	rowTickers := map[string]bool{}

	for _, row := range rows {
		ticker := row.Ticker
		rowTickers[ticker] = true
		finance, hasFinance := financeRefs[ticker]
		canon, hasCanon := canonRefs[ticker]
		if !hasFinance {
			missingFinance = append(missingFinance, ticker)
		}
		if !hasCanon {
			missingCanon = append(missingCanon, ticker)
		}
		checks := map[string]bool{
			"finance_band_low_match":  closeEnough(row.BandLow, lookupAny(finance, "entry_band_low")),
			"finance_band_high_match": closeEnough(row.BandHigh, lookupAny(finance, "entry_band_high")),
			"finance_stop_match":      closeEnough(row.Stop, lookupAny(finance, "stop_or_invalidation")),
			"canon_band_low_match":    closeEnough(row.BandLow, lookupNested(canon, "reference_price_low", "field_value")),
			"canon_band_high_match":   closeEnough(row.BandHigh, lookupNested(canon, "reference_price_high", "field_value")),
			"canon_stop_match":        closeEnough(row.Stop, lookupNested(canon, "reference_invalidation_level", "field_value")),
		}
		rowMismatches := []string{}
		for _, name := range sortedBoolKeys(checks) {
			if !checks[name] {
				rowMismatches = append(rowMismatches, name)
			}
		}
		if len(rowMismatches) > 0 {
			mismatches = append(mismatches, Mismatch{Ticker: ticker, LineNumber: row.LineNumber, Mismatches: rowMismatches})
		}
		blocked = append(blocked, BlockedFieldObservation{
			Ticker: ticker, ActionState: row.ActionState, Lane: row.Lane,
			BlockedReason: "action_state_and_lane_are_markdown_owner_only_not_part_of_entry_stop_reference_promotion",
		})
		comparisons = append(comparisons, Comparison{
			Ticker: ticker, LineNumber: row.LineNumber, Markdown: row, FinanceSQL: finance,
			CanonCacheSQL: canon, Checks: checks,
			CandidateFamilyReadyForThisRow: hasFinance && hasCanon && len(rowMismatches) == 0,
		})
	}

	financeExtra := extras(financeRefs, rowTickers)
	canonExtra := extras(canonRefs, rowTickers)
	readyRows := 0
	for _, row := range comparisons {
		if row.CandidateFamilyReadyForThisRow {
			readyRows++
		}
	}
	summary := Summary{
		MarkdownRows: len(rows), FinanceSQLRows: len(financeRefs), CanonCacheTickers: len(canonRefs),
		ReadyRows: readyRows, MismatchRows: len(mismatches), MissingFinanceRows: len(missingFinance),
		MissingCanonRows: len(missingCanon), FinanceExtraRows: len(financeExtra), CanonExtraRows: len(canonExtra),
	}
	status := "phase2_parity_not_ready"
	if summary.MarkdownRows > 0 && summary.MarkdownRows == summary.FinanceSQLRows && summary.MarkdownRows == summary.CanonCacheTickers &&
		summary.MismatchRows == 0 && summary.MissingFinanceRows == 0 && summary.MissingCanonRows == 0 {
		status = "phase2_parity_green_for_entry_stop_reference_metadata"
	}
	return Report{
		SchemaVersion: schemaVersion, GeneratedAtUTC: reporting.UTCNow(), Status: status,
		SQLiteDriver:      driver,
		AuthorityBoundary: "report_only_markdown_to_sql_parity_no_sql_writes_no_markdown_mutation_no_consumer_migration_no_recommendation_deployment_execution_or_customer_authority",
		CandidateFieldFamily: FieldFamily{
			Name: "entry_stop_reference_metadata", SourceOwnerNote: "03. Portfolio/Execution Board.md",
			FinanceSQLView:  "tmp/finance-intelligence-state.sqlite:latest_valid_entry_stop_refs",
			CanonCacheTable: "tmp/veritas-canon-cache.sqlite:canon_cache_fields",
			IncludedFields:  []string{"reference_price_low", "reference_price_high", "reference_invalidation_level"},
			ExcludedFields:  []string{"lane", "action_state", "technical_posture", "blocker_condition", "authority_note", "sizing", "sleeve", "cash", "order_terms"},
		},
		SourceNote: SourceNote{Path: "03. Portfolio/Execution Board.md", SHA256: fileSHA256(boardPath)},
		Summary:    summary, MissingFinanceTickers: missingFinance, MissingCanonTickers: missingCanon,
		FinanceExtraTickers: financeExtra, CanonExtraTickers: canonExtra, Mismatches: mismatches,
		BlockedFieldObservations: blocked, Comparisons: comparisons,
		NextRequiredGates: []string{
			"Add bidirectional drift validator that fails on SQL-only or Markdown-only changes.",
			"Run production consumer A/B proof with SQL-first optional read and Markdown fallback.",
			"Prepare exact field-family promotion decision packet before any source-of-truth promotion.",
		},
	}
}

func parseExecutionBoard(path string) ([]ExecutionRow, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	rows := []ExecutionRow{}
	inTable := false
	for idx, line := range strings.Split(string(bytes), "\n") {
		lineNumber := idx + 1
		if strings.HasPrefix(line, "| Ticker | Lane | Action state | Close/date | Band | Stop |") {
			inTable = true
			continue
		}
		if !inTable {
			continue
		}
		if strings.HasPrefix(line, "|---") {
			continue
		}
		if !strings.HasPrefix(line, "|") {
			break
		}
		cells := splitMarkdownRow(line)
		if len(cells) < 10 {
			continue
		}
		closeValue, closeDate := parseClose(cells[3])
		bandLow, bandHigh := parseBand(cells[4])
		rows = append(rows, ExecutionRow{
			Ticker: strings.ToUpper(stripMarkdown(cells[0])), Lane: stripMarkdown(cells[1]),
			ActionState: stripMarkdown(cells[2]), Close: closeValue, CloseDate: closeDate,
			BandLow: bandLow, BandHigh: bandHigh, Stop: parseNumber(cells[5]),
			TechnicalPosture: stripMarkdown(cells[6]), BlockerCondition: stripMarkdown(cells[7]),
			AuthorityNote: stripMarkdown(cells[8]), SourceFreshness: stripMarkdown(cells[9]),
			LineNumber: lineNumber,
		})
	}
	return rows, nil
}

func loadFinanceRefs(driver, sqlitePath, dbPath string) (map[string]map[string]any, error) {
	if _, err := os.Stat(dbPath); err != nil {
		return map[string]map[string]any{}, nil
	}
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT ticker, entry_band_low, entry_band_high, stop_or_invalidation, band_source, stop_source, freshness_status, validation_status, owner_note_path, source_artifact_path, source_artifact_hash, source_timestamp FROM latest_valid_entry_stop_refs")
	if err != nil {
		return nil, err
	}
	out := map[string]map[string]any{}
	for _, row := range rows {
		ticker, _ := row["ticker"].(string)
		if ticker != "" {
			out[strings.ToUpper(ticker)] = row
		}
	}
	return out, nil
}

func loadCanonRefs(driver, sqlitePath, dbPath string) (map[string]map[string]map[string]any, error) {
	if _, err := os.Stat(dbPath); err != nil {
		return map[string]map[string]map[string]any{}, nil
	}
	rows, err := sqlutil.JSONRowsWithDriver(driver, sqlitePath, dbPath, "SELECT scope, field_name, field_value, authority_boundary, validator_status, freshness_status, reconciliation_status, owner_mirror_note_path, source_artifact_hash FROM canon_cache_fields WHERE field_name IN ('reference_invalidation_level','reference_price_high','reference_price_low')")
	if err != nil {
		return nil, err
	}
	out := map[string]map[string]map[string]any{}
	for _, row := range rows {
		scope, _ := row["scope"].(string)
		field, _ := row["field_name"].(string)
		if scope == "" || field == "" {
			continue
		}
		ticker := strings.ToUpper(scope)
		if _, ok := out[ticker]; !ok {
			out[ticker] = map[string]map[string]any{}
		}
		out[ticker][field] = row
	}
	return out, nil
}

func Validate(report Report) error {
	if report.SourceOfTruthPromotionAllowedByThisArtifact || report.SQLFirstConsumerMigrationAllowed || report.SQLWritesAllowed ||
		report.MarkdownMutationAllowed || report.PortfolioMutationAllowed || report.OwnerApprovalInferred ||
		report.RecommendationOrDeploymentAuthorityAllowed || report.PaperOrLiveExecutionAllowed || report.CustomerOrExternalDeliveryAllowed {
		return errors.New("authority false flag widened")
	}
	if report.Summary.MarkdownRows == 0 {
		return errors.New("no execution board rows parsed")
	}
	if report.Status != "phase2_parity_green_for_entry_stop_reference_metadata" {
		return errors.New("parity not ready")
	}
	return nil
}

func splitMarkdownRow(line string) []string {
	raw := strings.Split(strings.Trim(strings.TrimSpace(line), "|"), "|")
	cells := make([]string, 0, len(raw))
	for _, cell := range raw {
		cells = append(cells, strings.TrimSpace(cell))
	}
	return cells
}

func stripMarkdown(value string) string {
	value = strings.ReplaceAll(value, "**", "")
	value = strings.ReplaceAll(value, "__", "")
	return strings.Join(strings.Fields(value), " ")
}

func parseNumber(value string) *float64 {
	match := numberPattern.FindString(strings.ReplaceAll(value, ",", ""))
	if match == "" {
		return nil
	}
	parsed, err := strconv.ParseFloat(match, 64)
	if err != nil {
		return nil
	}
	return &parsed
}

func parseClose(value string) (*float64, *string) {
	clean := stripMarkdown(value)
	match := closePattern.FindStringSubmatch(clean)
	if len(match) == 3 {
		parsed, err := strconv.ParseFloat(match[1], 64)
		if err == nil {
			date := match[2]
			return &parsed, &date
		}
	}
	return parseNumber(clean), nil
}

func parseBand(value string) (*float64, *float64) {
	clean := strings.ReplaceAll(stripMarkdown(value), " to ", "-")
	match := bandPattern.FindStringSubmatch(clean)
	if len(match) != 3 {
		return nil, nil
	}
	low, lowErr := strconv.ParseFloat(match[1], 64)
	high, highErr := strconv.ParseFloat(match[2], 64)
	if lowErr != nil || highErr != nil {
		return nil, nil
	}
	return &low, &high
}

func closeEnough(left *float64, right any) bool {
	if left == nil || right == nil {
		return left == nil && right == nil
	}
	rightValue, ok := numericAny(right)
	if !ok {
		return false
	}
	diff := *left - rightValue
	if diff < 0 {
		diff = -diff
	}
	return diff <= tolerance
}

func numericAny(value any) (float64, bool) {
	switch typed := value.(type) {
	case float64:
		return typed, true
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case string:
		parsed, err := strconv.ParseFloat(typed, 64)
		return parsed, err == nil
	default:
		return 0, false
	}
}

func lookupAny(row map[string]any, key string) any {
	if row == nil {
		return nil
	}
	return row[key]
}

func lookupNested(row map[string]map[string]any, key, nested string) any {
	if row == nil {
		return nil
	}
	if value, ok := row[key]; ok {
		return value[nested]
	}
	return nil
}

func sortedBoolKeys(values map[string]bool) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func extras[T any](values map[string]T, rowTickers map[string]bool) []string {
	out := []string{}
	for ticker := range values {
		if !rowTickers[ticker] {
			out = append(out, ticker)
		}
	}
	sort.Strings(out)
	return out
}

func fileSHA256(path string) string {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(bytes)
	return hex.EncodeToString(sum[:])
}
