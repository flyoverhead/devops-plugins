#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Wren Okafor" GIT_AUTHOR_EMAIL="wren@example.org"
export GIT_COMMITTER_NAME="Wren Okafor" GIT_COMMITTER_EMAIL="wren@example.org"
git init -q -b main
git config core.hooksPath /dev/null

printf 'module example.org/ledgerlib\n\ngo 1.23\n' > go.mod

cat > amount.go <<'GO'
// Package ledgerlib converts between integer cent amounts and their decimal text form.
package ledgerlib

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
)

var ErrAmount = errors.New("ledgerlib: malformed amount")

// Format renders an amount in cents as decimal text with exactly two fraction digits,
// for example 1205 -> "12.05" and -340 -> "-3.40". Parse is its inverse for every int64.
func Format(cents int64) string {
	whole := cents / 100
	frac := cents % 100
	if frac < 0 {
		frac = -frac
	}
	return fmt.Sprintf("%d.%02d", whole, frac)
}

// Parse reads decimal text of the kind Format produces; malformed text returns ErrAmount.
func Parse(s string) (int64, error) {
	neg := strings.HasPrefix(s, "-")
	body := strings.TrimPrefix(s, "-")
	w, f, ok := strings.Cut(body, ".")
	if !ok || len(f) != 2 || w == "" {
		return 0, ErrAmount
	}
	for _, part := range []string{w, f} {
		for _, r := range part {
			if r < '0' || r > '9' {
				return 0, ErrAmount
			}
		}
	}
	whole, err := strconv.ParseUint(w, 10, 64)
	if err != nil {
		return 0, ErrAmount
	}
	frac, _ := strconv.ParseUint(f, 10, 64)
	if whole > (1<<63)/100 {
		return 0, ErrAmount
	}
	total := whole*100 + frac
	limit := uint64(1<<63 - 1)
	if neg {
		limit++
	}
	if total > limit {
		return 0, ErrAmount
	}
	if neg {
		return -int64(total), nil
	}
	return int64(total), nil
}
GO

cat > amount_test.go <<'GO'
package ledgerlib

import "testing"

func TestFormatExample(t *testing.T) {
	if got := Format(1205); got != "12.05" {
		t.Fatalf("Format(1205) = %q", got)
	}
}
GO

gofmt -l . | grep . && exit 1
git add -A
git commit -q -m "ledgerlib: first import"
