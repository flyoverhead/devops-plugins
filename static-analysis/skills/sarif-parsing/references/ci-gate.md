# Gating CI on SARIF (GitHub Actions)

## Fail on any error-level finding

One job: run the scanner to SARIF, gate with the severity-resolving jq definitions, and upload
to code scanning even when the gate fails. Pin every action to a full commit SHA; the
placeholders below say which release to take it from.

```yaml
name: sast
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  semgrep:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@<commit-sha-of-a-v5-release>
      - name: Scan
        run: pipx run semgrep==1.184.0 scan --metrics=off --config p/default --sarif-output=results.sarif .
      - name: Gate on error-level findings
        run: |
          errors=$(jq -L .github/jq 'include "sarif"; [sarif_results | select(._level == "error")] | length' results.sarif)
          echo "error-level findings: $errors"
          test "$errors" -eq 0
      - name: Upload to code scanning
        if: always()
        uses: github/codeql-action/upload-sarif@<commit-sha-of-a-v4-release>
        with:
          sarif_file: results.sarif
```

- Commit `resources/sarif.jq` from this skill as `.github/jq/sarif.jq` (or paste its
  definitions into the `run:` block), and `resources/sarif_helpers.py` as
  `.github/sarif/sarif_helpers.py` for the baseline diff below. `ubuntu-latest` ships `jq`,
  `pipx` and Python 3.
- `security-events: write` is needed for the upload only; keep the workflow default at
  `contents: read`.
- Pull requests from forks get a read-only token: the upload step fails or is skipped there,
  while the gate still runs.
- Inside GitHub, thresholds can also be enforced by making the code-scanning check required
  in branch protection; the jq gate is for runners that do not upload.
- The gate counts after severity resolution. A plain `.level == "error"` filter passes every
  CodeQL run because CodeQL puts levels on rules.

## Fail only on new findings

Keep a baseline SARIF from the default branch (an artifact from the last `main` run) and fail
when the current run has fingerprints the baseline lacks:

```yaml
      - name: Fail on new findings
        run: |
          python3 .github/sarif/sarif_helpers.py results.sarif
          python3 - <<'PY'
          import sys
          sys.path.insert(0, ".github/sarif")
          import sarif_helpers as sh
          base = sh.extract_findings(sh.load_sarif("baseline.sarif"))
          cur = sh.extract_findings(sh.load_sarif("results.sarif"))
          new, fixed, _ = sh.diff_findings(base, cur)
          print(f"new: {len(new)}, fixed: {len(fixed)}")
          for f in sh.sort_by_severity(new):
              print(f"{f.level} {f.rule_id} {f.file_path}:{f.start_line}")
          sys.exit(1 if new else 0)
          PY
```

Make URIs repo-relative in both files first; differing checkout prefixes break location-based
fingerprints. Tool fingerprints (`partialFingerprints`) survive line shifts better than the
computed ones.
