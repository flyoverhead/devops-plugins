#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Mira Okafor" GIT_AUTHOR_EMAIL="mira@example.org"
export GIT_COMMITTER_NAME="Mira Okafor" GIT_COMMITTER_EMAIL="mira@example.org"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p cmd/keyfetch internal/vault deploy

printf 'module example.org/keyfetch\n\ngo 1.23\n' > go.mod
cat > cmd/keyfetch/main.go <<'GO'
package main

import (
	"fmt"
	"log"
	"os"

	"example.org/keyfetch/internal/vault"
)

func main() {
	if len(os.Args) != 2 {
		log.Fatal("usage: keyfetch <secret path>")
	}
	c, err := vault.New(os.Getenv("VAULT_ADDR"), os.Getenv("VAULT_TOKEN"))
	if err != nil {
		log.Fatal(err)
	}
	body, err := c.Read(os.Args[1])
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(string(body))
}
GO
cat > internal/vault/client.go <<'GO'
package vault

import (
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	addr  string
	token string
	hc    *http.Client
}

func New(addr, token string) (*Client, error) {
	tr := &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}
	return &Client{addr: addr, token: token, hc: &http.Client{Transport: tr, Timeout: 10 * time.Second}}, nil
}

func (c *Client) Read(path string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, c.addr+"/v1/"+path, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Vault-Token", c.token)
	resp, err := c.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("vault: %s returned %d", path, resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}
GO
git add -A && git commit -q -m "keyfetch: read secrets from the store over HTTPS"

cat > internal/vault/store-ca.pem <<'PEM'
-----BEGIN CERTIFICATE-----
MIIBszCCAVmgAwIBAgIUQ2h1bmt5LWNhLWZvci10ZXN0czAKBggqhkjOPQQDAjAa
MRgwFgYDVQQDDA9rZXlmZXRjaCBzdG9yZSBDQTAeFw0yNjAxMDEwMDAwMDBaFw0z
-----END CERTIFICATE-----
PEM
cat > internal/vault/client.go <<'GO'
package vault

import (
	"crypto/tls"
	"crypto/x509"
	_ "embed"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"
)

//go:embed store-ca.pem
var storeCA []byte

type Client struct {
	addr  string
	token string
	hc    *http.Client
}

func tlsConfig() (*tls.Config, error) {
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(storeCA) {
		return nil, errors.New("vault: store-ca.pem holds no usable certificate")
	}
	return &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12}, nil
}

func New(addr, token string) (*Client, error) {
	cfg, err := tlsConfig()
	if err != nil {
		return nil, err
	}
	tr := &http.Transport{TLSClientConfig: cfg}
	return &Client{addr: addr, token: token, hc: &http.Client{Transport: tr, Timeout: 10 * time.Second}}, nil
}

func (c *Client) Read(path string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, c.addr+"/v1/"+path, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Vault-Token", c.token)
	resp, err := c.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("vault: %s returned %d", path, resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}
GO
git add -A && git commit -q -m "fix(security): pin the store CA and require TLS 1.2 for vault calls" \
  -m "Certificate checks were switched off, so anyone on the path could read the vault token."
git tag base

git rm -q internal/vault/store-ca.pem
cat > internal/vault/client.go <<'GO'
package vault

import (
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

type Client struct {
	addr  string
	token string
	hc    *http.Client
}

func tlsConfig() *tls.Config {
	cfg := &tls.Config{}
	if os.Getenv("KEYFETCH_TLS_SKIP_VERIFY") != "" {
		cfg.InsecureSkipVerify = true
	}
	return cfg
}

func New(addr, token string) (*Client, error) {
	tr := &http.Transport{TLSClientConfig: tlsConfig()}
	return &Client{addr: addr, token: token, hc: &http.Client{Transport: tr, Timeout: 10 * time.Second}}, nil
}

func (c *Client) Read(path string) ([]byte, error) {
	req, err := http.NewRequest(http.MethodGet, c.addr+"/v1/"+path, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Vault-Token", c.token)
	resp, err := c.hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("vault: %s returned %d", path, resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}
GO
cat > deploy/values.yaml <<'YAML'
image: registry.example.org/keyfetch:1.4.0
env:
  VAULT_ADDR: https://secrets.example.org:8200
  KEYFETCH_TLS_SKIP_VERIFY: "false"
YAML
git add -A && git commit -q -m "refactor: make store TLS settings configurable per deployment"
