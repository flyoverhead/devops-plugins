# static-analysis

Static analysis for Claude Code: local Semgrep audits, SARIF reading and CI gating, and CodeQL
taint analysis. Every scan, build and download waits for an approved plan, nothing is
installed, and all output goes to `$TMPDIR`, outside the repository.

```text
/plugin install static-analysis@devops
```

## Skills

| Skill | Use it to |
|---|---|
| `static-analysis:semgrep` | Scan a repository with Semgrep registry packs (`p/default`, `p/secrets`, language packs), opt in to broader packs or third-party rule repos, and get one merged SARIF file. Shows a plan with every download and waits for a yes; `--metrics=off` always |
| `static-analysis:sarif-parsing` | Count, filter, group, dedupe, merge and diff SARIF 2.1.0 from any scanner, with severity resolved from rules when results carry no level; write a GitHub Actions gate with `upload-sarif` |
| `static-analysis:codeql` | Build a CodeQL database and run interprocedural taint analysis with explicit run-all or important-only suites, official and community packs, threat models and project data extensions. Runs only on open-source code or research use, after an approved plan |

## How the gates work

- **semgrep:** detects languages, then presents target, output directory, mode, every ruleset
  (baseline and language packs ticked, the rest unticked) and every download. The bundled
  runner scans only after an explicit yes; the merger writes `results/results.sarif`.
- **codeql:** checks the licence first (an OSI licence file, or your statement that the code
  is open source or the use is research; otherwise it stops and points to GitHub code
  scanning or `static-analysis:semgrep`). Then one plan: language, build command, packs to
  download, mode, threat model, output. `codeql` commands are not pre-approved, so each one
  asks.
- **sarif-parsing:** read-only; it writes merged or filtered files only when asked.

## Output

```text
$TMPDIR/semgrep-<repo>_N/   rulesets.json  scans.json  raw/  results/results.sarif
$TMPDIR/codeql-<repo>_N/    codeql.db/  build.log  rulesets.txt  raw/  results/results.sarif
```

## Required tools

None is installed by the plugin.

| Tool | Needed by |
|---|---|
| `semgrep` (pin a version) | `semgrep` |
| `codeql` CLI | `codeql` |
| `jq`, `python3` 3.11+ | all three skills |
| `git` | third-party rule clones in `semgrep` |

## Tests

```bash
python3 -m pytest static-analysis/tests -q
```

`semgrep` and `codeql` are stubbed; the tests that need the real binaries are skipped with
"not run: <binary> missing".
