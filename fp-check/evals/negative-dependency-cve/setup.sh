#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p internal/settings deploy
cat > go.mod <<'MOD'
module example.net/relayd

go 1.23

require gopkg.in/yaml.v2 v2.2.4
MOD
cat > internal/settings/settings.go <<'GO'
package settings

import (
	"os"

	"gopkg.in/yaml.v2"
)

type Upstream struct {
	Name    string `yaml:"name"`
	Address string `yaml:"address"`
}

type Settings struct {
	Listen    string     `yaml:"listen"`
	Upstreams []Upstream `yaml:"upstreams"`
}

func Load(path string) (*Settings, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var s Settings
	if err := yaml.Unmarshal(raw, &s); err != nil {
		return nil, err
	}
	return &s, nil
}
GO
cat > main.go <<'GO'
package main

import (
	"log"

	"example.net/relayd/internal/settings"
)

func main() {
	s, err := settings.Load("/etc/relayd/relayd.yaml")
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("relayd listening on %s with %d upstreams", s.Listen, len(s.Upstreams))
}
GO
cat > deploy/relayd.yaml <<'YAML'
listen: ":7400"
upstreams:
  - name: billing
    address: "10.20.0.11:7401"
YAML
cat > deploy/README.md <<'MD'
`relayd.yaml` is rendered by the platform team and installed to `/etc/relayd/` as root, mode 0644.
MD
git add -A && git commit -q -m "relayd: settings loader"
