---
name: test
description: Writes Go tests that match the repository - table-driven tests with t.Run, the repo's existing assert or mock library, t.Context(), b.Loop benchmarks, testing/synctest for concurrent code - and runs them with the race detector until they pass. Use when asked to write, add or extend Go tests or coverage, such as "need test coverage for parse.go". Not for benchmarking an optimisation - use golang:golang-optimization.
argument-hint: "[package | file]"
paths: ["**/*.go"]
allowed-tools: Read Write Edit Grep Glob Bash(go test:*) Bash(go tool cover:*) Bash(go vet:*) Bash(go list:*)
---

Target: $ARGUMENTS

# Go tests

The target is a package path or a file. When empty, use what the user named, otherwise the package in the current directory.

## Checklist

- [ ] Read the module's Go version (`go list -m -f '{{.GoVersion}}'`, fallback `grep -E '^(go|toolchain) ' go.mod`).
- [ ] Detect the test libraries already in use:

  ```bash
  grep -rhoE '"(github.com/stretchr/testify|go.uber.org/mock|github.com/golang/mock|github.com/google/go-cmp)[^"]*"' --include=*_test.go . | sort -u
  ```

- [ ] Read the code under test and every existing `*_test.go` in the package.
- [ ] List the cases before writing: happy path, every error return, boundaries, empty and nil input, branches not yet covered.
- [ ] Write one `Test<Func>` per exported function, table-driven.
- [ ] Run `go vet ./<pkg> && go test -race -count=1 -run '<TestName>' ./<pkg>`. On a failure decide whether the test or the code is wrong: fix the test; report a code bug instead of encoding it in an assertion.
- [ ] Measure coverage: `go test -coverprofile=cover.out ./<pkg> && go tool cover -func=cover.out`. Add cases for uncovered branches that matter.
- [ ] Report the files, the test names, the final output and the coverage line.
- [ ] Delete `cover.out`.

If `-race` cannot run (`-race requires cgo`), run without it, say so, and do not claim the code is race-free.

## Rules

### Structure

- Name every subtest with `t.Run(tt.name, ...)`. A case struct has `name`, the inputs, `want`, and `wantErr` (a bool, or an error checked with `errors.Is`).
- Use the same package for internals. Use the `_test` package when only the exported API is exercised, and for Examples. Follow what the package already does.
- Failure messages read `Func(input) = got, want want`.
- `t.Fatalf` when the case cannot continue, `t.Errorf` otherwise.
- Helpers call `t.Helper()`. Cleanup goes through `t.Cleanup`, temporary files through `t.TempDir()`.
- Add `t.Parallel()` only when the package already does and the cases share no state.

### Library

- Use what the repo has. With testify: `require` for preconditions, `assert` for checks. With go-cmp: `cmp.Diff(want, got)` and print it as `(-want +got)`. For mocks use the repo's generator (`go.uber.org/mock`, mockery) or a small hand-written fake.
- With none of these present, use the standard library only. Do not add a test dependency without asking.
- Do not write a generic `AssertEqual(got, want interface{})` helper. `==` on interfaces panics for slices and maps and compares pointers by address. Use `slices.Equal`, `maps.Equal` or `reflect.DeepEqual` for plain data and `errors.Is` for errors.

### Version-dependent

- `t.Context()` (1.24+) instead of `context.Background()`. It is cancelled just before cleanups run.
- Benchmarks use `for b.Loop()` on 1.24+; below that, `b.N` after `b.ResetTimer()`.
- Concurrent or timer-driven code uses `testing/synctest` (1.25+) instead of `time.Sleep`. Below 1.25, synchronise with channels. Never sleep.

### Integration tests

- Put `//go:build integration` on the first line, then a blank line, then `package`. Never `// +build`.
- Skip when the dependency is absent: `t.Skip("EXAMPLE_API_URL not set")`. Credentials come from CI-injected environment, never from a literal.
- HTTP clients: test against `httptest.NewServer`. Handlers: `httptest.NewRecorder` with `httptest.NewRequestWithContext(t.Context(), ...)`.

### Fuzzing

For parsers and decoders, write `Fuzz<Func>`. Seed it with `f.Add` from the table cases and assert an invariant: no panic, a round trip, or a bound. Run it for a short time:

```bash
go test -run '^$' -fuzz '^FuzzX$' -fuzztime 10s ./<pkg>
```

Commit any crashers the fuzzer saves under `testdata/fuzz/`.

## Gotchas

- At go 1.22+ do not write `tt := tt`. Below 1.22, keep it when a subtest calls `t.Parallel()`.
- `-count=1` bypasses the test cache.
- `-run 'TestParse/empty_input'` is a regexp per level; spaces in subtest names become `_`.
- A test that passes alone but fails under `./...` shares global state. Fix the state, not the order.

Code to start from: [test-templates.md](references/test-templates.md).
