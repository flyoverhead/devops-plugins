#!/usr/bin/env bash
set -euo pipefail
git init -q
mkdir -p .github/workflows src/tallyho tests
cat > pyproject.toml <<'TOML'
[project]
name = "tallyho"
version = "0.4.1"
requires-python = ">=3.11"
TOML
printf 'def tally(rows):\n    return sum(int(r) for r in rows if r.strip())\n' > src/tallyho/__init__.py
printf 'from tallyho import tally\n\n\ndef test_tally():\n    assert tally(["1", " ", "2"]) == 3\n' > tests/test_tally.py
cat > .github/workflows/ci.yml <<'YAML'
name: ci

on:
  pull_request_target:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - name: Show what is being tested
        run: echo "Testing: ${{ github.event.pull_request.title }}"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e . pytest
      - run: pytest -q
      - name: Post coverage summary
        uses: quillworks/pr-coverage-note@main
        with:
          token: ${{ github.token }}
YAML
git add -A && git commit -q -m "tallyho with CI"
