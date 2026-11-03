# Concurrency patterns

## Contents

- Bounded fan-out with errgroup
- Worker pool with results
- Pipeline stage
- Fan-in
- synctest

All templates assume `go 1.25` in the module. For an older module:

- Below 1.25: replace `wg.Go(f)` with `wg.Add(1)` before the `go` statement and `defer wg.Done()` inside it.
- Below 1.22: copy each loop variable (`id := id`) before the closure uses it.
- Below 1.22, `for range workers` (range over an integer) does not compile; use `for i := 0; i < workers; i++`.

## Bounded fan-out with errgroup

The first error cancels the derived context, so the remaining calls can stop early. `SetLimit` caps how many run at once; `Go` blocks while the cap is reached, which throttles the submit loop.

```go
package fanout

import (
	"context"
	"fmt"

	"golang.org/x/sync/errgroup"
)

type Quote struct {
	Symbol string
	Price  float64
}

func Quotes(ctx context.Context, symbols []string, limit int,
	get func(context.Context, string) (Quote, error)) ([]Quote, error) {
	out := make([]Quote, len(symbols))
	g, ctx := errgroup.WithContext(ctx)
	g.SetLimit(limit)
	for i, sym := range symbols {
		g.Go(func() error {
			q, err := get(ctx, sym)
			if err != nil {
				return fmt.Errorf("quote %s: %w", sym, err)
			}
			out[i] = q
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return nil, err
	}
	return out, nil
}
```

Each goroutine writes its own slice index, so no lock is needed. `go get golang.org/x/sync@latest` can raise the `go` line in `go.mod`; check the diff and choose an older tag if it moved.

## Worker pool with results

Rules the code follows: the caller closes `jobs`; the pool closes the result channel only after every worker has exited; every send and receive also watches `ctx.Done()`.

```go
package fanout

import (
	"context"
	"sync"
)

func Pool[J, R any](ctx context.Context, workers int, jobs <-chan J,
	do func(context.Context, J) R) <-chan R {
	results := make(chan R)
	var wg sync.WaitGroup
	for range workers {
		wg.Go(func() {
			for {
				select {
				case <-ctx.Done():
					return
				case job, ok := <-jobs:
					if !ok {
						return
					}
					select {
					case results <- do(ctx, job):
					case <-ctx.Done():
						return
					}
				}
			}
		})
	}
	go func() {
		wg.Wait()
		close(results)
	}()
	return results
}
```

## Pipeline stage

A stage owns its output channel: it creates it, closes it, and never lets a send outlive the context.

```go
package fanout

import "context"

func Stage[I, O any](ctx context.Context, in <-chan I, f func(I) O) <-chan O {
	out := make(chan O)
	go func() {
		defer close(out)
		for v := range in {
			select {
			case out <- f(v):
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}
```

A stage that returns early on cancellation leaves its upstream sender blocked unless the upstream also watches `ctx`. Pass the same context to every stage.

## Fan-in

Several senders share one output, so none of them may close it. One closer goroutine waits for all of them.

```go
package fanout

import (
	"context"
	"sync"
)

func Merge[T any](ctx context.Context, inputs ...<-chan T) <-chan T {
	out := make(chan T)
	var wg sync.WaitGroup
	for _, in := range inputs {
		wg.Go(func() {
			for v := range in {
				select {
				case out <- v:
				case <-ctx.Done():
					return
				}
			}
		})
	}
	go func() {
		wg.Wait()
		close(out)
	}()
	return out
}
```

## synctest

`testing/synctest` (1.25+) runs a test in a bubble with a fake clock. Time advances only when every goroutine in the bubble is blocked, `synctest.Wait` returns when they all are, and the test fails if the bubble deadlocks or a goroutine outlives it.

```go
package fanout

import (
	"context"
	"errors"
	"testing"
	"testing/synctest"
	"time"
)

func TestPoolStopsOnCancel(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ctx, cancel := context.WithCancel(t.Context())
		jobs := make(chan int)
		results := Pool(ctx, 3, jobs, func(_ context.Context, n int) int { return n * 2 })

		jobs <- 21
		if got := <-results; got != 42 {
			t.Fatalf("first result = %d, want 42", got)
		}

		cancel()
		synctest.Wait()
		if _, open := <-results; open {
			t.Fatal("results still open after cancel; a worker did not exit")
		}
	})
}

func TestTimeoutFiresWithoutWaiting(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
		defer cancel()

		start := time.Now()
		<-ctx.Done()

		if !errors.Is(ctx.Err(), context.DeadlineExceeded) {
			t.Fatalf("ctx.Err() = %v, want DeadlineExceeded", ctx.Err())
		}
		if got := time.Since(start); got != 5*time.Second {
			t.Fatalf("fake elapsed = %v, want 5s", got)
		}
	})
}
```

The second test finishes in microseconds of real time: the five seconds are fake.
