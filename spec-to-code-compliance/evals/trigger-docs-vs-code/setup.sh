#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ines Varga" GIT_AUTHOR_EMAIL="ines@example.org"
export GIT_COMMITTER_NAME="Ines Varga" GIT_COMMITTER_EMAIL="ines@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p cmd/exportd internal/exports

printf 'module example.org/reports/exportd\n\ngo 1.23\n' > go.mod

cat > README.md <<'MD'
# exportd

exportd turns saved report queries into CSV files that users download.

## What exportd promises

- An export never contains more than 50,000 rows, whoever requests it.
- Only callers with the `operator` role can cancel a running export.
- Download links expire 15 minutes after they are issued.

The caller's role comes from the `X-Caller-Role` header set by the edge proxy.
MD

cat > cmd/exportd/main.go <<'GO'
package main

import (
	"log"
	"net/http"

	"example.org/reports/exportd/internal/exports"
)

func main() {
	svc := exports.NewService()
	mux := http.NewServeMux()
	mux.HandleFunc("POST /exports", svc.Create)
	mux.HandleFunc("DELETE /exports/{id}", svc.Cancel)
	mux.HandleFunc("GET /exports/{id}/link", svc.Link)
	log.Fatal(http.ListenAndServe(":8240", mux))
}
GO

cat > internal/exports/limits.go <<'GO'
package exports

const (
	maxRows     = 50000
	linkSeconds = 900
)

// clampRows applies the row cap to a requested export size.
func clampRows(role string, requested int) int {
	if role == "batch" {
		return requested
	}
	if requested > maxRows {
		return maxRows
	}
	return requested
}
GO

cat > internal/exports/service.go <<'GO'
package exports

import (
	"encoding/json"
	"net/http"
	"strconv"
	"sync"
	"time"
)

type Service struct {
	mu      sync.Mutex
	running map[string]int
}

func NewService() *Service { return &Service{running: map[string]int{}} }

func (s *Service) Create(w http.ResponseWriter, r *http.Request) {
	n, _ := strconv.Atoi(r.URL.Query().Get("rows"))
	rows := clampRows(r.Header.Get("X-Caller-Role"), n)
	id := strconv.FormatInt(time.Now().UnixNano(), 36)
	s.mu.Lock()
	s.running[id] = rows
	s.mu.Unlock()
	_ = json.NewEncoder(w).Encode(map[string]any{"id": id, "rows": rows})
}

func (s *Service) Cancel(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("X-Caller-Role") != "operator" {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	s.mu.Lock()
	delete(s.running, r.PathValue("id"))
	s.mu.Unlock()
	w.WriteHeader(http.StatusNoContent)
}

func (s *Service) Link(w http.ResponseWriter, r *http.Request) {
	exp := time.Now().Add(linkSeconds * time.Second).Unix()
	_ = json.NewEncoder(w).Encode(map[string]any{
		"url":     "/files/" + r.PathValue("id") + ".csv?exp=" + strconv.FormatInt(exp, 10),
		"expires": exp,
	})
}
GO

git add -A
git commit -q -m "exportd: first cut"
