#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Tomasz Weir" GIT_AUTHOR_EMAIL="tomasz@example.org"
export GIT_COMMITTER_NAME="Tomasz Weir" GIT_COMMITTER_EMAIL="tomasz@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p pkg/shelf

printf 'module example.org/pantry\n\ngo 1.23\n' > go.mod

cat > pkg/shelf/life.go <<'GO'
// Package shelf decides what a shop may still put on the shelf.
package shelf

// MaxGrace caps the grace period a store may configure.
const MaxGrace = 14

// Sellable reports whether an item may be sold on day today (days since epoch).
// Recalled items never are; others stay sellable through bestBefore+grace inclusive.
func Sellable(bestBefore, grace, today int, recalled bool) bool {
	if recalled {
		return false
	}
	return today <= bestBefore+grace
}

// DaysLeft is the number of days until the item stops being sellable.
func DaysLeft(bestBefore, grace, today int) int {
	return bestBefore + grace - today
}
GO

cat > pkg/shelf/life_test.go <<'GO'
package shelf

import "testing"

func TestSellable(t *testing.T) {
	if !Sellable(100, 0, 90, false) {
		t.Fatal("fresh item rejected")
	}
	if Sellable(100, 0, 120, false) {
		t.Fatal("stale item accepted")
	}
}

func TestDaysLeft(t *testing.T) {
	if got := DaysLeft(100, 2, 95); got != 7 {
		t.Fatalf("DaysLeft = %d", got)
	}
}
GO

cat > gremlins.txt <<'TXT'
Gathering coverage... done in 287.914ms
KILLED ARITHMETIC_BASE at pkg/shelf/life.go:18:20
KILLED ARITHMETIC_BASE at pkg/shelf/life.go:18:28
KILLED CONDITIONALS_NEGATION at pkg/shelf/life.go:13:15
LIVED CONDITIONALS_BOUNDARY at pkg/shelf/life.go:13:15
LIVED ARITHMETIC_BASE at pkg/shelf/life.go:13:28

Mutation testing completed in 2 seconds 641 milliseconds
Killed: 3, Lived: 2, Not covered: 0
Timed out: 0, Not viable: 0, Skipped: 0
Test efficacy: 60.00%
Mutator coverage: 100.00%
TXT

gofmt -l . | grep . && exit 1
git add -A
git commit -q -m "shelf: sell-by rules plus last night's gremlins output"
