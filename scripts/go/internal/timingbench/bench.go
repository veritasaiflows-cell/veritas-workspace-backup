package timingbench

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"time"

	"veritas.local/wf74/internal/reporting"
)

const SchemaVersion = "go_validator_timing_benchmark.v1"

type CommandRunner func(ctx context.Context, path string, args []string) CommandResult

type Options struct {
	Root        string
	BinaryDir   string
	Validators  []string
	InspectOnly bool
	Timeout     time.Duration
	Runner      CommandRunner
}

type ValidatorSpec struct {
	Name string   `json:"name"`
	Args []string `json:"args"`
}

type CommandResult struct {
	ExitCode int
	Output   string
	Err      error
}

type Finding struct {
	Path     string `json:"path"`
	Check    string `json:"check"`
	Severity string `json:"severity"`
	OK       bool   `json:"ok"`
	Detail   any    `json:"detail,omitempty"`
}

func (f Finding) IsOK() bool {
	return f.OK
}

func (f Finding) FindingSeverity() string {
	return f.Severity
}

type Result struct {
	Validator     string   `json:"validator"`
	BinaryPath    string   `json:"binary_path"`
	Status        string   `json:"status"`
	Args          []string `json:"args,omitempty"`
	ElapsedMS     *float64 `json:"elapsed_ms,omitempty"`
	ExitCode      *int     `json:"exit_code,omitempty"`
	SizeBytes     *int64   `json:"size_bytes,omitempty"`
	ModifiedAtUTC string   `json:"modified_at_utc,omitempty"`
	OutputPreview string   `json:"output_preview,omitempty"`
	Error         string   `json:"error,omitempty"`
}

type Summary struct {
	Checks             int      `json:"checks"`
	Critical           int      `json:"critical"`
	Warnings           int      `json:"warnings"`
	ValidatorCount     int      `json:"validator_count"`
	ExecutedCount      int      `json:"executed_count"`
	InspectedCount     int      `json:"inspected_count"`
	MissingCount       int      `json:"missing_count"`
	FailedCount        int      `json:"failed_count"`
	MaxElapsedMS       *float64 `json:"max_elapsed_ms,omitempty"`
	UnsafeRequestCount int      `json:"unsafe_request_count"`
}

type Report struct {
	SchemaVersion     string          `json:"schema_version"`
	GeneratedAtUTC    string          `json:"generated_at_utc"`
	Status            string          `json:"status"`
	Root              string          `json:"root"`
	BinaryDir         string          `json:"binary_dir"`
	InspectOnly       bool            `json:"inspect_only"`
	TimeoutMS         int64           `json:"timeout_ms"`
	AuthorityBoundary map[string]bool `json:"authority_boundary"`
	Allowlist         []ValidatorSpec `json:"allowlist"`
	Results           []Result        `json:"results"`
	Findings          []Finding       `json:"findings"`
	Summary           Summary         `json:"summary"`
	NextSafeAction    string          `json:"next_safe_action"`
}

var safeNamePattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9-]*$`)

var defaultSpecs = map[string]ValidatorSpec{
	"go-json-proof-contract-lint": {
		Name: "go-json-proof-contract-lint",
		Args: []string{"--root", "{root}"},
	},
	"go-sql-canon-proof-bundle-lint": {
		Name: "go-sql-canon-proof-bundle-lint",
		Args: []string{"--root", "{root}"},
	},
	"go-validator-route-budget-lint": {
		Name: "go-validator-route-budget-lint",
		Args: []string{"--root", "{root}", "--allow-timing-warnings"},
	},
}

func Run(opts Options) Report {
	root := strings.TrimSpace(opts.Root)
	if root == "" {
		root = "."
	}
	binaryDir := strings.TrimSpace(opts.BinaryDir)
	if binaryDir == "" {
		binaryDir = filepath.Join(root, "scripts", "go", "bin")
	}
	timeout := opts.Timeout
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	runner := opts.Runner
	if runner == nil {
		runner = defaultRunner
	}

	validators := append([]string{}, opts.Validators...)
	if len(validators) == 0 {
		for name := range defaultSpecs {
			validators = append(validators, name)
		}
		sort.Strings(validators)
	}

	findings := []Finding{}
	add := func(path, check, severity string, ok bool, detail any) {
		findings = append(findings, Finding{
			Path:     filepath.ToSlash(path),
			Check:    check,
			Severity: severity,
			OK:       ok,
			Detail:   detail,
		})
	}

	results := []Result{}
	executed := 0
	inspected := 0
	missing := 0
	failed := 0
	unsafe := 0
	var maxElapsed *float64

	for _, requested := range validators {
		name := strings.TrimSpace(requested)
		spec, allowed := defaultSpecs[name]
		if !allowed || !safeValidatorName(name) {
			unsafe++
			add(name, "validator_allowlisted", "critical", false, "validator is not in the fixed Go read-only allowlist")
			results = append(results, Result{Validator: name, Status: "blocked", Error: "validator is not allowlisted"})
			continue
		}
		add(name, "validator_allowlisted", "info", true, "")
		binaryPath, stat, err := resolveBinary(binaryDir, name)
		result := Result{
			Validator:  name,
			BinaryPath: filepath.ToSlash(binaryPath),
			Status:     "ok",
			Args:       formatArgs(spec.Args, root),
		}
		if err != nil {
			missing++
			result.Status = "missing"
			result.Error = err.Error()
			add(name, "binary_exists", "warning", false, err.Error())
			results = append(results, result)
			continue
		}
		size := stat.Size()
		result.SizeBytes = &size
		result.ModifiedAtUTC = stat.ModTime().UTC().Format(time.RFC3339)
		add(name, "binary_exists", "info", true, filepath.ToSlash(binaryPath))
		if opts.InspectOnly {
			inspected++
			results = append(results, result)
			continue
		}

		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		started := time.Now()
		command := runner(ctx, binaryPath, result.Args)
		cancel()
		elapsed := float64(time.Since(started).Microseconds()) / 1000.0
		exitCode := command.ExitCode
		result.ElapsedMS = &elapsed
		result.ExitCode = &exitCode
		result.OutputPreview = preview(command.Output, 600)
		if maxElapsed == nil || elapsed > *maxElapsed {
			value := elapsed
			maxElapsed = &value
		}
		executed++
		if command.Err != nil || command.ExitCode != 0 {
			failed++
			result.Status = "warning"
			result.Error = errorText(command.Err)
			add(name, "validator_process_completed_zero", "warning", false, map[string]any{
				"exit_code": command.ExitCode,
				"error":     errorText(command.Err),
			})
		} else {
			add(name, "validator_process_completed_zero", "info", true, map[string]any{"elapsed_ms": elapsed})
		}
		results = append(results, result)
	}

	base := reporting.SummarizeFindings(findings)
	return Report{
		SchemaVersion:     SchemaVersion,
		GeneratedAtUTC:    reporting.UTCNow(),
		Status:            reporting.StatusFromCounts(base.Critical, base.Warnings),
		Root:              filepath.ToSlash(root),
		BinaryDir:         filepath.ToSlash(binaryDir),
		InspectOnly:       opts.InspectOnly,
		TimeoutMS:         timeout.Milliseconds(),
		AuthorityBoundary: reporting.ReadOnlyAuthorityBoundary(),
		Allowlist:         sortedAllowlist(),
		Results:           results,
		Findings:          findings,
		Summary: Summary{
			Checks:             base.Checks,
			Critical:           base.Critical,
			Warnings:           base.Warnings,
			ValidatorCount:     len(validators),
			ExecutedCount:      executed,
			InspectedCount:     inspected,
			MissingCount:       missing,
			FailedCount:        failed,
			MaxElapsedMS:       maxElapsed,
			UnsafeRequestCount: unsafe,
		},
		NextSafeAction: "Use as read-only timing evidence only. Add validators to the allowlist deliberately; do not execute shell strings, Python commands, cron jobs, SQL writers, or brokerage actions from this benchmark.",
	}
}

func safeValidatorName(name string) bool {
	if !safeNamePattern.MatchString(name) {
		return false
	}
	return !strings.ContainsAny(name, `/\.:`)
}

func resolveBinary(binaryDir, name string) (string, os.FileInfo, error) {
	candidates := []string{name}
	if runtime.GOOS == "windows" {
		candidates = []string{name + ".exe", name}
	}
	for _, candidate := range candidates {
		path := filepath.Join(binaryDir, candidate)
		stat, err := os.Stat(path)
		if err == nil && !stat.IsDir() {
			return path, stat, nil
		}
	}
	return filepath.Join(binaryDir, candidates[0]), nil, errors.New("allowlisted binary not found")
}

func formatArgs(args []string, root string) []string {
	out := make([]string, 0, len(args))
	for _, arg := range args {
		out = append(out, strings.ReplaceAll(arg, "{root}", root))
	}
	return out
}

func defaultRunner(ctx context.Context, path string, args []string) CommandResult {
	cmd := exec.CommandContext(ctx, path, args...)
	out, err := cmd.CombinedOutput()
	exitCode := 0
	if err != nil {
		exitCode = 1
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			exitCode = exitErr.ExitCode()
		}
		if ctx.Err() != nil {
			err = fmt.Errorf("%w: %v", ctx.Err(), err)
		}
	}
	return CommandResult{ExitCode: exitCode, Output: string(out), Err: err}
}

func sortedAllowlist() []ValidatorSpec {
	names := make([]string, 0, len(defaultSpecs))
	for name := range defaultSpecs {
		names = append(names, name)
	}
	sort.Strings(names)
	out := make([]ValidatorSpec, 0, len(names))
	for _, name := range names {
		out = append(out, defaultSpecs[name])
	}
	return out
}

func preview(value string, max int) string {
	value = strings.TrimSpace(value)
	if len(value) <= max {
		return value
	}
	return value[:max] + "...truncated"
}

func errorText(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
