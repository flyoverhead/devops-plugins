#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ines Varga" GIT_AUTHOR_EMAIL="ines@example.org"
export GIT_COMMITTER_NAME="Ines Varga" GIT_COMMITTER_EMAIL="ines@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p cmd/pingback internal/probe

printf 'module example.org/pingback\n\ngo 1.23\n' > go.mod
cat > cmd/pingback/main.go <<'GO'
package main

import (
	"log"
	"net/http"

	"example.org/pingback/internal/probe"
)

func main() {
	http.HandleFunc("/ping", probe.PingHandler)
	http.HandleFunc("/trace", probe.TraceHandler)
	log.Fatal(http.ListenAndServe(":8080", nil))
}
GO
cat > internal/probe/handler.go <<'GO'
package probe

import (
	"fmt"
	"net/http"
	"os/exec"
)

func PingHandler(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Query().Get("host")
	out, err := exec.Command("sh", "-c", "ping -c 1 "+host).CombinedOutput()
	if err != nil {
		http.Error(w, string(out), http.StatusBadGateway)
		return
	}
	fmt.Fprint(w, string(out))
}

func TraceHandler(w http.ResponseWriter, r *http.Request) {
	host := r.URL.Query().Get("host")
	out, err := exec.Command("traceroute", "-m", "8", host).CombinedOutput()
	if err != nil {
		http.Error(w, string(out), http.StatusBadGateway)
		return
	}
	fmt.Fprint(w, string(out))
}
GO
git add -A && git commit -q -m "pingback: ping and traceroute endpoints"
