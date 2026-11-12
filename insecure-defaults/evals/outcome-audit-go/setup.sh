#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p deploy
printf 'module example.com/demo\n\ngo 1.22\n' > go.mod
cat > main.go <<'GO'
package main

import (
	"crypto/hmac"
	"crypto/md5"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"log"
	"net/http"
	"os"
	"strings"
	"time"
)

const catalogJSON = `{"items":["lamp","desk","chair"]}`

type cookieSigner struct{ secret []byte }

func newCookieSigner() *cookieSigner {
	secret := os.Getenv("SHOPFRONT_COOKIE_SECRET")
	if secret == "" {
		secret = "shopfront-insecure-default"
	}
	return &cookieSigner{secret: []byte(secret)}
}

func (s *cookieSigner) seal(payload string) string {
	mac := hmac.New(sha256.New, s.secret)
	mac.Write([]byte(payload))
	tag := base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
	return payload + "|" + tag
}

func (s *cookieSigner) open(value string) (string, bool) {
	payload, tag, ok := strings.Cut(value, "|")
	if !ok {
		return "", false
	}
	want := s.seal(payload)
	return payload, hmac.Equal([]byte(want), []byte(payload+"|"+tag))
}

type shop struct{ signer *cookieSigner }

func (sh *shop) cart(rw http.ResponseWriter, req *http.Request) {
	owner := strings.TrimSpace(req.Header.Get("X-Authenticated-User"))
	if owner == "" {
		http.Error(rw, "login required", http.StatusUnauthorized)
		return
	}
	cookie := &http.Cookie{Name: "cart", Value: sh.signer.seal(owner), HttpOnly: true, MaxAge: 3600}
	http.SetCookie(rw, cookie)
	rw.WriteHeader(http.StatusAccepted)
}

func (sh *shop) orders(rw http.ResponseWriter, req *http.Request) {
	c, err := req.Cookie("cart")
	if err != nil {
		http.Error(rw, "no cart", http.StatusUnauthorized)
		return
	}
	owner, valid := sh.signer.open(c.Value)
	if !valid {
		http.Error(rw, "bad signature", http.StatusForbidden)
		return
	}
	rw.Header().Set("X-Cart-Owner", owner)
	rw.Header().Set("Content-Type", "application/json")
	_, _ = rw.Write([]byte(`{"orders":[]}`))
}

func (sh *shop) catalog(rw http.ResponseWriter, req *http.Request) {
	digest := md5.Sum([]byte(catalogJSON))
	rw.Header().Set("ETag", hex.EncodeToString(digest[:]))
	rw.Header().Set("Content-Type", "application/json")
	_, _ = rw.Write([]byte(catalogJSON))
}

func main() {
	sh := &shop{signer: newCookieSigner()}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /catalog", sh.catalog)
	mux.HandleFunc("POST /cart", sh.cart)
	mux.HandleFunc("GET /orders", sh.orders)
	srv := &http.Server{Addr: ":9000", Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	if err := srv.ListenAndServe(); err != nil {
		log.Print(err)
	}
}
GO
cat > deploy/values.yaml <<'YAML'
image:
  repository: registry.example.com/shopfront/api
  tag: "2.0.7"
env:
  LOG_LEVEL: warn
YAML
git add -A && git commit -q -m "shopfront api"
