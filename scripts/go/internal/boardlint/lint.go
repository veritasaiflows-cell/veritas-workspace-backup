package boardlint

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_execution_board_structural_lint.v1"

type Options struct {
	Root      string
	BoardPath string
}

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   any    `json:"detail,omitempty"`
	Line     int    `json:"line,omitempty"`
}

func (f Finding) IsOK() bool {
	return f.OK
}

func (f Finding) FindingSeverity() string {
	return f.Severity
}

type Table struct {
	HeaderLine int      `json:"header_line"`
	Headers    []string `json:"headers"`
	RowCount   int      `json:"row_count"`
}

type TickerRow struct {
	Ticker    string   `json:"ticker"`
	Line      int      `json:"line"`
	BandLow   *float64 `json:"band_low,omitempty"`
	BandHigh  *float64 `json:"band_high,omitempty"`
	Stop      *float64 `json:"stop,omitempty"`
	HasBand   bool     `json:"has_band"`
	HasStop   bool     `json:"has_stop"`
	TableLine int      `json:"table_line"`
}

type Summary struct {
	Checks               int  `json:"checks"`
	Critical             int  `json:"critical"`
	Warnings             int  `json:"warnings"`
	RequiredHeaders      int  `json:"required_headers"`
	RequiredHeadersOK    int  `json:"required_headers_ok"`
	OptionalHeaders      int  `json:"optional_headers"`
	OptionalHeadersOK    int  `json:"optional_headers_ok"`
	TableCount           int  `json:"table_count"`
	TickerRowCount       int  `json:"ticker_row_count"`
	MalformedTickerRows  int  `json:"malformed_ticker_rows"`
	NumericFieldFailures int  `json:"numeric_field_failures"`
	ThinSurface          bool `json:"thin_surface"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	BoardPath         string          `json:"board_path"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Tables            []Table         `json:"tables"`
	TickerRows        []TickerRow     `json:"ticker_rows"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

var (
	tickerPattern = regexp.MustCompile(`^[A-Z][A-Z0-9.-]{0,9}$`)
	numberPattern = regexp.MustCompile(`-?\d+(?:\.\d+)?`)
	bandPattern   = regexp.MustCompile(`(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)`)
)

func Run(opts Options) Report {
	root := defaulted(opts.Root, ".")
	boardRel := defaulted(opts.BoardPath, filepath.Join("03. Portfolio", "Execution Board.md"))
	boardPath := resolve(root, boardRel)
	findings := []Finding{}
	add := func(check, severity string, ok bool, detail any, line int) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(boardRel),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
			Line:     line,
		})
	}

	bytes, err := os.ReadFile(boardPath)
	if err != nil {
		add("board_readable", "critical", false, err.Error(), 0)
		base := reporting.SummarizeFindings(findings)
		return report(root, boardRel, nil, nil, findings, Summary{
			Checks:   base.Checks,
			Critical: base.Critical,
			Warnings: base.Warnings,
		})
	}
	add("board_readable", "info", true, "", 0)
	text := string(bytes)
	lines := strings.Split(text, "\n")

	requiredHeaders := []string{"# Execution Board", "## Purpose", "## Current Route", "## Owner Boundary"}
	requiredOK := 0
	for _, header := range requiredHeaders {
		line := lineContaining(lines, header)
		ok := line > 0
		if ok {
			requiredOK++
		}
		add("required_header:"+header, "critical", ok, "", line)
	}
	optionalHeaders := []string{"## Human Policy Notes", "## Historical Trail"}
	optionalOK := 0
	for _, header := range optionalHeaders {
		line := lineContaining(lines, header)
		ok := line > 0
		if ok {
			optionalOK++
		}
		add("optional_header:"+header, "warning", ok, "recommended human-context section is missing", line)
	}

	thinSurface := strings.Contains(text, "THIN HUMAN SURFACE")
	add("canonical_thin_surface_marker", "critical", thinSurface, "missing THIN HUMAN SURFACE marker", 0)
	add("canonical_structured_owner_declared", "critical", strings.Contains(text, "Structured owner:"), "missing structured owner declaration", 0)
	add("canonical_authority_boundary_declared", "critical", strings.Contains(text, "Authority:"), "missing authority declaration", 0)
	lower := strings.ToLower(text)
	for _, phrase := range []string{"no owner approval", "portfolio mutation", "order authority", "execution"} {
		add("canonical_authority_phrase:"+phrase, "critical", strings.Contains(lower, phrase), "canonical boundary phrase missing", 0)
	}

	tables, rows, malformedRows, numericFailures := parseTables(lines, add)
	if len(tables) == 0 && !thinSurface {
		add("canonical_table_or_thin_surface_present", "critical", false, "no ticker table and no canonical thin surface", 0)
	} else {
		add("canonical_table_or_thin_surface_present", "info", true, "", 0)
	}
	if len(tables) == 0 && thinSurface {
		add("thin_surface_without_live_ticker_table", "info", true, "structured SQL/JSON packets own live ticker rows", 0)
	}

	base := reporting.SummarizeFindings(findings)
	return report(root, boardRel, tables, rows, findings, Summary{
		Checks:               base.Checks,
		Critical:             base.Critical,
		Warnings:             base.Warnings,
		RequiredHeaders:      len(requiredHeaders),
		RequiredHeadersOK:    requiredOK,
		OptionalHeaders:      len(optionalHeaders),
		OptionalHeadersOK:    optionalOK,
		TableCount:           len(tables),
		TickerRowCount:       len(rows),
		MalformedTickerRows:  malformedRows,
		NumericFieldFailures: numericFailures,
		ThinSurface:          thinSurface,
	})
}

func report(root, boardRel string, tables []Table, rows []TickerRow, findings []Finding, summary Summary) Report {
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(summary.Critical, summary.Warnings),
		Root:              filepath.ToSlash(root),
		BoardPath:         filepath.ToSlash(boardRel),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Tables:            tables,
		TickerRows:        rows,
		Findings:          findings,
		Summary:           summary,
		NextSafeAction:    "Use as read-only structural proof only. Repair malformed Execution Board sections in the Markdown owner; do not infer approval, execution, portfolio mutation, or SQL-canon promotion from this lint.",
	}
}

func parseTables(lines []string, add func(string, string, bool, any, int)) ([]Table, []TickerRow, int, int) {
	tables := []Table{}
	rows := []TickerRow{}
	malformedRows := 0
	numericFailures := 0
	for index := 0; index < len(lines); index++ {
		line := strings.TrimSpace(lines[index])
		if !strings.HasPrefix(line, "|") {
			continue
		}
		headers := splitRow(line)
		if !containsNormalized(headers, "ticker") {
			continue
		}
		headerLine := index + 1
		normalized := normalizedHeaders(headers)
		headerIndex := headerIndexMap(normalized)
		required := []string{"ticker", "lane", "action state", "close/date", "band", "stop"}
		for _, header := range required {
			_, ok := headerIndex[header]
			add("table_required_column:"+header, "critical", ok, normalized, headerLine)
		}
		optional := []string{"technical posture", "blocker condition", "authority note", "source freshness"}
		for _, header := range optional {
			_, ok := headerIndex[header]
			add("table_optional_column:"+header, "warning", ok, normalized, headerLine)
		}
		separatorOK := index+1 < len(lines) && isSeparatorRow(lines[index+1])
		add("table_separator_after_header", "critical", separatorOK, "", headerLine+1)
		table := Table{HeaderLine: headerLine, Headers: normalized}
		rowStart := index + 2
		for rowIndex := rowStart; rowIndex < len(lines); rowIndex++ {
			rowLine := strings.TrimSpace(lines[rowIndex])
			if !strings.HasPrefix(rowLine, "|") {
				break
			}
			if isSeparatorRow(rowLine) {
				continue
			}
			cells := splitRow(rowLine)
			if len(cells) != len(headers) {
				malformedRows++
				add("table_row_cell_count_matches_header", "critical", false, map[string]int{"cells": len(cells), "headers": len(headers)}, rowIndex+1)
				continue
			}
			ticker := strings.ToUpper(stripMarkdown(cell(cells, headerIndex, "ticker")))
			if !tickerPattern.MatchString(ticker) {
				malformedRows++
				add("ticker_row_symbol_shape", "critical", false, ticker, rowIndex+1)
			} else {
				add("ticker_row_symbol_shape", "info", true, ticker, rowIndex+1)
			}
			row := TickerRow{Ticker: ticker, Line: rowIndex + 1, TableLine: headerLine}
			if bandText := cell(cells, headerIndex, "band"); meaningful(bandText) {
				row.HasBand = true
				low, high, ok := parseBand(bandText)
				if !ok {
					numericFailures++
				} else {
					row.BandLow = &low
					row.BandHigh = &high
				}
				add("ticker_row_band_numeric_when_present", "critical", ok, bandText, rowIndex+1)
			}
			if stopText := cell(cells, headerIndex, "stop"); meaningful(stopText) {
				row.HasStop = true
				stop, ok := parseNumber(stopText)
				if !ok {
					numericFailures++
				} else {
					row.Stop = &stop
				}
				add("ticker_row_stop_numeric_when_present", "critical", ok, stopText, rowIndex+1)
			}
			for _, optional := range []string{"authority note", "source freshness"} {
				if idx, ok := headerIndex[optional]; ok {
					add("ticker_row_optional_field_present:"+optional, "warning", meaningful(cells[idx]), cells[idx], rowIndex+1)
				}
			}
			rows = append(rows, row)
			table.RowCount++
		}
		tables = append(tables, table)
		index = rowStart + table.RowCount
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Ticker == rows[j].Ticker {
			return rows[i].Line < rows[j].Line
		}
		return rows[i].Ticker < rows[j].Ticker
	})
	return tables, rows, malformedRows, numericFailures
}

func splitRow(line string) []string {
	raw := strings.Split(strings.Trim(strings.TrimSpace(line), "|"), "|")
	out := make([]string, 0, len(raw))
	for _, cell := range raw {
		out = append(out, strings.TrimSpace(cell))
	}
	return out
}

func normalizedHeaders(headers []string) []string {
	out := make([]string, 0, len(headers))
	for _, header := range headers {
		out = append(out, normalizeHeader(header))
	}
	return out
}

func normalizeHeader(value string) string {
	value = strings.ToLower(stripMarkdown(value))
	value = strings.ReplaceAll(value, "\\", "/")
	return strings.Join(strings.Fields(value), " ")
}

func headerIndexMap(headers []string) map[string]int {
	out := map[string]int{}
	for index, header := range headers {
		out[header] = index
	}
	return out
}

func containsNormalized(headers []string, wanted string) bool {
	for _, header := range headers {
		if normalizeHeader(header) == wanted {
			return true
		}
	}
	return false
}

func isSeparatorRow(line string) bool {
	trimmed := strings.Trim(strings.TrimSpace(line), "| ")
	if trimmed == "" {
		return false
	}
	for _, r := range trimmed {
		if r != '-' && r != ':' && r != '|' && r != ' ' {
			return false
		}
	}
	return strings.Contains(trimmed, "-")
}

func cell(cells []string, index map[string]int, header string) string {
	idx, ok := index[header]
	if !ok || idx < 0 || idx >= len(cells) {
		return ""
	}
	return strings.TrimSpace(cells[idx])
}

func stripMarkdown(value string) string {
	replacer := strings.NewReplacer("**", "", "__", "", "`", "", "[", "", "]", "")
	return strings.TrimSpace(replacer.Replace(value))
}

func meaningful(value string) bool {
	clean := strings.ToLower(strings.TrimSpace(stripMarkdown(value)))
	switch clean {
	case "", "-", "n/a", "na", "none", "not set", "tbd":
		return false
	default:
		return true
	}
}

func parseBand(value string) (float64, float64, bool) {
	clean := normalizeNumberText(value)
	clean = strings.ReplaceAll(clean, " to ", "-")
	match := bandPattern.FindStringSubmatch(clean)
	if len(match) != 3 {
		return 0, 0, false
	}
	low, lowErr := strconv.ParseFloat(match[1], 64)
	high, highErr := strconv.ParseFloat(match[2], 64)
	return low, high, lowErr == nil && highErr == nil
}

func parseNumber(value string) (float64, bool) {
	match := numberPattern.FindString(normalizeNumberText(value))
	if match == "" {
		return 0, false
	}
	parsed, err := strconv.ParseFloat(match, 64)
	return parsed, err == nil
}

func normalizeNumberText(value string) string {
	value = stripMarkdown(value)
	value = strings.ReplaceAll(value, ",", "")
	value = strings.ReplaceAll(value, "\u2013", "-")
	value = strings.ReplaceAll(value, "\u2014", "-")
	return value
}

func lineContaining(lines []string, needle string) int {
	for idx, line := range lines {
		if strings.TrimSpace(line) == needle {
			return idx + 1
		}
	}
	return 0
}

func resolve(root, relPath string) string {
	if filepath.IsAbs(relPath) {
		return relPath
	}
	return filepath.Join(root, filepath.FromSlash(relPath))
}

func defaulted(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}
