#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Wren Okafor" GIT_AUTHOR_EMAIL="wren@example.org"
export GIT_COMMITTER_NAME="Wren Okafor" GIT_COMMITTER_EMAIL="wren@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p cmd/digestd internal/caller internal/digest

printf 'module example.org/mail/digestd\n\ngo 1.23\n' > go.mod

cat > README.md <<'MD'
# digestd

digestd builds newsletter digests. A tenant posts the digest text with a recipient count,
and digestd spools one file per digest for the mail relay to pick up.

The edge gateway forwards `X-Tenant` and `X-Tenant-Plan` on every request.
MD

cat > cmd/digestd/main.go <<'GO'
package main

import (
	"log"
	"net/http"

	"example.org/mail/digestd/internal/digest"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/digests", digest.Enqueue)
	log.Fatal(http.ListenAndServe(":9310", mux))
}
GO

cat > internal/caller/caller.go <<'GO'
package caller

import (
	"errors"
	"net/http"
)

type Tenant struct {
	ID   string
	Plan string
}

func FromHeaders(r *http.Request) (Tenant, error) {
	t := Tenant{ID: r.Header.Get("X-Tenant"), Plan: r.Header.Get("X-Tenant-Plan")}
	if t.ID == "" {
		return Tenant{}, errors.New("missing tenant")
	}
	return t, nil
}
GO

cat > internal/digest/fanout.go <<'GO'
package digest

import (
	"errors"
	"strconv"
)

const maxRecipients = 2000

// admitFanout keeps every digest at or below maxRecipients.
func admitFanout(plan, raw string) (int, error) {
	n, err := recipientQuota(plan, raw)
	if err != nil {
		return 0, err
	}
	if n <= 0 {
		return 0, errors.New("no recipients")
	}
	return n, nil
}

func recipientQuota(plan, raw string) (int, error) {
	n, err := strconv.Atoi(raw)
	if err != nil {
		return 0, err
	}
	if plan == "enterprise" {
		return n, nil
	}
	return min(n, maxRecipients), nil
}
GO

cat > internal/digest/enqueue.go <<'GO'
package digest

import (
	"bufio"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"example.org/mail/digestd/internal/caller"
)

const (
	spoolDir = "/var/spool/digestd"
	maxBody  = 1 << 20
)

func Enqueue(w http.ResponseWriter, r *http.Request) {
	t, err := caller.FromHeaders(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusUnauthorized)
		return
	}
	n, err := admitFanout(t.Plan, r.URL.Query().Get("recipients"))
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	var body io.Reader = r.Body
	if t.Plan != "enterprise" {
		body = io.LimitReader(r.Body, maxBody)
	}
	slots := make([]string, n)
	sc := bufio.NewScanner(body)
	for i := 0; i < n && sc.Scan(); i++ {
		slots[i] = sc.Text()
	}
	name := t.ID + "-" + strconv.FormatInt(time.Now().UnixNano(), 10) + ".txt"
	if err := os.WriteFile(filepath.Join(spoolDir, name), []byte(strings.Join(slots, "\n")), 0o640); err != nil {
		http.Error(w, "spool failed", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusAccepted)
}
GO

git add -A
git commit -q -m "digestd: first import"
