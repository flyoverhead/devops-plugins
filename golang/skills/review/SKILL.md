---
name: review
description: Reviews Go code read-only for correctness, security, concurrency and idiom - runs go vet, staticcheck, golangci-lint, govulncheck and gosec when installed and reports findings as path:line with a severity. Use when asked to review or look over Go code, a Go diff or a Go file before an MR. Not for rewriting the code - use golang:golang-patterns.
argument-hint: "[path | git-range]"
context: fork
agent: golang:golang-pro
paths: ["**/*.go"]
allowed-tools: Read Grep Glob Bash(git diff:*) Bash(git log:*) Bash(git status:*) Bash(go vet:*) Bash(go list:*) Bash(staticcheck:*) Bash(golangci-lint run:*) Bash(govulncheck:*) Bash(gosec:*) Bash(command -v:*)
---

Review target: $ARGUMENTS

# Go code review

Report problems; never fix them. Paths are relative to the user's repository (the current directory), not to this skill. The review runs forked with no conversation history, so `$ARGUMENTS` is all the context there is.

## Checklist

- [ ] Resolve the target and note which rule was used.
- [ ] Read the module's Go version (`go list -m -f '{{.GoVersion}}'`, fallback `grep -E '^(go|toolchain) ' go.mod`).
- [ ] Run every installed tool.
- [ ] Read every in-scope file in full, and the callers of any changed exported identifier.
- [ ] Walk the areas under "What to look for".
- [ ] Drop findings that have no line number; merge duplicates.
- [ ] Write the report.

## Read-only

Never edit, write, format or commit. Never run `go mod tidy`, `gofmt -w`, or any tool with `--fix`. The tool list in the frontmatter has no write access on purpose. Never pass `--output` or `--ext-diff` to `git diff` or `git log`, nor `-vettool` or `-toolexec` to `go vet`: they write files or run other programs.

## Target

1. A path: its `.go` files, recursively, skipping `vendor/` and generated files (a header comment `Code generated ... DO NOT EDIT.`).
2. A git range or commit: `git diff --no-ext-diff --no-textconv <range> -- '*.go'`, plus enough surrounding code to judge each hunk.
3. Empty: `git diff --no-ext-diff --no-textconv --merge-base origin/main -- '*.go'`. If that fails, the changed `.go` files from `git status --short`. If there are none, every `.go` file under the current directory.

State which rule applied.

## Tools

Check each with `command -v` and run only those that exist:

| Tool | Command |
|---|---|
| go vet | `go vet ./...` |
| staticcheck | `staticcheck ./...` |
| golangci-lint | `golangci-lint run ./...` (uses the repo's config) |
| govulncheck | `govulncheck ./...` (needs network access to vuln.go.dev) |
| gosec | `gosec -quiet ./...` |

- A missing tool is a line in the report, not a reason to stop.
- Limit tool output to the target.
- If a tool fails, report its first error line. A build error is itself a Critical finding.

## What to look for

- **Correctness**: ignored errors, including those discarded with `_` (`rows, _ := db.Query(...)`, `_ = f.Close()` on a writer); `defer` inside loops; writes to a nil map; shadowed `err`; slice aliasing after `append`; integer conversion overflow; `time.Now()` values compared with `==`.
- **Concurrency**: unlocked shared state; `wg.Add` inside the goroutine; goroutines with no exit; channels closed by the receiver; copied sync types; loop variable capture below go 1.22. Point to `golang:golang-concurrency` for the fix.
- **Security**:
  - A secret literal is Critical. The fix is to read it at runtime from a secret manager such as HashiCorp Vault through its API, or from a CI-injected value, and to rotate the exposed secret. Quote the identifier in the report, never the value.
  - SQL built with `+` or `Sprintf`: use placeholders with `QueryContext`.
  - `exec.Command("sh", "-c", ...)` with external input.
  - `filepath.Join(base, userInput)`: use `os.Root` (1.24+) or `filepath.IsLocal`.
  - `math/rand` for tokens: use `crypto/rand` (`rand.Text()` on 1.24+).
  - `InsecureSkipVerify: true`.
  - `http.ListenAndServe` without timeouts.
  - Unbounded `io.ReadAll` of a request body.
  - `net/http/pprof` on a public mux.
- **Performance**: only what is visible without a profile: allocation in hot loops, `regexp.MustCompile` per call, `+=` string loops, missing preallocation. Anything else: recommend `golang:golang-optimization`.
- **Idiom and API**: point to `golang:golang-patterns`.
- **Tests**: changed behaviour without a test change, tests that sleep, tests without assertions. Point to `golang:test`.

## Severity

| Level | Meaning |
|---|---|
| Critical | exploitable vulnerability, leaked secret, data loss, build failure |
| High | production bug: race, leak, ignored write-path error, wrong result |
| Medium | likely future bug or maintenance hazard |
| Low | idiom, naming, documentation |

## Report

Plain text, no emoji. One finding per line, most severe first:

```
path:line — Severity — finding — fix
```

Then three sections:

- **Tools**: one line per tool: clean, N findings, not installed, or failed with its first error line.
- **Scope**: how the target was resolved and the number of files read.
- **Not checked**: anything skipped and why.

No praise section and no rewritten files. With no findings, say so and list the tools that ran.

Example, with neutral values:

```
store/user.go:48 — Critical — query built with fmt.Sprintf from the name argument (SQL injection) — use db.QueryContext(ctx, "SELECT ... WHERE name = $1", name)
store/user.go:12 — Critical — const dbPassword holds a credential — read it at runtime from Vault or a CI-injected variable, and rotate it
store/user.go:51 — High — error from rows.Err() ignored — check and return it

Tools: go vet - 1 finding; staticcheck - not installed; govulncheck - clean
Scope: git diff --no-ext-diff --no-textconv --merge-base origin/main, 3 files
Not checked: runtime behaviour, database schema
```
