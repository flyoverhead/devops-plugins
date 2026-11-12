# Library idioms

## Contents

- Go native fuzz
- Go rapid
- Python Hypothesis
- TypeScript fast-check

## Go native fuzz

Needs Go 1.18+ and no new module. The fuzz function doubles as a property test.

```go
func FuzzAmountRoundtrip(f *testing.F) {
	for _, seed := range []int64{0, 1, -1, 99, -99, math.MinInt64, math.MaxInt64} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, c int64) {
		got, err := Parse(Format(c))
		if err != nil || got != c {
			t.Fatalf("roundtrip of %d: got %d, err %v", c, got, err)
		}
	})
}
```

- Seed edges with `f.Add`. The corpus keeps them, and plain `go test` replays seeds plus the
  saved `testdata/fuzz/<FuzzName>/` files, so a found counterexample becomes a regression test.
- Only built-in types are accepted as fuzz arguments (`int64`, `string`, `[]byte`, ...). Build
  structured values inside the function from those.
- Time-boxed run: `go test -run '^$' -fuzz '^FuzzAmountRoundtrip$' -fuzztime 20s ./pkg/`.
  Run it on a single fuzz target and one package at a time.
- Error path for a decoder: `f.Fuzz(func(t *testing.T, s string) { _, err := Parse(s); if err != nil && !errors.Is(err, ErrAmount) { t.Fatalf(...) } })`.
- A found input is written under `testdata/fuzz/`; mention it in the report and keep it.

## Go rapid

Only when `go.mod` already requires `pgregory.net/rapid`.

```go
func TestAmountRoundtrip(t *testing.T) {
	rapid.Check(t, func(t *rapid.T) {
		c := rapid.Int64().Draw(t, "cents")
		got, err := Parse(Format(c))
		if err != nil || got != c {
			t.Fatalf("roundtrip of %d: got %d, err %v", c, got, err)
		}
	})
}
```

Compose structured values with `rapid.Custom`; `-rapid.checks=N` sets the example count.

## Python Hypothesis

```python
from hypothesis import given, settings, strategies as st, example

@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=-(2**63), max_value=2**63 - 1))
@example(0)
@example(-1)
def test_roundtrip(cents):
    assert parse(fmt(cents)) == cents
```

- Bound values in the strategy. `assume` is for relations between drawn values only.
- Dependent values: `st.builds`, `@st.composite`, or `.flatmap`.
- Profiles: register `local` (10 examples), `ci` (200) and `nightly` (1000, `deadline=None`) and
  select one with `--hypothesis-profile`.
- Decoder error path: `@given(st.binary())`, call the decoder, and catch only its documented error.

## TypeScript fast-check

```ts
import fc from "fast-check";

test("roundtrip", () => {
  fc.assert(
    fc.property(fc.integer(), (n) => {
      expect(parse(format(n))).toBe(n);
    }),
    { numRuns: 200, examples: [[0], [-1]] },
  );
});
```

- Bound values with the arbitrary's options, not `fc.pre`.
- Dependent values: `fc.record`, `.chain`, `.map`.
- `numRuns` about 10 locally, 200 in CI, 1000 nightly. A failure prints a seed and a path; keep
  them in the report so the run can be replayed.
