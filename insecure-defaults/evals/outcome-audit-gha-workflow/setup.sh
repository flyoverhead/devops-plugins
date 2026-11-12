#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p .github/workflows src
# shellcheck disable=SC2016
printf 'export const greet = (n: string): string => `hello ${n}`;\n' > src/index.ts
printf '{\n  "name": "greeter",\n  "version": "0.3.0",\n  "scripts": {"test": "node --test", "lint": "eslint src"}\n}\n' > package.json
cat > .github/workflows/pr-checks.yml <<'YAML'
name: pr-checks

on:
  pull_request_target:
    types: [opened, synchronize, reopened]

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - name: Announce
        run: echo "Checking PR: ${{ github.event.pull_request.title }}"
      - name: Install
        run: npm ci
      - name: Dependency scan
        uses: snyk/actions/node@v0.4.0
        continue-on-error: true
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      - name: Test
        run: npm test
YAML
cat > .github/workflows/release.yml <<'YAML'
name: release

on:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
      - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af
        with:
          node-version: "22"
      - run: npm ci
      - run: npm test
YAML
git add -A && git commit -q -m "greeter with CI"
