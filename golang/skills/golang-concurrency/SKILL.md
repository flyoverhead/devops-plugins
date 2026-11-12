---
name: golang-concurrency
description: Fixes Go data races, deadlocks and goroutine leaks and writes concurrent Go - race fixes proven with go test -race -count=10, errgroup with SetLimit, WaitGroup.Go, context cancellation, channel ownership, copylocks and Add-before-go gotchas, testing/synctest. Use when go test -race fails or prints DATA RACE, when adding goroutines or a worker pool, running work in parallel with a limit, or fixing a deadlock or leak. Not for allocation or CPU tuning - use golang:golang-optimization.
effort: high
paths: ["**/*.go"]
allowed-tools: Bash(go test:*) Bash(go vet:*) Bash(go build:*) Bash(go list:*) Read Edit Grep Glob
---

# Go concurrency

A race fix is proven by the race detector, not by reading the code. Read the module's Go version first (`go list -m -f '{{.GoVersion}}'`, fallback `grep -E '^(go|toolchain) ' go.mod`): loop variable semantics, `WaitGroup.Go` and `synctest` depend on it. Never raise the `go` line or add a dependency silently.

## Checklist

- [ ] Reproduce: `go test -race -count=1 -run <Test> ./<pkg>`. Keep the first `DATA RACE` block; it holds the two conflicting stacks.
- [ ] Name the shared state and the one owner that should guard it.
- [ ] Pick the primitive from the decision table.
- [ ] Fix the code under test, not the test, unless the test itself races.
- [ ] Prove: `go vet ./... && go test -race -count=10 ./<pkg>`; loop until both exit 0.
- [ ] Run `go test -race ./...` once for the whole module.
- [ ] Report both access locations, the fix, and the final command output.

When `-race` fails with `-race requires cgo` (cgo disabled or no C compiler), say so, run `go vet ./...` and `go test -count=10 ./...`, and state that the race is NOT proven fixed.

## Decision rules

| Situation | Use |
|---|---|
| Shared map or struct | `sync.Mutex` owned by the type that holds the data. `RWMutex` only when reads dominate and the critical section is long; measure first. |
| Single counter or flag | Typed `atomic.Int64` or `atomic.Bool` (1.19+), not `atomic.AddInt64` on a plain field. |
| Bounded fan-out that can fail | `golang.org/x/sync/errgroup`: `errgroup.WithContext`, `SetLimit(n)`, `Go`, `return g.Wait()`. |
| Fan-out without errors | `sync.WaitGroup`; `wg.Go(f)` on 1.25+. |
| Stream of items | Pipeline of channels; each stage closes its own output. |
| Lazy one-time init that can fail | `sync.OnceValues` (1.21+), not `sync.Once` plus a captured error. |
| Cancellation | `context.Context`; every blocking send or receive also selects on `ctx.Done()`. |
| Rate limit | `golang.org/x/time/rate`, `Limiter.Wait(ctx)`. |

- An unbounded `go f(item)` over input you do not control is a bug.
- `errgroup.Go` blocks once the limit is reached, so the submit loop is the back-pressure. Do not add a second semaphore.

Code for each pattern is in [patterns.md](references/patterns.md).

## Gotchas

- Loop variables are per iteration at go 1.22+; no copies needed. Below 1.22, copy them.
- Call `wg.Add` before the `go` statement, never inside the goroutine (vet `waitgroup` flags it on 1.25+).
- Structs holding a `Mutex`, `WaitGroup` or atomic are not copyable. Use pointer receivers (vet `copylocks`).
- Only the sender closes a channel, and only once. With several senders, start one closer goroutine that runs after `wg.Wait()`.
- A nil channel blocks forever, which disables that `select` case on purpose.
- A buffer is a throughput decision, not a fix. Use 0 or 1 unless the bound has a name.
- `time.After` in a loop allocates a timer per iteration; use one `time.Timer` or `time.Ticker`.
- `fatal error: concurrent map writes` means an unguarded map. `sync.Map` fits only write-once/read-many or disjoint keys.
- `defer mu.Unlock()` inside a loop runs at function return, not per iteration. Extract the body into a function.

## Goroutine leaks

A leak is a goroutine nothing can unblock. To find one:

- Dump stacks: `GOTRACEBACK=all` on a crash, `kill -QUIT <pid>`, or `/debug/pprof/goroutine?debug=2` on a private pprof listener.
- Group the goroutines by blocking line. A count that grows between dumps is the leak.

In tests use `testing/synctest` (1.25+): `synctest.Test(t, func(t *testing.T) { ... synctest.Wait() ... })`. Time is fake, the test fails when the bubble deadlocks (every goroutine is durably blocked and no timer is pending to advance the clock), and it waits for the bubble's goroutines to exit. Every goroutine needs a documented exit condition. Example: [synctest](references/patterns.md#synctest).

## Limits

- `go test` and `go vet`: never `-exec`, `-toolexec`, `-vettool` or `-overlay`; they run other
  programs in place of the toolchain's own.
- `go build`: never `-toolexec`, `-overlay` or `-o`; they run other programs or write the
  binary over any path. `go build ./...` is enough to prove the code compiles.
