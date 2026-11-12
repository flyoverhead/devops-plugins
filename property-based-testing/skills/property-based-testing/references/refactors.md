# Rearrangements that expose a property

Suggest, never apply unasked. Each one is the author's call; say which property it unlocks.

| Smell | Rearrangement | Unlocks |
|---|---|---|
| calculation interleaved with I/O | extract a pure core, leave the I/O at the edge; the thin wrapper keeps its mocked example tests | invariants, monotonicity, an oracle |
| a request, query or message built and sent in one function | build the value in its own function | properties over the built value |
| an encoder with no decoder | add the inverse, even if only in tests, and say which | roundtrip |
| output assembled by string concatenation | a structured value plus a renderer and a parser | roundtrip; escaping faults surface here |
| result produced by mutating the argument | return a value; a copying wrapper suffices if the signature must stay | before/after comparison, idempotence |
| a global, constant or environment variable inside the logic | inject it as a parameter | generators that reach 0, 1 and the maximum |

## When not to suggest

- The only property it would unlock is "does not crash".
- The module needs wholesale restructuring. Say so once; do not hand over a pile of small suggestions.
- The change breaks a public API. Flag it as breaking and offer a compatible variant, for example
  the old signature wrapping the new one.
- Existing tests already cover the behaviour. After any accepted rearrangement run them and
  report that they still pass.
