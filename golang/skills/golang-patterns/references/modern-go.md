# Go release to idiom lookup

## Contents

- How to use
- Language and library by release
- Behaviour gated by the go line
- Checking a release you do not know

## How to use

Read the module's Go version, then use every idiom at or below it. Never raise the `go` line to unlock an idiom without asking.

```bash
go list -m -f '{{.GoVersion}}'
```

Two separate gates apply. The compiler rejects newer language features according to the module's `go` line (`-lang`). New library calls are not gated by it: they compile whenever the installed toolchain has them and fail only on an older toolchain. Check both the `go` line and the toolchain that CI uses.

## Language and library by release

| Release | Use | Replaces |
|---|---|---|
| 1.20 | `errors.Join`; several `%w` verbs in one `fmt.Errorf` | hand-rolled multi-error types |
| 1.21 | `min`, `max`, `clear` builtins | helper functions and delete loops |
| 1.21 | `slices`, `maps`, `cmp` packages | `sort.Slice`, manual loops |
| 1.21 | `log/slog` | `log` with formatted strings |
| 1.21 | `sync.OnceFunc`, `OnceValue`, `OnceValues` | `sync.Once` plus captured results |
| 1.21 | `context.AfterFunc`, `context.WithoutCancel` | goroutines waiting on `ctx.Done()` |
| 1.21 | `toolchain` line; PGO on by default (`-pgo=auto`) | manual toolchain pinning |
| 1.22 | per-iteration loop variables | `v := v` copies |
| 1.22 | `for i := range n` | `for i := 0; i < n; i++` |
| 1.22 | `ServeMux` method and wildcard patterns (`"GET /items/{id}"`, `r.PathValue("id")`) | third-party routers for simple APIs |
| 1.22 | `math/rand/v2` | `math/rand` seeding |
| 1.23 | range-over-func: `iter.Seq`, `iter.Seq2` | callback-style walkers |
| 1.23 | `slices.Collect`, `slices.Sorted`, `maps.Keys`, `maps.Values` (iterators) | key-collecting loops |
| 1.23 | `unique` | hand-written interning maps |
| 1.23 | timers collected when unreferenced, unbuffered timer channels | `Stop` and drain dances |
| 1.24 | generic type aliases | duplicated alias declarations |
| 1.24 | `testing.B.Loop` | `for i := 0; i < b.N; i++` |
| 1.24 | `testing.T.Context` | `context.WithCancel` in tests |
| 1.24 | `omitzero` struct tag option | `omitempty` on structs and `time.Time` |
| 1.24 | `os.Root` | `filepath.Join` with untrusted input |
| 1.24 | `strings.SplitSeq`, `FieldsSeq`, `Lines` | `strings.Split` allocating a slice |
| 1.24 | `crypto/rand.Text` | hand-built random tokens |
| 1.24 | `runtime.AddCleanup` | `runtime.SetFinalizer` |
| 1.24 | `tool` directives in `go.mod` (`go get -tool`, `go tool <name>`) | `tools.go` blank imports |
| 1.25 | `sync.WaitGroup.Go` | `wg.Add(1)` plus `go func() { defer wg.Done() }` |
| 1.25 | `testing/synctest` (`synctest.Test`, `synctest.Wait`) | `time.Sleep` in concurrent tests |
| 1.25 | container-aware `GOMAXPROCS` | `automaxprocs` |
| 1.25 | `runtime/trace.FlightRecorder` | always-on full traces |
| 1.25 | vet analyzers `waitgroup`, `hostport` | review by eye |
| 1.26 | `new(expr)` | pointer helper functions |
| 1.26 | `errors.AsType[E]` | `var t *T; errors.As(err, &t)` |

## Behaviour gated by the go line

Some runtime behaviour follows the main module's `go` line, not the toolchain.

- Loop variables are per iteration only when the module declares `go 1.22` or later. Below that, closures and goroutines in a loop still share one variable.
- Timer channel semantics (unbuffered, collectable timers) apply at `go 1.23`. The `asynctimerchan` setting is removed in 1.27, where the new behaviour is unconditional.
- Container-aware `GOMAXPROCS` and its periodic update (`containermaxprocs`, `updatemaxprocs`) apply only when the main module declares `go 1.25` or later, and never when the `GOMAXPROCS` environment variable is set.

## Checking a release you do not know

- Read the release notes: `https://go.dev/doc/go1.N`.
- Find the release that introduced a symbol from the installed toolchain's API files:

  ```bash
  grep -F 'func SplitSeq' "$(go env GOROOT)/api/go1.24.txt"
  ```

- GODEBUG behaviour changes tied to the go line are listed in `"$(go env GOROOT)/doc/godebug.md"`.
