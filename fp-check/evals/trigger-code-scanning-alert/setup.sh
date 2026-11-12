#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module example.net/snapd\n\ngo 1.23\n' > go.mod
cat > main.go <<'GO'
package main

import (
	"log"
	"net/http"
	"os/exec"
)

// snapd packs the export share into a named tarball on request and reports disk usage.

func handleSnapshot(w http.ResponseWriter, r *http.Request) {
	label := r.URL.Query().Get("label")
	script := "tar -czf /var/spool/snapd/" + label + ".tgz -C /srv/exports ."
	out, err := exec.Command("sh", "-c", script).CombinedOutput()
	if err != nil {
		http.Error(w, string(out), http.StatusInternalServerError)
		return
	}
	w.Write([]byte("snapshot stored\n"))
}

func handleUsage(w http.ResponseWriter, r *http.Request) {
	out, err := exec.Command("df", "-h", "/srv/exports").Output()
	if err != nil {
		http.Error(w, "usage unavailable", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/plain")
	w.Write(out)
}

func main() {
	http.HandleFunc("/snapshot", handleSnapshot)
	http.HandleFunc("/usage", handleUsage)
	log.Fatal(http.ListenAndServe(":8085", nil))
}
GO
git add -A && git commit -q -m "snapd: snapshot and usage endpoints"
