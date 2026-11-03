#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module github.com/example/demo\n\ngo 1.25\n' > go.mod
cat > parse.go <<'GO'
package demo

import "strings"

func ParseLine(s string) []string {
	var out []string
	for _, f := range strings.Split(s, ",") {
		out = append(out, strings.TrimSpace(f))
	}
	return out
}
GO
