# Changelog

## 2026-11-03

### Added

- Skills: `golang-patterns` (version-gated idioms, functional options, errors, context, modules), `golang-concurrency` (race fixes proven with `go test -race -count=10`, errgroup, `synctest`), `golang-optimization` (`b.Loop` benchmarks, benchstat, pprof, PGO), `review` (read-only, forked), `test` (table-driven, repo-aware) and `scaffold` (user-invoked cli, service and library projects).
- Scaffold templates for GitHub Actions CI and release, goreleaser v2 (one binary per OS and architecture in each archive), a Debian 13 slim image with CA certificates running as non-root, golangci-lint v2 and a CI govulncheck pinned to v1.9.0.
- Agents: `golang-pro`, `golang-architect` and `golang-performance`.
- Hooks: `gofmt` and `go vet` after Go edits; a session-start report of the Go toolchain in the `hookSpecificOutput` shape.
- LSP configuration for gopls.
