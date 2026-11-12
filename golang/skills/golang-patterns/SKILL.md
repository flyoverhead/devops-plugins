---
name: golang-patterns
description: Applies idiomatic Go conventions when refactoring or writing Go - functional options when a constructor or function parameter list keeps growing, error wrapping, generics versus interfaces, context handling, module paths and GOPRIVATE, goreleaser v2 releases, log/slog, and idioms gated by the go line in go.mod. Use when cleaning up or refactoring Go code, designing a package API, reviewing for idiom, or setting up a Go module. Not for concurrency - use golang:golang-concurrency; not for performance - use golang:golang-optimization.
paths: ["**/*.go", "**/go.mod"]
allowed-tools: Bash(go vet:*) Bash(go build:*) Bash(go test:*) Bash(gofmt:*) Bash(go list:*) Read Edit Grep Glob
---

# Go idioms and conventions

Write Go the way the module's own `go` line allows, and the way the surrounding package already reads. Match local style before applying a general rule.

## Checklist

- [ ] Read the module's Go version (next section).
- [ ] Read the whole package and grep for callers before changing any exported identifier.
- [ ] Apply the rules below, smallest change first.
- [ ] Run the validate command and loop until it is clean.
- [ ] Report what changed as `path:line`, what was not changed on purpose, and the validate output.

## Read the version first

```bash
go list -m -f '{{.GoVersion}}'
```

Fallback when that prints nothing: `grep -E '^(go|toolchain) ' go.mod`. Idioms are gated by this number; see [modern-go.md](references/modern-go.md) for the release table.

- Never raise the `go` line as a side effect. Importers inherit the requirement, so a bump is a breaking change. Ask first.
- Never add a `toolchain` line or a new dependency without saying so.

## Conventions

- The module path equals the canonical import path: `github.com/<owner>/<repo>`, or the path on a self-hosted forge host. A repo that already uses a bare name (`module tool`) keeps it; do not rename without asking.
- Private modules: `GOPRIVATE` lists the private hosts. Authenticate with a token in `~/.netrc` or with SSH. Credentials never go in the module path or in a `replace`. CI exports `GOPRIVATE`, `GOPROXY` and `GOTOOLCHAIN=auto` as environment variables.
- Releases: goreleaser config with `version: 2`, GitHub Releases published from a tag workflow, `CGO_ENABLED=0`, `-trimpath`, version injected with `-ldflags -X`. Sign checksums with a GPG key from the CI secrets `GPG_PRIVATE_KEY` and `GPG_PASSPHRASE`; the key is never committed.
- Forks of third-party providers: leave the upstream layout untouched. Keep local changes as `.patch` files applied at build time. Never edit vendored upstream code in place.
- Logging: `log/slog` for new code, with the JSON handler in services. When the repo already uses logrus or zap, follow it.
- Secrets come from a secret manager at runtime (for example the HashiCorp Vault API) or from CI-injected environment. Never as defaults in code, flag defaults or fixtures.

## Decision rules

### Constructors and options

- More than 3 optional parameters: functional options. Required values stay positional.
- 2 or 3 optional parameters: a `Config` struct whose zero value is useful.

```go
type Option func(*config)

func WithTimeout(d time.Duration) Option { return func(c *config) { c.timeout = d } }

func New(endpoint string, opts ...Option) (*Client, error) {
	cfg := config{timeout: 10 * time.Second}
	for _, opt := range opts {
		opt(&cfg)
	}
	if cfg.timeout <= 0 {
		return nil, errors.New("timeout must be positive")
	}
	return &Client{endpoint: endpoint, cfg: cfg}, nil
}
```

Set defaults before the loop, validate after it and return an error. Keep `Option` and the `With...` functions in the same file as the constructor.

### Generics versus interfaces

- Use generics only when the body does not depend on the concrete type: containers, `Map`/`Filter`, pipeline stages.
- When the body calls methods on the value, take an interface instead.
- Prefer the standard `slices`, `maps`, `cmp` packages and the `min`/`max` builtins (1.21+). `maps.Keys` returns an iterator since 1.23; wrap it in `slices.Collect` or `slices.Sorted`.

### Interfaces

- Define the interface where it is consumed, with only the methods that consumer calls.
- Return concrete types from constructors.

### Errors

- Wrap with `%w` inside a module. At a public boundary where callers must not depend on the cause, use `%v` or return an exported sentinel or typed error.
- Messages are lowercase, carry no trailing punctuation, put context first and do not chain "failed to".
- `errors.Join` for several independent failures; `errors.Is` and `errors.As` to inspect (`errors.AsType[*T]` on 1.26+).
- Handle an error or return it, once. Never log and return.

### Context

- First parameter of anything that does I/O or blocks.
- Never stored in a struct, never nil (`context.TODO()` while plumbing).
- Always call the cancel function: `defer cancel()`.
- `WithValue` only for request-scoped data, keyed by an unexported type.

### Modules and workspaces

- No committed `go.work` in a single-module repo; CI sets `GOWORK=off`.
- No local-path `replace` on a branch that reaches main.
- Run `go mod tidy` after import changes and commit `go.sum`.
- `go get <dep>@latest` can raise the `go` line (`go: upgraded go 1.25 => 1.26.0`). Inspect the `go.mod` diff and pin an older tag if it moved.

## Validate

```bash
gofmt -l . && go vet ./... && go build ./... && go test ./...
```

`gofmt -l` exits 0 even when it lists files, so any output is a failure. Run `gofmt -w` on the listed files, then rerun the whole command until it is clean.

## Limits

- `go test` and `go vet`: never `-exec`, `-toolexec`, `-vettool` or `-overlay`; they run other
  programs in place of the toolchain's own.
- `go build`: never `-toolexec`, `-overlay` or `-o`; they run other programs or write the
  binary over any path. `go build ./...` is enough to prove the code compiles.
