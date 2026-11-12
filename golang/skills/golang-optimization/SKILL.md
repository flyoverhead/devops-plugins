---
name: golang-optimization
description: Optimises Go performance with evidence - b.Loop benchmarks compared with benchstat, pprof CPU, heap and goroutine profiles, escape analysis with -gcflags=-m=2, sync.Pool gotchas, GOMEMLIMIT and GOGC in containers, and PGO with default.pgo. Use when code is slow or allocates too much, when asked to profile, benchmark or reduce memory, or about pprof, GC tuning or PGO. Not for writing unit tests - use golang:test.
effort: high
paths: ["**/*.go"]
allowed-tools: Bash(go test:*) Bash(go tool pprof:*) Bash(go build:*) Bash(go vet:*) Bash(go list:*) Bash(benchstat:*) Bash(go tool trace:*) Read Write Edit Grep Glob
---

# Go performance, with evidence

No change is an optimisation until a before/after measurement on the same machine and toolchain says so. Read the module's Go version first (`go list -m -f '{{.GoVersion}}'`, fallback `grep -E '^(go|toolchain) ' go.mod`); the benchmark style depends on it. Never raise the `go` line or add a dependency silently.

## Checklist

- [ ] Find the hot path from evidence (a profile, a trace, a reported number), not from suspicion.
- [ ] Write or find a benchmark of that exact path with realistic input.
- [ ] Baseline: `go test -run '^$' -bench '^BenchmarkX$' -benchmem -count=10 ./<pkg> | tee old.txt`.
- [ ] Explain the cost: the `-benchmem` columns, escape analysis, `go tool pprof -list`.
- [ ] Change one thing; keep the tests green.
- [ ] Rerun into `new.txt` with the same flags.
- [ ] Compare: `benchstat old.txt new.txt`. Keep the change only when it shows `p < 0.05`; otherwise revert it.
- [ ] Report before and after `ns/op`, `B/op` and `allocs/op`, plus the benchstat lines. The literal `allocs/op` must appear in the final message.

If `benchstat` is not installed, ask before running `go install golang.org/x/perf/cmd/benchstat@latest`. Without it, report the medians of the ten runs and say the difference was not statistically tested.

## Benchmarks

On go 1.24 or later, write `for b.Loop()` and call `b.ReportAllocs()`. The compiler cannot optimise away work inside the loop, and setup before the loop is excluded from timing.

```go
func BenchmarkParseLine(b *testing.B) {
	line := "2026-11-03T10:15:00Z level=info msg=started id=42"
	b.ReportAllocs()
	for b.Loop() {
		fields := ParseLine(line)
		if len(fields) == 0 {
			b.Fatal("no fields parsed")
		}
	}
}
```

Below 1.24, use `for i := 0; i < b.N; i++` after `b.ResetTimer()` and store results in a package-level sink so the call is not eliminated. Never mix the two styles in one file.

- Always pass `-run '^$'` so tests do not run, and `-count=10` so benchstat has samples.
- Add `-cpu 1,4` when contention matters, and write `b.RunParallel` benchmarks for shared structures.
- Use an idle machine and the same toolchain for both runs. CI runners are too noisy for absolute numbers; compare relative changes only.

## Explain the cost

```bash
go build -gcflags=-m=2 ./<pkg> 2>&1 | grep -E 'escapes to heap|moved to heap'
```

Common causes of heap allocation:

- a returned pointer to a local;
- a value stored in an interface or `any`, including `fmt` arguments;
- a closure captured by a goroutine;
- a slice whose size is not a constant.

Fixes in order of cost: preallocate (`make([]T, 0, n)`, `strings.Builder.Grow`, `make(map[K]V, n)`), use `strings.SplitSeq` or `FieldsSeq` on 1.24+, avoid the interface conversion on the hot path. Inlining shows in `-gcflags=-m`; there is no `//go:inline` directive. Take a `-mutexprofile` or `-blockprofile` before replacing a `Mutex` with an `RWMutex` or sharding it. Commands for each profile are in [profiling.md](references/profiling.md).

## sync.Pool

Use it only for hot, short-lived objects that a heap profile shows dominating allocation.

- Pool pointers, not values (staticcheck SA6002).
- Call `Reset` after `Get`.
- Never use or alias an object after `Put`. Do not return `buf.Bytes()` after a deferred `Put`; copy first with `bytes.Clone` or `buf.String()`.
- Drop oversized objects instead of returning them, for example when `buf.Cap() > 64<<10`.
- The pool is emptied across GC cycles. It is a cache, not a free list.
- Never pool connections or locks.

## Runtime in containers

- Set `GOMEMLIMIT` to about 90% of the container limit (a 1 GiB pod gets `900MiB`). Leave `GOGC` at its default. `GOGC=off` together with a limit risks GC thrashing near the limit.
- `GOMAXPROCS` follows the cgroup CPU limit from go 1.25 when the main module's `go` line is 1.25 or later. Before that, use `go.uber.org/automaxprocs`. Never hard-code `runtime.GOMAXPROCS`.
- `net/http/pprof` registers its handlers on `http.DefaultServeMux` in `init`. Never serve `DefaultServeMux` publicly. Run the application on its own mux and pprof on `localhost:6060` or a cluster-internal address.

## PGO

1. Collect a CPU profile from production: `curl -o cpu.pprof 'http://<pod>:6060/debug/pprof/profile?seconds=30'`.
2. Merge several with `go tool pprof -proto a.pprof b.pprof > default.pgo`.
3. Commit `default.pgo` in the main package directory (`cmd/<name>/`). `-pgo=auto` has been the default since 1.21, so `go build` and goreleaser pick it up.
4. Verify with the benchmark checklist above.
5. Refresh it when hot paths change. A stale profile is safe; it just helps less.

## Limits

- `go test` and `go vet`: never `-exec`, `-toolexec`, `-vettool` or `-overlay`; they run other
  programs in place of the toolchain's own.
- `go build`: never `-toolexec`, `-overlay` or `-o`; they run other programs or write the
  binary over any path. `go build ./...` is enough to prove the code compiles.
