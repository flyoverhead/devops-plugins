# Test templates

## Contents

- Table-driven test
- HTTP handler test
- Concurrent code with synctest
- Fuzz test

Standard library only, written for `go 1.25`. Each section compiles on its own and passes `go test -race`. Replace the example functions with the code under test and keep the shape.

## Table-driven test

Code under test, a size parser with sentinel errors:

```go
package sizes

import (
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
)

var (
	ErrEmpty  = errors.New("empty size")
	ErrSyntax = errors.New("invalid size")
	ErrUnit   = errors.New("unknown unit")
	ErrRange  = errors.New("size out of range")
)

var units = map[string]int64{"B": 1, "KiB": 1 << 10, "MiB": 1 << 20, "GiB": 1 << 30}

func ParseSize(s string) (int64, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0, ErrEmpty
	}
	i := 0
	for i < len(s) && s[i] >= '0' && s[i] <= '9' {
		i++
	}
	if i == 0 {
		return 0, fmt.Errorf("%w: %q", ErrSyntax, s)
	}
	n, err := strconv.ParseInt(s[:i], 10, 64)
	if err != nil {
		return 0, fmt.Errorf("%w: %q", ErrRange, s)
	}
	mult, ok := units[strings.TrimSpace(s[i:])]
	if !ok {
		return 0, fmt.Errorf("%w: %q", ErrUnit, s[i:])
	}
	if n > math.MaxInt64/mult {
		return 0, fmt.Errorf("%w: %q", ErrRange, s)
	}
	return n * mult, nil
}
```

The test covers valid input, both boundaries, empty input and each failure class. `wantErr` holds the sentinel; `nil` means success.

```go
package sizes

import (
	"errors"
	"testing"
)

func TestParseSize(t *testing.T) {
	cases := []struct {
		name    string
		in      string
		want    int64
		wantErr error
	}{
		{name: "bytes", in: "512B", want: 512},
		{name: "kibibytes", in: "4KiB", want: 4096},
		{name: "space before unit", in: "2 MiB", want: 2 << 20},
		{name: "zero", in: "0B", want: 0},
		{name: "largest GiB value", in: "8589934591GiB", want: 8589934591 << 30},
		{name: "one past the largest", in: "8589934592GiB", wantErr: ErrRange},
		{name: "empty", in: "", wantErr: ErrEmpty},
		{name: "only spaces", in: "   ", wantErr: ErrEmpty},
		{name: "no digits", in: "KiB", wantErr: ErrSyntax},
		{name: "no unit", in: "10", wantErr: ErrUnit},
		{name: "unknown unit", in: "1XB", wantErr: ErrUnit},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseSize(tc.in)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("ParseSize(%q) error = %v, want %v", tc.in, err, tc.wantErr)
			}
			if got != tc.want {
				t.Errorf("ParseSize(%q) = %d, want %d", tc.in, got, tc.want)
			}
		})
	}
}
```

`errors.Is(err, nil)` is true only when `err` is nil, so one assertion covers both the success and the failure rows.

## HTTP handler test

A hand-written fake replaces the store. The test goes through the real mux, so route patterns and path values are exercised too.

```go
package lookup

import (
	"fmt"
	"net/http"
)

type Store interface {
	Get(key string) (string, bool)
}

func NewHandler(s Store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /kv/{key}", func(w http.ResponseWriter, r *http.Request) {
		v, ok := s.Get(r.PathValue("key"))
		if !ok {
			http.NotFound(w, r)
			return
		}
		fmt.Fprint(w, v)
	})
	return mux
}
```

```go
package lookup

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

type fakeStore map[string]string

func (f fakeStore) Get(key string) (string, bool) {
	v, ok := f[key]
	return v, ok
}

func TestHandlerGet(t *testing.T) {
	h := NewHandler(fakeStore{"region": "eu-1"})
	cases := []struct {
		name     string
		path     string
		wantCode int
		wantBody string
	}{
		{name: "found", path: "/kv/region", wantCode: http.StatusOK, wantBody: "eu-1"},
		{name: "missing", path: "/kv/zone", wantCode: http.StatusNotFound},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequestWithContext(t.Context(), http.MethodGet, tc.path, nil)
			rec := httptest.NewRecorder()
			h.ServeHTTP(rec, req)
			if rec.Code != tc.wantCode {
				t.Fatalf("GET %s status = %d, want %d", tc.path, rec.Code, tc.wantCode)
			}
			if tc.wantBody != "" && rec.Body.String() != tc.wantBody {
				t.Errorf("GET %s body = %q, want %q", tc.path, rec.Body.String(), tc.wantBody)
			}
		})
	}
}
```

For an HTTP client, point it at `httptest.NewServer(handler)` and register `t.Cleanup(srv.Close)` right after creating the server. Pass `srv.URL` to the client under test.

## Concurrent code with synctest

A retry loop with hour-long backoff would be untestable with real sleeps. Inside a `synctest` bubble the clock is fake, so the test cancels the loop while it waits and checks that it exits.

```go
package retry

import (
	"context"
	"time"
)

func Retry(ctx context.Context, attempts int, base time.Duration, fn func(context.Context) error) error {
	delay := base
	var err error
	for range attempts {
		if err = fn(ctx); err == nil {
			return nil
		}
		timer := time.NewTimer(delay)
		select {
		case <-timer.C:
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		}
		delay *= 2
	}
	return err
}
```

```go
package retry

import (
	"context"
	"errors"
	"testing"
	"testing/synctest"
	"time"
)

func TestRetryStopsOnCancel(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ctx, cancel := context.WithCancel(t.Context())
		calls := 0
		fail := func(context.Context) error {
			calls++
			return errors.New("unavailable")
		}

		done := make(chan error, 1)
		go func() { done <- Retry(ctx, 10, time.Hour, fail) }()

		synctest.Wait()
		cancel()

		if err := <-done; !errors.Is(err, context.Canceled) {
			t.Fatalf("Retry error = %v, want context.Canceled", err)
		}
		if calls != 1 {
			t.Errorf("calls = %d, want 1", calls)
		}
	})
}
```

`synctest.Wait` returns once the retry goroutine is blocked on its first backoff, so `calls` is stable when read. No real time passes.

## Fuzz test

Seed the corpus from the table cases, then assert properties that must hold for every input rather than specific outputs.

```go
package sizes

import (
	"errors"
	"testing"
)

func FuzzParseSize(f *testing.F) {
	for _, seed := range []string{"512B", "4KiB", "0B", "", "KiB", "1XB", "8589934592GiB", "-1B"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, in string) {
		got, err := ParseSize(in)
		if err == nil {
			if got < 0 {
				t.Fatalf("ParseSize(%q) = %d, want non-negative", in, got)
			}
			return
		}
		if !errors.Is(err, ErrEmpty) && !errors.Is(err, ErrSyntax) &&
			!errors.Is(err, ErrUnit) && !errors.Is(err, ErrRange) {
			t.Fatalf("ParseSize(%q) returned an unclassified error: %v", in, err)
		}
	})
}
```

Run it with `go test -run '^$' -fuzz '^FuzzParseSize$' -fuzztime 10s ./<pkg>`. When the fuzzer finds a failure it writes the input to `testdata/fuzz/<FuzzName>/<hash>`. Commit that file; plain `go test` replays it as a regression test.
