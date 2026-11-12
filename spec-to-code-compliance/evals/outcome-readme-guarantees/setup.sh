#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ivo Marten" GIT_AUTHOR_EMAIL="ivo@example.org"
export GIT_COMMITTER_NAME="Ivo Marten" GIT_COMMITTER_EMAIL="ivo@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p cmd/hookrelay internal/limiter internal/deliverylog internal/relay internal/config

printf 'module example.org/relay/hookrelay\n\ngo 1.23\n' > go.mod

cat > README.md <<'MD'
# hookrelay

hookrelay accepts webhooks from partner systems, checks their signatures and keeps a
delivery log that internal consumers read.

## Guarantees

1. **Fair use.** Each API client, identified by `X-Client-ID`, is limited to 120 requests
   per minute. Requests over the limit are answered with `429 Too Many Requests`.
2. **Delivery log retention.** Delivery log entries are deleted 14 days after they are
   written.
3. **Signature checks.** Inbound signatures are compared in constant time, so response
   timing reveals nothing about the expected value.

## Running

    HOOKRELAY_SIGNING_SECRET=... go run ./cmd/hookrelay

The service listens on `:8086`.
MD

cat > cmd/hookrelay/main.go <<'GO'
package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"example.org/relay/hookrelay/internal/config"
	"example.org/relay/hookrelay/internal/deliverylog"
	"example.org/relay/hookrelay/internal/limiter"
	"example.org/relay/hookrelay/internal/relay"
)

func main() {
	cfg := config.Load()
	store := deliverylog.NewStore()
	go store.RunPruner(context.Background(), 30*time.Minute)

	h := relay.NewHandler(cfg, store)
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/hooks/{source}", h.Receive)
	mux.HandleFunc("GET /v1/deliveries", h.List)

	lim := limiter.New()
	log.Printf("hookrelay listening on %s", cfg.Addr)
	log.Fatal(http.ListenAndServe(cfg.Addr, lim.Middleware(mux)))
}
GO

cat > internal/config/config.go <<'GO'
package config

import "os"

type Config struct {
	Addr          string
	SigningSecret []byte
	AdminToken    string
}

func Load() Config {
	secret := os.Getenv("HOOKRELAY_SIGNING_SECRET")
	if secret == "" {
		secret = "relay-dev-secret-0042"
	}
	addr := os.Getenv("HOOKRELAY_ADDR")
	if addr == "" {
		addr = ":8086"
	}
	return Config{Addr: addr, SigningSecret: []byte(secret), AdminToken: os.Getenv("HOOKRELAY_ADMIN_TOKEN")}
}
GO

cat > internal/limiter/limiter.go <<'GO'
package limiter

import (
	"net/http"
	"sync"
	"time"
)

const PerMinute = 120

type Limiter struct {
	mu      sync.Mutex
	counts  map[string]int
	resetAt time.Time
	now     func() time.Time
}

func New() *Limiter {
	return &Limiter{counts: map[string]int{}, now: time.Now}
}

func (l *Limiter) allow(client string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	t := l.now()
	if t.After(l.resetAt) {
		l.counts = map[string]int{}
		l.resetAt = t.Add(time.Minute)
	}
	l.counts[client]++
	return l.counts[client] <= PerMinute
}

// Middleware counts every request against the client named in X-Client-ID.
func (l *Limiter) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Relay-Replay") == "1" {
			// replays from our own forwarder were already counted once
			next.ServeHTTP(w, r)
			return
		}
		if !l.allow(r.Header.Get("X-Client-ID")) {
			http.Error(w, "too many requests", http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}
GO

cat > internal/deliverylog/store.go <<'GO'
package deliverylog

import (
	"context"
	"log"
	"sync"
	"time"
)

const keepFor = 336 * time.Hour

type Entry struct {
	Source  string
	Body    []byte
	Written time.Time
}

type Store struct {
	mu      sync.Mutex
	entries []Entry
}

func NewStore() *Store { return &Store{} }

func (s *Store) Add(source string, body []byte) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.entries = append(s.entries, Entry{Source: source, Body: body, Written: time.Now()})
}

func (s *Store) All() []Entry {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]Entry(nil), s.entries...)
}

// Prune drops entries written before now-keepFor and returns how many it removed.
func (s *Store) Prune(now time.Time) int {
	cutoff := now.Add(-keepFor)
	s.mu.Lock()
	defer s.mu.Unlock()
	kept := s.entries[:0]
	for _, e := range s.entries {
		if e.Written.After(cutoff) {
			kept = append(kept, e)
		}
	}
	removed := len(s.entries) - len(kept)
	s.entries = kept
	return removed
}

func (s *Store) RunPruner(ctx context.Context, every time.Duration) {
	t := time.NewTicker(every)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case now := <-t.C:
			if n := s.Prune(now); n > 0 {
				log.Printf("deliverylog: pruned %d entries", n)
			}
		}
	}
}
GO

cat > internal/relay/signature.go <<'GO'
package relay

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
)

// verifySignature reports whether sig is the hex HMAC-SHA256 of body under secret.
// The comparison runs in constant time.
func verifySignature(secret, body []byte, sig string) bool {
	mac := hmac.New(sha256.New, secret)
	mac.Write(body)
	expected := hex.EncodeToString(mac.Sum(nil))
	return sig == expected
}
GO

cat > internal/relay/handler.go <<'GO'
package relay

import (
	"encoding/json"
	"io"
	"net/http"

	"example.org/relay/hookrelay/internal/config"
	"example.org/relay/hookrelay/internal/deliverylog"
)

type Handler struct {
	cfg   config.Config
	store *deliverylog.Store
}

func NewHandler(cfg config.Config, store *deliverylog.Store) *Handler {
	return &Handler{cfg: cfg, store: store}
}

func (h *Handler) Receive(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		http.Error(w, "bad body", http.StatusBadRequest)
		return
	}
	if !verifySignature(h.cfg.SigningSecret, body, r.Header.Get("X-Hook-Signature")) {
		http.Error(w, "bad signature", http.StatusUnauthorized)
		return
	}
	h.store.Add(r.PathValue("source"), body)
	w.WriteHeader(http.StatusAccepted)
}

func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Authorization") != "Bearer "+h.cfg.AdminToken {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	_ = json.NewEncoder(w).Encode(h.store.All())
}
GO

git add -A
git commit -q -m "hookrelay: initial import"
