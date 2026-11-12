# Changelog

## 2026-11-12

### Changed

- Skills that pre-allow `go test` or `go vet` name the forbidden flags (`-exec`, `-toolexec`, `-vettool`, `-overlay`); `review` also forbids `--output` and `--ext-diff` on `git diff`/`git log`.
- Skills and agents that pre-allow `go build` forbid `-toolexec`, `-overlay` and `-o` on it. `review` passes `--no-ext-diff --no-textconv` on every documented `git diff`.
- Agents: Bash is limited to the commands each one uses. `golang-pro`: `gofmt`, `go vet`, `go build`, `go test`, `go list`, `go mod tidy`. `golang-performance`: `go test`, `go build`, `go list`, `go tool pprof`, `go tool trace`, `benchstat`, `kubectl port-forward`. `golang-architect`: `go list`, `go mod graph`.

## 2026-11-03

### Added

- Skills: `golang-patterns` (version-gated idioms, functional options, errors, context, modules), `golang-concurrency` (race fixes proven with `go test -race -count=10`, errgroup, `synctest`), `golang-optimization` (`b.Loop` benchmarks, benchstat, pprof, PGO), `review` (read-only, forked), `test` (table-driven, repo-aware) and `scaffold` (user-invoked cli, service and library projects).
- Scaffold templates for GitHub Actions CI and release, goreleaser v2 (one binary per OS and architecture in each archive), a Debian 13 slim image with CA certificates running as non-root, golangci-lint v2 and a CI govulncheck pinned to v1.9.0.
- Agents: `golang-pro`, `golang-architect` and `golang-performance`.
- Hooks: `gofmt` and `go vet` after Go edits; a session-start report of the Go toolchain in the `hookSpecificOutput` shape.
- LSP configuration for gopls.
