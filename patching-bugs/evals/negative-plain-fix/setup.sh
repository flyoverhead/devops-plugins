#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Dana Mrazek" GIT_AUTHOR_EMAIL="dana@example.org"
export GIT_COMMITTER_NAME="Dana Mrazek" GIT_COMMITTER_EMAIL="dana@example.org"
export GIT_CONFIG_COUNT=0
mkdir -p target
cd target
git init -q -b main
git config core.hooksPath /dev/null
git config commit.gpgsign false
git config tag.gpgsign false
git config user.name "Dana Mrazek"
git config user.email "dana@example.org"
mkdir -p vault cmd/snipvault

cat > go.mod <<'EOF'
module example.org/snipvault

go 1.21
EOF

cat > vault/vault.go <<'EOF'
// Package vault keeps named text snippets as files under one directory.
package vault

import (
	"errors"
	"os"
	"path/filepath"
)

// ErrEmptyName is returned for a blank snippet name.
var ErrEmptyName = errors.New("vault: empty snippet name")

// Vault stores snippets under Dir. Names may contain folders, e.g. "go/http.txt".
type Vault struct {
	Dir string
}

// Save writes body as the snippet called name, creating folders as needed.
func (v Vault) Save(name string, body []byte) error {
	if name == "" {
		return ErrEmptyName
	}
	p := filepath.Join(v.Dir, name)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	return os.WriteFile(p, body, 0o644)
}

// Load returns the snippet called name.
func (v Vault) Load(name string) ([]byte, error) {
	if name == "" {
		return nil, ErrEmptyName
	}
	return os.ReadFile(filepath.Join(v.Dir, name))
}
EOF

cat > vault/vault_test.go <<'EOF'
package vault

import "testing"

func TestSaveThenLoadNested(t *testing.T) {
	v := Vault{Dir: t.TempDir()}
	if err := v.Save("go/http.txt", []byte("http.ListenAndServe")); err != nil {
		t.Fatal(err)
	}
	got, err := v.Load("go/http.txt")
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "http.ListenAndServe" {
		t.Fatalf("got %q", got)
	}
}

func TestEmptyName(t *testing.T) {
	v := Vault{Dir: t.TempDir()}
	if err := v.Save("", nil); err != ErrEmptyName {
		t.Fatalf("got %v", err)
	}
}
EOF

cat > cmd/snipvault/main.go <<'EOF'
// Command snipvault saves and prints text snippets kept under $SNIPVAULT_HOME.
//
//	snipvault save NAME < body.txt
//	snipvault show NAME
package main

import (
	"fmt"
	"io"
	"os"

	"example.org/snipvault/vault"
)

func fail(code int, format string, args ...any) {
	fmt.Fprintf(os.Stderr, "snipvault: "+format+"\n", args...)
	os.Exit(code)
}

func main() {
	home := os.Getenv("SNIPVAULT_HOME")
	if home == "" {
		fail(2, "SNIPVAULT_HOME is not set")
	}
	if len(os.Args) != 3 {
		fail(2, "usage: snipvault save|show NAME")
	}
	v := vault.Vault{Dir: home}
	name := os.Args[2]
	switch os.Args[1] {
	case "save":
		body, err := io.ReadAll(os.Stdin)
		if err != nil {
			fail(1, "read stdin: %v", err)
		}
		if err := v.Save(name, body); err != nil {
			fail(1, "save %q: %v", name, err)
		}
	case "show":
		body, err := v.Load(name)
		if err != nil {
			fail(1, "show %q: %v", name, err)
		}
		os.Stdout.Write(body)
	default:
		fail(2, "unknown command %q", os.Args[1])
	}
}
EOF

cat > README.md <<'EOF'
# snipvault

Keeps text snippets as files under `$SNIPVAULT_HOME`. Snippet names may contain folders
(`go/http.txt`).

Build: `go build -o bin/snipvault ./cmd/snipvault`
Test: `go test ./...`
EOF
printf 'bin/\n' > .gitignore
git add -A
git commit -q -m "vault: snippet store and snipvault CLI"
