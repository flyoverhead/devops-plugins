#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module github.com/example/demo\n\ngo 1.25\n' > go.mod
cat > client.go <<'GO'
package demo

type Client struct{}

func NewClient(host string, port int, user, pass string, timeout int, retries int, tls bool, proxy string, debug bool) *Client {
	return &Client{}
}
GO
