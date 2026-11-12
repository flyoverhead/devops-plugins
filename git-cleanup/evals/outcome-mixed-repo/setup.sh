#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ruth Adeyemi" GIT_AUTHOR_EMAIL="ruth@example.org"
export GIT_COMMITTER_NAME="Ruth Adeyemi" GIT_COMMITTER_EMAIL="ruth@example.org"

mkdir -p hub
git init -q --bare -b main hub/portal.git
git clone -q hub/portal.git portal 2>/dev/null
cd portal
git config core.hooksPath /dev/null

mkdir -p web
cat > web/server.go <<'GO'
package web

import "net/http"

func Routes(mux *http.ServeMux) {
	mux.HandleFunc("/login", login)
}

func login(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("content-type", "text/plain")
	w.Write([]byte("ok"))
}
GO
printf '# portal\n\nCustomer portal.\n' > README.md
git add -A && git commit -q -m "Portal skeleton with a login handler"
git push -q -u origin main

git switch -q -c bugfix/header-case
cat > web/server.go <<'GO'
package web

import "net/http"

func Routes(mux *http.ServeMux) {
	mux.HandleFunc("/login", login)
}

func login(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte("ok"))
}
GO
git commit -q -am "Use canonical Content-Type header name"
git push -q -u origin bugfix/header-case
git switch -q main
git merge -q --no-ff bugfix/header-case -m "Merge branch 'bugfix/header-case'"
git push -q origin main

git switch -q -c feature/rate-limit
cat > web/limit.go <<'GO'
package web

import (
	"net/http"
	"sync"
	"time"
)

type limiter struct {
	mu   sync.Mutex
	seen map[string]time.Time
}

func (l *limiter) allow(ip string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	if t, ok := l.seen[ip]; ok && time.Since(t) < time.Second {
		return false
	}
	l.seen[ip] = time.Now()
	return true
}

func limited(l *limiter, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !l.allow(r.RemoteAddr) {
			http.Error(w, "slow down", http.StatusTooManyRequests)
			return
		}
		next(w, r)
	}
}
GO
git add -A && git commit -q -m "Add a per-IP limiter"
cat > web/server.go <<'GO'
package web

import (
	"net/http"
	"time"
)

func Routes(mux *http.ServeMux) {
	mux.HandleFunc("/login", limited(&limiter{seen: map[string]time.Time{}}, login))
}

func login(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.Write([]byte("ok"))
}
GO
git commit -q -am "Wrap /login in the limiter"
git push -q -u origin feature/rate-limit
git switch -q main
git merge -q --squash feature/rate-limit >/dev/null
git commit -q -m "Rate-limit the login endpoint" -m "See merge request web/portal!88"
git push -q origin main
git push -q origin --delete feature/rate-limit

git switch -q -c wip/metrics-exporter
printf 'package web\n\nvar requests int\n' > web/metrics.go
git add -A && git commit -q -m "Count requests"
git push -q -u origin wip/metrics-exporter
printf 'package web\n\nvar requests, failures int\n' > web/metrics.go
git commit -q -am "Count failures too"
printf 'package web\n\nvar requests, failures, throttled int\n' > web/metrics.go
git commit -q -am "Count throttled requests"
git switch -q main

git switch -q -c try/new-cache
printf 'package web\n\nvar cache = map[string][]byte{}\n' > web/cache.go
git add -A && git commit -q -m "Experiment: in-memory response cache"
git push -q -u origin try/new-cache
git switch -q main
git push -q origin --delete try/new-cache

git fetch -q --prune
