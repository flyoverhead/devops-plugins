#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module example.com/pinger

go 1.22
' > go.mod
cat > main.go <<'GO'
package main

import (
	"net/http"
	"os/exec"
)

func pingHandler(rw http.ResponseWriter, req *http.Request) {
	host := req.URL.Query().Get("host")
	out, _ := exec.Command("sh", "-c", "ping -c 1 "+host).CombinedOutput()
	_, _ = rw.Write(out)
}

func main() {
	http.HandleFunc("/ping", pingHandler)
	_ = http.ListenAndServe(":8080", nil)
}
GO
git add -A && git commit -q -m init
