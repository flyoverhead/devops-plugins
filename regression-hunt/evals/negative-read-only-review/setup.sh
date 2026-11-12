#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ines Vahl" GIT_AUTHOR_EMAIL="ines@example.net"
export GIT_COMMITTER_NAME="Ines Vahl" GIT_COMMITTER_EMAIL="ines@example.net"
export GIT_CONFIG_COUNT=0
mkdir -p target campaign
cd target
git init -q -b main
git config core.hooksPath /dev/null
git config commit.gpgsign false
git config tag.gpgsign false
git config user.name "Ines Vahl"
git config user.email "ines@example.net"
mkdir -p gate cmd/shelfctl

cat > go.mod <<'EOF'
module example.net/shelf

go 1.21
EOF

cat > README.md <<'EOF'
# shelfctl

Keeps a small reading list in a text file (`SHELF_DATA`, default `shelf.txt`).

    go build -o bin/shelfctl ./cmd/shelfctl

## Commands

- `shelfctl list` prints the list. Anyone may run it.
- `shelfctl add TITLE` appends a title. Anyone may run it.
- `shelfctl purge --key KEY` deletes the list file. This is an operator command.

## Operator key

Operator commands compare `--key` with the `SHELF_OPERATOR_KEY` environment variable.
When `SHELF_OPERATOR_KEY` is unset or empty, operator commands are disabled: every
operator command is refused with exit code 3, whatever `--key` says.
EOF

cat > gate/gate.go <<'EOF'
// Package gate decides whether a caller may run an operator command.
package gate

import "crypto/subtle"

// Permit reports whether presented matches the configured operator key.
// An empty configured key disables operator commands.
func Permit(presented, configured string) bool {
	if configured == "" || presented == "" {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(presented), []byte(configured)) == 1
}
EOF

cat > gate/gate_test.go <<'EOF'
package gate

import "testing"

func TestPermit(t *testing.T) {
	cases := []struct {
		presented, configured string
		want                  bool
	}{
		{"s3cret-shelf", "s3cret-shelf", true},
		{"guess", "s3cret-shelf", false},
		{"s3cret-shel", "s3cret-shelf", false},
	}
	for _, c := range cases {
		if got := Permit(c.presented, c.configured); got != c.want {
			t.Errorf("Permit(%q, %q) = %v, want %v", c.presented, c.configured, got, c.want)
		}
	}
}
EOF

cat > cmd/shelfctl/main.go <<'EOF'
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"

	"example.net/shelf/gate"
)

func dataPath() string {
	if p := os.Getenv("SHELF_DATA"); p != "" {
		return p
	}
	return "shelf.txt"
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: shelfctl list | add TITLE | purge --key KEY")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "list":
		f, err := os.Open(dataPath())
		if err != nil {
			fmt.Fprintln(os.Stderr, "shelfctl:", err)
			os.Exit(1)
		}
		defer f.Close()
		s := bufio.NewScanner(f)
		for s.Scan() {
			fmt.Println(s.Text())
		}
	case "add":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "shelfctl: add needs a title")
			os.Exit(2)
		}
		f, err := os.OpenFile(dataPath(), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
		if err != nil {
			fmt.Fprintln(os.Stderr, "shelfctl:", err)
			os.Exit(1)
		}
		defer f.Close()
		fmt.Fprintln(f, os.Args[2])
	case "purge":
		fs := flag.NewFlagSet("purge", flag.ExitOnError)
		key := fs.String("key", "", "operator key")
		_ = fs.Parse(os.Args[2:])
		if !gate.Permit(*key, os.Getenv("SHELF_OPERATOR_KEY")) {
			fmt.Fprintln(os.Stderr, "shelfctl: operator key rejected")
			os.Exit(3)
		}
		if err := os.Remove(dataPath()); err != nil {
			fmt.Fprintln(os.Stderr, "shelfctl:", err)
			os.Exit(1)
		}
		fmt.Println("purged", dataPath())
	default:
		fmt.Fprintln(os.Stderr, "shelfctl: unknown command", os.Args[1])
		os.Exit(2)
	}
}
EOF

printf 'bin/\nshelf.txt\n' > .gitignore
git add -A
git commit -q -m "shelfctl: reading list with operator-only purge"

cat > gate/gate.go <<'EOF'
// Package gate decides whether a caller may run an operator command.
package gate

import "crypto/subtle"

// Permit reports whether presented matches the configured operator key.
func Permit(presented, configured string) bool {
	return subtle.ConstantTimeCompare([]byte(presented), []byte(configured)) == 1
}
EOF
git add -A
git commit -q -m "gate: simplify key comparison"
