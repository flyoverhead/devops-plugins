# Packs, suites, threat models and performance

## Contents

- Query packs per language
- Suites
- Important-only post-filter
- Threat models
- Model packs and extensions at analysis time
- Performance
- rulesets.txt

## Query packs per language

All are downloaded with `codeql pack download <pack>` after the plan is approved.

| Language | Official | Community (opt-out in the plan) |
|---|---|---|
| go | `codeql/go-queries` | `trailofbits/go-queries`, `githubsecuritylab/codeql-go-queries` |
| cpp | `codeql/cpp-queries` | `trailofbits/cpp-queries`, `githubsecuritylab/codeql-cpp-queries` |
| java (Kotlin too) | `codeql/java-queries` | `trailofbits/java-queries`, `githubsecuritylab/codeql-java-queries` |
| python | `codeql/python-queries` | `githubsecuritylab/codeql-python-queries` |
| javascript (TypeScript too) | `codeql/javascript-queries` | `githubsecuritylab/codeql-javascript-queries` |
| csharp | `codeql/csharp-queries` | `githubsecuritylab/codeql-csharp-queries` |
| ruby | `codeql/ruby-queries` | `githubsecuritylab/codeql-ruby-queries` |
| swift, rust | `codeql/swift-queries`, `codeql/rust-queries` | none |

The `githubsecuritylab/*` packs are published from the GitHubSecurityLab
`CodeQL-Community-Packs` repositories. Pass the downloaded community packs to
`generate_suite.sh` as `INSTALLED_THIRD_PARTY_PACKS` (space separated). A pack that failed to
download is left out and named in the final summary.

## Suites

Never analyse with a pack name: a pack's default suite applies filters you cannot see and
can return nothing. `generate_suite.sh run-all|important-only` writes
`$OUTPUT_DIR/raw/<mode>.qls` and checks it with `verify_query_suite.py`
(`codeql resolve queries`); zero queries → the suite is deleted and the script exits 1.

**run-all** imports both `codeql-suites/<lang>-security-and-quality.qls` and
`codeql-suites/<lang>-security-experimental.qls` from `codeql/<lang>-queries` — they
complement each other (the first leaves out experimental paths; the second adds them), so
neither alone is the broadest set — and adds every community pack with `queries: .`. It keeps
`problem` and `path-problem` queries and drops deprecated queries and those tagged
`modeleditor` or `modelgenerator`. It is broad, not literally every query.

**important-only** selects `queries: .` from the official and community packs and keeps
`problem`/`path-problem` queries tagged `security` with precision `high` or `very-high`, plus
a second include for `medium` precision security queries, which the post-filter narrows.
Community queries that lack a precision or the `security` tag are dropped; that strictness is
accepted.

## Important-only post-filter

`scripts/important-only.jq` keeps results whose rule has precision `high`, `very-high` or none
(unknown), and `medium` only when `security-severity` ≥ 6.0 (missing counts as 0). Precision
and severity live on rule definitions; CodeQL stores those under `tool.extensions[n].rules`,
reached through `result.rule.toolComponent.index` and `result.rule.index` (or `ruleIndex`).

## Threat models

`--threat-model` is singular and repeatable. Default: `remote` only.

| Add | When |
|---|---|
| `local` | CLIs, file parsers, desktop tools: argv, stdin and local files are attacker input |
| `environment` | twelve-factor services configured through environment variables |
| `database` | stored or second-order attacks; many false positives |
| `file` | upload handlers, log or config parsers |
| `all` | audit mode, everything |
| `!name` | remove one model from the set |

## Model packs and extensions at analysis time

- A model pack that `codeql` already has installed is named with `--model-packs`.
- In-repo model packs and the standalone `extensions/` written by this skill:
  `--additional-packs <dir>`.
- Known limit: pre-compiled query packs ignore both. The workaround copies the extension YAML
  into the `ext/` directory of the `codeql/<lang>-all` pack in CodeQL's managed pack cache.
  That writes outside `$TMPDIR` and is lost on the next pack update, so it needs its own plan
  line and an explicit yes. Prefer `--additional-packs` with a model pack under `$TMPDIR`
  whenever the packs are not pre-compiled.

## Performance

| Lever | Guidance |
|---|---|
| `CODEQL_RAM` (MB) | 4000–8000 under 100K lines; 8000–16000 up to 1M; 32000–64000 above |
| `--threads` | `0` (all cores), or `8` on a shared machine |
| `--timeout=600000` | per-query cap in ms for runaway queries |
| `--evaluator-log=<file>` then `codeql generate log-summary <file>` | find the slow queries |
| `codeql database cleanup` / `--rerun` | defeat cached results when comparing runs |
| Disk | database 2–10× the source; pack and compilation cache 1–5 GB; run `df -h` before starting |

## rulesets.txt

```text
mode: run-all
database: /abs/tmp/codeql-repo_1/codeql.db
language: go
timestamp: 2026-11-11T14:05:00Z

[query packs]
codeql/go-queries
trailofbits/go-queries
githubsecuritylab/codeql-go-queries

[model packs]

[threat models]
remote
```
