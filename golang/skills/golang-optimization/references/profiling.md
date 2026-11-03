# Profiling cookbook

## Contents

- From a benchmark
- From a running service
- Reading a profile
- Execution trace
- GC and memory at runtime

## From a benchmark

```bash
go test -run '^$' -bench '^BenchmarkX$' -cpuprofile cpu.out ./<pkg>
go test -run '^$' -bench '^BenchmarkX$' -memprofile mem.out ./<pkg>
go test -run '^$' -bench '^BenchmarkX$' -mutexprofile mutex.out -blockprofile block.out ./<pkg>
go test -run '^$' -bench '^BenchmarkX$' -trace trace.out ./<pkg>
```

- Add `-memprofilerate 1` to record every allocation. It is accurate and slow; use it for one run.
- The test binary `<pkg>.test` is written beside the profile. When pprof shows addresses instead of names, pass both: `go tool pprof <pkg>.test cpu.out`.

## From a running service

Expose pprof on a private listener, `127.0.0.1:6060`, never on the public mux. Kubernetes: `kubectl port-forward pod/<pod> 6060:6060`.

| Endpoint | Gives |
|---|---|
| `/debug/pprof/profile?seconds=30` | CPU profile |
| `/debug/pprof/heap` | live heap (`inuse_*`) and cumulative allocations |
| `/debug/pprof/allocs` | allocation sites since start |
| `/debug/pprof/goroutine?debug=2` | full goroutine stacks |
| `/debug/pprof/trace?seconds=5` | execution trace |

```bash
curl -o cpu.pprof 'http://127.0.0.1:6060/debug/pprof/profile?seconds=30'
go tool pprof -top -nodecount=20 cpu.pprof
```

The mutex and block profiles are empty until the program calls `runtime.SetMutexProfileFraction` and `runtime.SetBlockProfileRate`.

## Reading a profile

```bash
go tool pprof -top -nodecount=20 cpu.out
go tool pprof -list 'ParseLine$' cpu.out
go tool pprof -sample_index=alloc_space -top mem.out
go tool pprof -diff_base old.pprof new.pprof
go tool pprof -http=127.0.0.1:8081 cpu.out
```

- `-sample_index` takes `alloc_space`, `alloc_objects`, `inuse_space` or `inuse_objects` on heap profiles.
- `flat` is the time spent in the function itself; `cum` includes everything it calls. Optimise the largest `flat` entries in code you own. High `cum` in a caller only points to where to look.
- `-http` opens an interactive UI. Hand that command to the user instead of running it.
- Runtime internals are pointers, not targets: `runtime.mallocgc` means allocation pressure, `runtime.chanrecv` or `runtime.lock` means contention.

## Execution trace

```bash
go tool trace trace.out
```

Use the trace for latency spikes, scheduler delay and GC pauses, which a sampled CPU profile hides. On go 1.25+, `runtime/trace.FlightRecorder` keeps a rolling window in memory so a trace can be written when something slow happens, without paying for continuous tracing.

## GC and memory at runtime

```bash
GODEBUG=gctrace=1 ./<binary>
GOMEMLIMIT=900MiB GOGC=100 ./<binary>
```

`gctrace=1` prints one line per GC cycle with heap sizes and pause times. For in-process numbers prefer `runtime/metrics` (`/gc/heap/goal:bytes`, `/sched/latencies:seconds`) over `runtime.ReadMemStats`, which stops the world.
