# Property ladder

Weakest at the bottom of the list of "what you check", strongest at the top. Choose the highest
rung the code supports.

| Rung | Form | Typical home |
|---|---|---|
| Roundtrip / inverse | `decode(encode(x)) == x`, `f(g(x)) == x` | codecs, marshal pairs, parsers with a printer |
| Oracle | `fast(x) == reference(x)` | optimized rewrite, hand-rolled version of a library call |
| Idempotence | `f(f(x)) == f(x)` | normalizers, sanitizers, canonicalizers |
| Invariant | a quantity holds before and after | collections (size, order, uniqueness), balances, ranges |
| Easy-to-check postcondition | `is_sorted(sort(x))`, output has no forbidden character | sorting, validators, escapers |
| Algebraic law | commutativity, associativity, identity element | merge, union, numeric combine |
| Type preservation | result stays in the declared domain | any pure function |
| Does not crash | no exception, no hang | last resort |

## Choosing

- Take the strongest rung that does not restate the implementation. An assertion that recomputes
  the function (`add(a, b) == a + b`) is a copy of the code; swap it for a law
  (`add(a, 0) == a`, `add(a, b) == add(b, a)`).
- Idempotence and roundtrip catch different faults. Normalizers want idempotence; a normalizer
  with a matching denormalizer wants both.
- A pair of operations gives an inverse for free: insert then remove leaves the collection as it
  was; push then pop returns the element.
- A custom collection with add, remove and get: state a model (a plain map or slice) and check
  the collection against it after a random operation sequence.
- Comparators: antisymmetry, transitivity, and agreement with the sort that uses them.
- Validators: generate from the grammar of valid values and expect true; mutate one valid value
  and expect false.
- Where the only rung available is "does not crash", look for a small rearrangement first
  (see the refactors reference); if none exists, report a poor fit instead of adding a library.

## Determinism

`f(x) == f(x)` is a property only where `f` could differ between calls: output built from map or
set iteration, hashing with a random seed, timestamps, goroutine scheduling. On a pure function
it is a tautology and gets flagged in review.
