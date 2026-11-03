#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module github.com/example/demo\n\ngo 1.25\n' > go.mod
cat > counter.go <<'GO'
package demo

type Counter struct {
	m map[string]int
}

func NewCounter() *Counter { return &Counter{m: map[string]int{}} }

func (c *Counter) Inc(key string) { c.m[key]++ }

func (c *Counter) Get(key string) int { return c.m[key] }
GO
cat > counter_test.go <<'GO'
package demo

import (
	"sync"
	"testing"
)

func TestCounterConcurrent(t *testing.T) {
	c := NewCounter()
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				c.Inc("k")
			}
		}()
	}
	wg.Wait()
	if got := c.Get("k"); got != 1000 {
		t.Fatalf("got %d, want 1000", got)
	}
}
GO
