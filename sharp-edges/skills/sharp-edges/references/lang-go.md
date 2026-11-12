# Go

Every entry: **Bites**, **Spot**, **Fix**. Read the `go` directive in `go.mod` before you start:
some edges depend on the language version.

## Contents

- Arithmetic and memory: wraparound, slice aliasing, unsafe conversions
- Values and errors: typed nil, JSON leniency, dropped errors
- Resources and concurrency: defer in loops, goroutine leaks, maps, loop variables
- Grep set

## Arithmetic and memory

### Silent integer wraparound

- **Bites:** `n * size` wraps instead of panicking, so a huge count yields a tiny allocation
  and the following copy runs past the intended bounds; fuzzers never see a crash.
- **Spot:** multiplication, addition or narrowing conversions (`int64` → `int32`) that feed
  `make`, slicing or length checks.
- **Fix:** `bits.Mul64` / `bits.Add64` with an overflow check, or explicit range checks first.

### Sub-slices share memory

- **Bites:** `buf[:n]` returned to a caller, then `append` within capacity, overwrites data
  another holder still reads.
- **Spot:** functions that return or store a slice of an internal buffer.
- **Fix:** `copy` into a fresh slice, or a full slice expression `buf[:n:n]`.

### String and byte views through unsafe

- **Bites:** `unsafe.String`/`unsafe.Slice` or `*(*string)(unsafe.Pointer(&b))` lets a later
  write to the bytes change a "constant" string, including map keys.
- **Spot:** `unsafe.Pointer` casts between strings and byte slices.
- **Fix:** plain `string(b)` / `[]byte(s)`; keep the unsafe form only in measured hot paths.

## Values and errors

### Typed nil inside an interface

- **Bites:** `func load() error { var e *ParseError; return e }` returns a non-nil `error`, so
  `if err != nil` always fires, or a nil check on an interface holding a nil pointer passes.
- **Spot:** functions with a concrete pointer variable returned as `error` or another interface.
- **Fix:** return the literal `nil` on success.

### Lenient JSON decoding

- **Bites:** `encoding/json` matches field names case-insensitively, keeps the last of
  duplicate keys and drops unknown keys, so `"verifyTLS": false` misspelled as
  `"verifyTls"` works and `"verfiyTLS"` is ignored without a word.
- **Spot:** `json.Unmarshal` / `json.NewDecoder` into security-relevant structs or request bodies.
- **Fix:** `dec.DisallowUnknownFields()`, a custom `UnmarshalJSON`, or a stricter decoder;
  validate the decoded struct.

### Errors dropped or shadowed

- **Bites:** `v, _ := parse(x)` keeps a zero value; `err :=` inside an `if` creates a new
  variable and the outer `err` stays nil; `defer f.Close()` on a writer loses the flush error.
- **Spot:** `, _ :=` and `, _ =`, `err :=` in inner scopes, bare `defer x.Close()` after writes.
- **Fix:** handle every error; close writers explicitly and check the result.

## Resources and concurrency

### defer inside a loop

- **Bites:** each iteration's `defer` runs only when the function returns: file descriptors
  pile up, locks stay held.
- **Spot:** `defer` lexically under `for`.
- **Fix:** move the body into a function or closure, or release explicitly at the end of each
  iteration.

### Goroutine left blocked after a timeout

- **Bites:** `go func() { ch <- work() }()` with `select` on `time.After`; after the timeout
  nobody receives, the sender blocks forever and memory grows.
- **Spot:** `go func` writing to an unbuffered channel read inside a `select` with a timeout or
  `ctx.Done()`.
- **Fix:** a buffer of one, or a send that also selects on `ctx.Done()`.

### Maps shared between goroutines

- **Bites:** concurrent writes, or a write during a read, crash the process with a fatal error
  that `recover` cannot catch.
- **Spot:** package-level or struct maps touched from handlers or goroutines without a lock.
- **Fix:** `sync.Mutex`/`sync.RWMutex` around access, or `sync.Map` for append-mostly caches.

### Loop variable captured by closures

- **Bites:** before Go 1.22, every closure created in a `for` loop shares one variable and sees
  its last value.
- **Spot:** only when `go.mod` says `go 1.21` or lower: `go func` or closures using the loop
  variable. Report nothing for 1.22 or later.
- **Fix:** raise the `go` directive, or shadow the variable (`v := v`).

## Grep set

```bash
grep -rn --include='*.go' -E 'defer ' .
grep -rn --include='*.go' -E 'json\.(Unmarshal|NewDecoder)' .
grep -rn --include='*.go' -E ', _ :?= ' .
grep -rn --include='*.go' -E 'unsafe\.(Pointer|String|Slice)' .
grep -rn --include='*.go' -E 'go func\(' .
```

For `defer`, keep only hits inside a `for` body.
