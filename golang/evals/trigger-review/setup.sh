#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module github.com/example/demo\n\ngo 1.25\n' > go.mod
cat > handler.go <<'GO'
package demo

import (
	"database/sql"
	"net/http"
	"time"
)

const dbPassword = "hunter2"

type Handler struct {
	db *sql.DB
}

func (h *Handler) User(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	rows, _ := h.db.Query("SELECT * FROM users WHERE name='" + name + "'")
	defer rows.Close()
	go func() {
		for {
			time.Sleep(time.Second)
			_ = dbPassword
		}
	}()
	w.WriteHeader(http.StatusOK)
}
GO
git add -A && git commit -q -m init
