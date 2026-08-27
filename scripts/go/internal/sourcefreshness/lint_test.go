package sourcefreshness

import (
	"os"
	"path/filepath"
	"testing"
)

func TestThinHumanSurfacePolicySource(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "Execution Board.md")
	content := `<!-- THIN HUMAN SURFACE
Structured owner: state/finance/finance-canon.sqlite plus generated/read-only proof packets.
-->
# Execution Board
`
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	if !thinHumanSurfacePolicySource(path) {
		t.Fatalf("expected thin human surface marker to exempt %s", path)
	}
}

func TestThinHumanSurfacePolicySourceRequiresStructuredOwner(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "Loose Note.md")
	if err := os.WriteFile(path, []byte("THIN HUMAN SURFACE without owner"), 0o600); err != nil {
		t.Fatal(err)
	}
	if thinHumanSurfacePolicySource(path) {
		t.Fatalf("expected missing SQL structured owner to avoid exemption")
	}
}
