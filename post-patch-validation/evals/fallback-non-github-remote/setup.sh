#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ines Kowal" GIT_AUTHOR_EMAIL="ines@example.net"
export GIT_COMMITTER_NAME="Ines Kowal" GIT_COMMITTER_EMAIL="ines@example.net"
export GIT_CONFIG_COUNT=0
git init -q -b main
git config core.hooksPath /dev/null
git config commit.gpgsign false
git config tag.gpgsign false
git remote add origin https://forge.example.net/sec/auditlog.git
mkdir -p logline audit cmd/auditcat

cat > go.mod <<'EOF'
module example.net/auditlog

go 1.22
EOF

cat > logline/field.go <<'EOF'
// Package logline prepares values for the key=value audit log.
package logline

// Field returns v ready to be placed inside one audit line.
func Field(v string) string {
	return v
}
EOF

cat > audit/audit.go <<'EOF'
// Package audit writes one key=value line per security-relevant action.
package audit

import (
	"fmt"
	"io"

	"example.net/auditlog/logline"
)

// Entry is one audited action.
type Entry struct {
	Actor  string
	Action string
	Target string
}

// Write appends e to w as a single line.
func Write(w io.Writer, e Entry) error {
	_, err := fmt.Fprintf(w, "actor=%s action=%s target=%s\n",
		logline.Field(e.Actor), logline.Field(e.Action), logline.Field(e.Target))
	return err
}
EOF

cat > audit/audit_test.go <<'EOF'
package audit

import (
	"bytes"
	"testing"
)

func TestWritePlainEntry(t *testing.T) {
	var buf bytes.Buffer
	if err := Write(&buf, Entry{Actor: "mara", Action: "rotate-key", Target: "vault/app"}); err != nil {
		t.Fatal(err)
	}
	want := "actor=mara action=rotate-key target=vault/app\n"
	if buf.String() != want {
		t.Fatalf("got %q, want %q", buf.String(), want)
	}
}
EOF

cat > cmd/auditcat/main.go <<'EOF'
// Command auditcat prints one audit line for the given actor, action and target.
package main

import (
	"fmt"
	"os"

	"example.net/auditlog/audit"
)

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: auditcat ACTOR ACTION TARGET")
		os.Exit(2)
	}
	e := audit.Entry{Actor: os.Args[1], Action: os.Args[2], Target: os.Args[3]}
	if err := audit.Write(os.Stdout, e); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
EOF

printf '# auditlog\n\nKey=value audit trail used by the access broker.\n' > README.md
git add -A
git commit -q -m "audit: key=value writer and auditcat CLI"
git tag vulnerable

cat > logline/field.go <<'EOF'
// Package logline prepares values for the key=value audit log.
package logline

import "strings"

// Field returns v ready to be placed inside one audit line. A line break in a
// value would let the caller start a forged entry, so it is written escaped.
func Field(v string) string {
	return strings.Replace(v, "\n", `\n`, 1)
}
EOF

cat > logline/field_test.go <<'EOF'
package logline

import "testing"

func TestFieldEscapesLineBreak(t *testing.T) {
	got := Field("mara\nactor=root action=grant target=prod")
	if got != `mara\nactor=root action=grant target=prod` {
		t.Fatalf("line break kept: %q", got)
	}
}
EOF
git add -A
git commit -q -m "logline: escape line breaks in audit fields (AUD-212)" \
  -m "A newline in the actor let a caller append a forged audit entry. PR #41."
