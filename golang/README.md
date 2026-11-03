# golang

Go toolkit for Claude Code: version-aware idioms, race and leak fixes, evidence-based performance work, read-only review, tests, and a project scaffold.

```text
/plugin install golang@devops
```

## Skills

| Skill | Use it to |
|---|---|
| `golang:golang-patterns` | Refactor or write idiomatic Go: functional options, error wrapping, generics versus interfaces, module paths, goreleaser v2, idioms allowed by the `go` line |
| `golang:golang-concurrency` | Fix `DATA RACE`, deadlocks and goroutine leaks; add bounded fan-out with errgroup; test with `testing/synctest` |
| `golang:golang-optimization` | Cut time and allocations with `b.Loop` benchmarks, benchstat, pprof, escape analysis, GC tuning and PGO |
| `golang:review` | Review Go code read-only and get `path:line` findings by severity, backed by vet, staticcheck, golangci-lint, govulncheck and gosec |
| `golang:test` | Write table-driven tests that follow the repository's libraries, run under the race detector |
| `golang:scaffold` | Create a CLI, service or library on GitHub with CI, release workflow, goreleaser and a GHCR image. Invoked only as `/golang:scaffold <name> <cli\|service\|library> [module-path]` |

## Agents

- `golang:golang-pro`: implements multi-file Go changes and verifies them.
- `golang:golang-architect`: design decisions and trade-offs for services; writes no code.
- `golang:golang-performance`: service-wide profiling and benchmark investigations.

## Hooks

- After every `Edit` or `Write` of a `.go` file: `gofmt -w` on the file, then `go vet .` on its package; vet findings are reported back to Claude. Vendored and `.pb.go` files are skipped.
- At session start: reports the Go toolchain version, `GOROOT` and `GOPATH`.

## Required tools

- `go`, with `gofmt` (required).
- `jq` (used by the hooks).
- Optional: `gopls`, configured in `.lsp.json`; `staticcheck`; `golangci-lint`; `govulncheck`; `gosec`; `benchstat`.
