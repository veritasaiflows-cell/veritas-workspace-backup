package sqlutil

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	_ "modernc.org/sqlite"
)

const (
	DriverCLI       = "cli"
	DriverInProcess = "inprocess"
)

func NormalizeDriver(driver string) string {
	switch strings.ToLower(strings.TrimSpace(driver)) {
	case "", DriverCLI:
		return DriverCLI
	case DriverInProcess:
		return DriverInProcess
	default:
		return strings.ToLower(strings.TrimSpace(driver))
	}
}

func ValidateDriver(driver string) error {
	switch NormalizeDriver(driver) {
	case DriverCLI, DriverInProcess:
		return nil
	default:
		return errors.New("unsupported sqlite driver: " + driver)
	}
}

func Scalar(sqlitePath, dbPath, sql string) (string, error) {
	cmd := exec.Command(sqlitePath, "-readonly", "-noheader", dbPath, sql)
	out, err := cmd.CombinedOutput()
	text := strings.TrimSpace(string(out))
	if err != nil {
		return "", CommandError{text, err}
	}
	lines := strings.Split(text, "\n")
	if len(lines) == 0 {
		return "", nil
	}
	return strings.TrimSpace(lines[0]), nil
}

func JSONRows(sqlitePath, dbPath, sql string) ([]map[string]any, error) {
	cmd := exec.Command(sqlitePath, "-readonly", "-json", dbPath, sql)
	out, err := cmd.CombinedOutput()
	text := strings.TrimSpace(string(out))
	if err != nil {
		return nil, CommandError{text, err}
	}
	if text == "" {
		return nil, nil
	}
	var rows []map[string]any
	if err := json.Unmarshal([]byte(text), &rows); err != nil {
		return nil, err
	}
	return rows, nil
}

func TextRowCount(sqlitePath, dbPath, sql string) (int, error) {
	cmd := exec.Command(sqlitePath, "-readonly", dbPath, sql)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return 0, CommandError{strings.TrimSpace(string(out)), err}
	}
	text := strings.TrimRight(string(out), "\r\n")
	if text == "" {
		return 0, nil
	}
	return len(strings.Split(text, "\n")), nil
}

func TableRowCount(sqlitePath, dbPath, tableName string) (int64, error) {
	value, err := Scalar(sqlitePath, dbPath, "SELECT COUNT(*) FROM "+QuoteIdentifier(tableName))
	if err != nil {
		return 0, err
	}
	return strconv.ParseInt(strings.TrimSpace(value), 10, 64)
}

func ScalarWithDriver(driver, sqlitePath, dbPath, query string) (string, error) {
	switch NormalizeDriver(driver) {
	case DriverInProcess:
		return ScalarInProcess(dbPath, query)
	case DriverCLI:
		return Scalar(sqlitePath, dbPath, query)
	default:
		return "", errors.New("unsupported sqlite driver: " + driver)
	}
}

func JSONRowsWithDriver(driver, sqlitePath, dbPath, query string) ([]map[string]any, error) {
	switch NormalizeDriver(driver) {
	case DriverInProcess:
		return JSONRowsInProcess(dbPath, query)
	case DriverCLI:
		return JSONRows(sqlitePath, dbPath, query)
	default:
		return nil, errors.New("unsupported sqlite driver: " + driver)
	}
}

func TextRowCountWithDriver(driver, sqlitePath, dbPath, query string) (int, error) {
	switch NormalizeDriver(driver) {
	case DriverInProcess:
		return TextRowCountInProcess(dbPath, query)
	case DriverCLI:
		return TextRowCount(sqlitePath, dbPath, query)
	default:
		return 0, errors.New("unsupported sqlite driver: " + driver)
	}
}

func TableRowCountWithDriver(driver, sqlitePath, dbPath, tableName string) (int64, error) {
	switch NormalizeDriver(driver) {
	case DriverInProcess:
		return TableRowCountInProcess(dbPath, tableName)
	case DriverCLI:
		return TableRowCount(sqlitePath, dbPath, tableName)
	default:
		return 0, errors.New("unsupported sqlite driver: " + driver)
	}
}

func QuoteIdentifier(value string) string {
	return `"` + strings.ReplaceAll(value, `"`, `""`) + `"`
}

func ScalarInProcess(dbPath, query string) (string, error) {
	db, err := OpenReadOnlyInProcess(dbPath)
	if err != nil {
		return "", err
	}
	defer db.Close()
	var value any
	if err := db.QueryRow(query).Scan(&value); err != nil {
		return "", err
	}
	return scalarText(value), nil
}

func JSONRowsInProcess(dbPath, query string) ([]map[string]any, error) {
	db, err := OpenReadOnlyInProcess(dbPath)
	if err != nil {
		return nil, err
	}
	defer db.Close()
	rows, err := db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	columns, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	out := []map[string]any{}
	for rows.Next() {
		values := make([]any, len(columns))
		targets := make([]any, len(columns))
		for i := range values {
			targets[i] = &values[i]
		}
		if err := rows.Scan(targets...); err != nil {
			return nil, err
		}
		row := map[string]any{}
		for i, column := range columns {
			row[column] = normalizeValue(values[i])
		}
		out = append(out, row)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

func TextRowCountInProcess(dbPath, query string) (int, error) {
	db, err := OpenReadOnlyInProcess(dbPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	rows, err := db.Query(query)
	if err != nil {
		return 0, err
	}
	defer rows.Close()
	count := 0
	for rows.Next() {
		count++
	}
	if err := rows.Err(); err != nil {
		return 0, err
	}
	return count, nil
}

func TableRowCountInProcess(dbPath, tableName string) (int64, error) {
	value, err := ScalarInProcess(dbPath, "SELECT COUNT(*) FROM "+QuoteIdentifier(tableName))
	if err != nil {
		return 0, err
	}
	return strconv.ParseInt(strings.TrimSpace(value), 10, 64)
}

func WriteProbeInProcess(dbPath string) error {
	db, err := OpenReadOnlyInProcess(dbPath)
	if err != nil {
		return err
	}
	defer db.Close()
	_, err = db.Exec("CREATE TABLE veritas_read_only_probe(id INTEGER)")
	return err
}

func OpenReadOnlyInProcess(dbPath string) (*sql.DB, error) {
	abs, err := filepath.Abs(dbPath)
	if err != nil {
		return nil, err
	}
	path := filepath.ToSlash(abs)
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	db, err := sql.Open("sqlite", "file:"+path+"?mode=ro&cache=shared")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	for _, pragma := range []string{
		"PRAGMA query_only=ON",
		"PRAGMA foreign_keys=ON",
		"PRAGMA busy_timeout=5000",
	} {
		if _, err := db.Exec(pragma); err != nil {
			db.Close()
			return nil, err
		}
	}
	return db, nil
}

func scalarText(value any) string {
	switch typed := value.(type) {
	case nil:
		return ""
	case []byte:
		return string(typed)
	case int64:
		return strconv.FormatInt(typed, 10)
	case float64:
		return strconv.FormatFloat(typed, 'f', -1, 64)
	case bool:
		if typed {
			return "1"
		}
		return "0"
	default:
		return fmt.Sprint(typed)
	}
}

func normalizeValue(value any) any {
	if bytes, ok := value.([]byte); ok {
		return string(bytes)
	}
	return value
}

type CommandError struct {
	Output string
	Err    error
}

func (e CommandError) Error() string {
	if e.Output == "" {
		return e.Err.Error()
	}
	return e.Err.Error() + ": " + e.Output
}
