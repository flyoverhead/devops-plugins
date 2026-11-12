---
name: codeql
description: Runs CodeQL taint and dataflow analysis on a repository — checks the licence first, finds or builds the database through a logged build ladder, gates on database quality, adds data-extension models for project sources and sinks, and analyses with an explicit run-all or important-only suite into SARIF outside the repo, all behind one approved plan. Use when asked to run codeql, build a CodeQL database, or do taint, dataflow or SAST analysis with CodeQL. Not for quick pattern scans or code that cannot build — use static-analysis:semgrep; not for reading SARIF — use static-analysis:sarif-parsing.
argument-hint: "[repo-root] [output-dir]"
allowed-tools: Read Glob Grep Write AskUserQuestion TaskCreate TaskUpdate TaskList Bash(${CLAUDE_SKILL_DIR}/scripts/find_databases.sh:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/check_db_quality.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/verify_query_suite.py:*) Bash(jq:*) Bash(command -v:*) Bash(printenv TMPDIR) Bash(mkdir -p:*) Bash(df -h:*) Bash(git rev-parse:*)
---

Target: $ARGUMENTS

# CodeQL analysis

Build-based, interprocedural analysis. Slower and heavier than Semgrep, and it runs the
project's build, so every step that builds, downloads or analyses sits behind one approved
plan. `codeql` itself is deliberately not in `allowed-tools`: each `codeql` call asks the user.
Do not try to avoid that.

## Hard rules

- Licence gate before anything else, including preflight.
- One plan, one explicit yes, before any `codeql database create`, `codeql pack download` or
  build step. The request is not approval. Approval covers exactly what the plan listed.
- Never install CodeQL, packs outside the plan, or project dependencies globally.
- Output goes to `$TMPDIR/codeql-<repo>_N/` (or the user's directory), never into the repo.
- Never pass pack names to `codeql database analyze`; always an explicit `.qls`.
- Zero findings is a result to investigate, not proof of safety.
- Every Bash call is a fresh shell: re-set every variable, re-source `build_log.sh`, re-declare
  arrays in each call. A lost function exits 127 and looks like a failed build; a lost array
  silently drops `--threat-model` or `--model-packs`.

## Steps

0. Licence gate
1. Preflight
2. Output directory and existing databases
3. Language and build detection
4. Plan gate
5. Download packs
6. Build the database
7. Quality gate
8. Data extensions (optional)
9. Analyse
10. Post-process and report

### 0. Licence gate

Look for `LICENSE*`, `LICENCE*` or `COPYING*` at the repo root (Glob, then Read). Pass when:

- the file is an OSI-approved licence (MIT, Apache-2.0, BSD-2/3-Clause, ISC, MPL-2.0,
  GPL/LGPL/AGPL, EPL-2.0, Unlicense, Zlib, BSL-1.0 and similar) — record "MIT LICENSE file"
  as the basis; or
- the user says the code is open source, or that the use is academic or security research —
  record their words as the basis.

Anything else — no file, an unknown or source-available licence, "All rights reserved" — is a
stop, not a question loop. Do not run preflight, plan or build. The gate needs no `gh`, no
remote and no network. Reply with this message, filled in, and end the turn. Add nothing
about languages, build commands, packs or output paths: a plan preview before the gate passes
reads as a plan.

```text
CodeQL stopped at the licence check: <no licence file | the licence is X, not OSI-approved>.
The CodeQL CLI terms allow it on open-source code and for academic or security research;
other code needs a GitHub Advanced Security / Code Security licence. Nothing was installed,
built or downloaded.
Ways forward:
  1. Reply that the code is open source, or that this is research use — I record your words
     as the basis and show the CodeQL plan for approval.
  2. Scan locally now with static-analysis:semgrep (no build, no CodeQL licence needed).
  3. Use GitHub code scanning, which runs CodeQL in GitHub Actions under the repository's plan.
```

### 1. Preflight

`command -v codeql jq python3`, then `codeql --version`. If any is missing, name it and stop;
never install. For CodeQL, name the official routes only as information: the CodeQL bundle
from the `github/codeql-action` releases, `brew install --cask codeql`, or the `gh codeql`
extension. When the licence passed and the language is clear, also show the draft plan
(step 4), marked "blocked: codeql not installed", so the user sees what would run.

### 2. Output directory and existing databases

- Output: the user's path, else `$TMPDIR/codeql-<repo>_N` (`/tmp` when unset), `N` one above
  the highest existing suffix. Absolute, `mkdir -p`, outside the repo.
- Existing databases: `dbs=$("${CLAUDE_SKILL_DIR}/scripts/find_databases.sh"); rc=$?`. It
  searches the output-dir candidates, keeps only directories `codeql resolve database` accepts
  (a failed build leaves a marker file behind), and exits 2 when `codeql` is missing — an
  error, never "no database".

| Found | Do |
|---|---|
| none | full pipeline |
| one | ask: reuse it or build new |
| several | ask with at most four options: the three most recent plus "build new"; name the rest in text |
| user named one, or said "build new" | do that, no question |

"Scan" alone does not pick a database. The answer goes into the plan, not a separate round.

### 3. Language and build detection

Count source files per extension (Glob) and look for build files (`go.mod`, `Makefile`,
`CMakeLists.txt`, `pom.xml`, `build.gradle*`, `Cargo.toml`, `*.sln`/`*.csproj`,
`package.json`, `pyproject.toml`, build scripts, README build sections). Several languages →
ask which, or plan one database per language.

| Language id | Must the project build? | Build mode `none` |
|---|---|---|
| python, javascript (incl. TypeScript), ruby | no; accepts a `paths-ignore` config | n/a |
| go, swift | yes | rejected — never use it |
| java (incl. Kotlin), csharp, cpp, rust | yes | accepted, partial analysis, last resort |

Confirm with `codeql database create --help` when codeql is present; its help lists omit
none-mode support for cpp and rust, so trust the table for those.

### 4. Plan gate

Present one plan and wait. Show anything the user already chose as chosen.

```text
CodeQL plan
Licence:        MIT (LICENSE file)            | user statement: "<words>"
Language:       go (23 files, go.mod)
Database:       build new → /abs/tmp/codeql-repo_1/codeql.db
Build:          rung 1 autobuild: codeql database create "$DB" --language=go --source-root=.
                rung 2: --command="go build ./..."; the build runs project code and writes
                build artifacts in the working tree. No clean or dependency steps planned.
Mode:           [x] run-all   [ ] important-only
Query packs:    codeql/go-queries (official), trailofbits/go-queries,
                githubsecuritylab/codeql-go-queries   ← downloaded with `codeql pack download`
Model packs:    none (data extensions offered after the build)
Threat model:   remote (default)
Output:         /abs/tmp/codeql-repo_1/   (outside the repo)
Estimate:       ~5 min, database ~2–10× source size; free disk checked with df -h
Reply "yes" to run, or edit any line.
```

Pack choice per language, threat models and suites:
[references/query-suites.md](references/query-suites.md). Any step that deletes build directories in
the repo, installs project dependencies, or writes extension files into CodeQL's pack cache
must appear as its own plan line. Edits → present the whole plan again.

### 5. Download packs

After the yes, one call per pack: `codeql pack download <pack>`. A failed community pack is
reported and dropped from `INSTALLED_THIRD_PARTY_PACKS`; do not swap in another.

### 6. Build the database

Interpreted languages:

```bash
codeql database create "$DB" --overwrite --language=python \
  --codescanning-config="$OUTPUT_DIR/codeql-config.yml" --source-root=.
```

`codeql-config.yml` holds `paths-ignore` for vendored, generated and test paths. Compiled
languages climb the build ladder, each rung logged with `build_log.sh`, stopping at the first
success: autobuild → custom `--command` → multi-step trace → `--build-mode=none` (never go or
swift). On a failed rung, apply the fixes in order and retry the same rung. Full ladder, the
macOS arm64 exit-137 sub-ladder and the fixes: [references/build.md](references/build.md).

### 7. Quality gate

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_db_quality.py" --format=json -- "$DB"
```

| Exit | Meaning | Do |
|---|---|---|
| 0 | usable | continue |
| 1 | nothing to analyse | do not analyse; fix the build (next rung or the fixes) |
| 3 | extractor error ratio above 5% | look at which files failed; raise `--max-error-ratio` only with a logged reason |
| 4 | diagnostics format unknown | report it; the checker needs an update |

Compare `project_files` with the source count from step 3, never with `archive_files`. Ways to
improve a poor database are in [references/build.md](references/build.md#improving-a-poor-database).
All rungs exhausted → ask: accept the current state, user fixes the build, or abort.

### 8. Data extensions (optional)

Teach CodeQL the project's own sources, sinks, sanitisers and pass-through wrappers. First
check for existing model packs and skip creation if found. Otherwise enumerate, map, ask
(create all / select / skip), write YAML under `$OUTPUT_DIR/extensions/`, and prove the
models load by comparing finding counts with and without them. The workflow and column
formats: [references/extensions.md](references/extensions.md).

### 9. Analyse

Write `$OUTPUT_DIR/rulesets.txt` (mode, database, language, timestamp, then query packs,
model packs, threat models). Generate and verify the suite in the same call as the analysis:

```bash
set -e
OUTPUT_DIR=/abs/out; DB="$OUTPUT_DIR/codeql.db"; MODE=run-all
export CODEQL_LANG=go OUTPUT_DIR
export INSTALLED_THIRD_PARTY_PACKS="trailofbits/go-queries githubsecuritylab/codeql-go-queries"
SUITE=$("${CLAUDE_SKILL_DIR}/scripts/generate_suite.sh" "$MODE")
EXTRA=()
codeql database analyze "$DB" --format=sarif-latest --output="$OUTPUT_DIR/raw/results.sarif" \
  --threads=0 ${EXTRA[@]+"${EXTRA[@]}"} -- "$SUITE"
```

Fill `EXTRA` with the approved `--threat-model`, `--model-packs` and `--additional-packs`
flags; the guarded expansion is safe on bash 3.2 when it is empty. `set -e` keeps a failed analysis from leaving a truncated SARIF that later reads as zero
findings. `generate_suite.sh` exits 1 and deletes the suite if it resolves no queries.

### 10. Post-process and report

- run-all: `cp raw/results.sarif results/results.sarif`.
- important-only: `jq -f "${CLAUDE_SKILL_DIR}/scripts/important-only.jq" raw/results.sarif >
  results/results.sarif` — keeps high, very-high and unknown precision, and medium only with
  `security-severity` ≥ 6.0 (read from the rule, via `ruleIndex` and `toolComponent`).
- Summarise by level (resolved from rules: CodeQL results carry no `level`), by
  security-severity and by rule; `static-analysis:sarif-parsing` has the jq.
- Zero findings: check extraction (`project_files`), models, packs and suite filtering before
  saying anything about the code.

Report: output directory, database, language, mode, query packs, model packs, threat models,
extraction mode (`buildMode` in `codeql-database.yml`), counts by level, output paths,
licence basis, a coverage note for compiled languages (files the build did not compile were
not analysed), and that the quality gate and suite verification passed.

## Output layout

```text
$TMPDIR/codeql-<repo>_N/
  codeql.db/   build.log   codeql-config.yml   rulesets.txt
  diagnostics/ (enumeration queries, CSVs)   extensions/ (sources.yml, sinks.yml, summaries.yml)
  raw/<mode>.qls   raw/results.sarif (unfiltered)   results/results.sarif
```

## Excuses to reject

| Thought | Reality |
|---|---|
| "security-extended is enough" / "security-and-quality is broadest" | run-all imports security-and-quality and security-experimental plus community packs |
| "It built, so the database is good" | run the quality gate |
| "Standard frameworks need no extensions" | project wrappers hide sources and sinks |
| "`none` mode is fine for compiled code" / "use none on macOS instead of fixing 137" | it is partial; climb the ladder first |
| "Zero findings, so it is secure" | investigate extraction and suites first |
| "Use the pack's default suite" | its hidden filters can yield zero results |
| "Write output to the current directory" | `$TMPDIR` only |
| "Take the first database found" / "'scan' means reuse one" | apply the decision table |

## Near misses

- Quick single-file pattern checks, or code that will not build → `static-analysis:semgrep`.
- Reading or gating on SARIF that already exists → `static-analysis:sarif-parsing`.
- Turning on GitHub code scanning in a workflow is workflow editing, not this skill.
- Is a finding real? → `fp-check:fp-check`.
