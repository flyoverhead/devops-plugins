# JavaScript and TypeScript

Every entry: **Bites**, **Spot**, **Fix**.

## Contents

- Comparison and conversion: loose equality, operators, parseInt, JSON numbers
- Objects: prototype pollution, property checks, this binding, mutating methods
- Execution: dynamic code, ReDoS, async ordering
- TypeScript escape hatches
- Grep set

## Comparison and conversion

### Loose equality

- **Bites:** `""`, `0`, `[]` and `false` compare equal with `==`, so `if (user.role == 0)` or
  `if (token == expected)` accepts the wrong value.
- **Spot:** `==` and `!=` in role, flag and token checks.
- **Fix:** `===` and `!==` everywhere; a lint rule to keep it that way.

### Operators that coerce

- **Bites:** `limit + 1` with `limit = "10"` gives `"101"`; `"9" > "10"` is true.
- **Spot:** arithmetic or comparisons on values straight from a request or env.
- **Fix:** convert and validate at the boundary (`Number`, a schema), then compute.

### `parseInt` surprises

- **Bites:** `parseInt("12abc")` is `12`; without a radix, prefixes change the base in older
  engines.
- **Spot:** `parseInt(` with one argument on input.
- **Fix:** `parseInt(x, 10)` plus `Number.isInteger`, or `Number(x)` with a check.

### Big integers in JSON

- **Bites:** IDs above 2^53 lose precision and point at a different object.
- **Spot:** numeric IDs from other systems parsed with `JSON.parse`.
- **Fix:** send IDs as strings; `BigInt` where arithmetic is needed.

## Objects

### Prototype pollution

- **Bites:** a recursive merge or set-by-path helper fed `{"__proto__": {"isAdmin": true}}`
  gives every object an `isAdmin` property. `JSON.parse` alone is harmless; the merge is not.
- **Spot:** deep-merge, extend, `set(obj, path, value)` helpers on parsed input.
- **Fix:** skip `__proto__`, `constructor`, `prototype` keys; `Object.create(null)` or `Map`.

### Property checks that see inherited members

- **Bites:** `"toString" in perms` is true; `perms[req.query.action]` reads inherited methods.
- **Spot:** `in` or bracket access with caller-chosen keys.
- **Fix:** `Object.hasOwn(obj, key)`, or a `Map`/`Set` allowlist.

### `this` lost in callbacks

- **Bites:** `button.on("click", auth.check)` runs `check` with the wrong `this` and reads
  `undefined` settings.
- **Spot:** methods passed as callbacks.
- **Fix:** arrow functions or `.bind(obj)`.

### Methods that mutate

- **Bites:** `sort`, `reverse`, `splice`, `fill` change the shared array in place; default
  `sort` compares as strings so `[10, 9, 1]` sorts to `[1, 10, 9]`.
- **Spot:** these calls on arrays the caller still uses; numeric sorts without a comparator.
- **Fix:** `toSorted`/`toReversed` or a copy first; always pass a comparator for numbers.

## Execution

### Strings that run as code

- **Bites:** `eval`, `new Function`, `setTimeout("...")` / `setInterval("...")` execute input.
- **Spot:** any of them reachable from request data.
- **Fix:** pass functions, not strings; parse data with `JSON.parse`.

### Catastrophic regex backtracking

- **Bites:** `/^(a+)+$/` or overlapping alternations take exponential time on crafted input and
  block the event loop for every user.
- **Spot:** nested quantifiers or ambiguous alternations applied to untrusted strings.
- **Fix:** rewrite the pattern, cap input length, or use a linear-time engine.

### Missing await

- **Bites:** `validate(req)` without `await` lets the handler continue before validation
  rejects; an unhandled rejection can crash the process.
- **Spot:** async calls in auth or validation paths whose promise is not awaited.
- **Fix:** `await` them; enable `no-floating-promises`. Serial awaits are a speed issue only.

## TypeScript escape hatches

- **Bites:** `as`, `any`, the non-null `!` and type guards that always return `true` vanish at
  runtime, so a request typed as `Admin` is whatever the client sent.
- **Spot:** these constructs where data crosses a trust boundary.
- **Fix:** validate with a runtime schema at the boundary and derive the type from it.

## Grep set

```bash
grep -rn --include='*.ts' --include='*.js' -E '[^=!]==[^=]' .
grep -rn --include='*.ts' --include='*.js' -E 'eval\(|Function\(' .
grep -rn --include='*.ts' -E ' as [A-Z]|!\.' .
grep -rn --include='*.ts' --include='*.js' -E 'parseInt\([^,)]*\)' .
grep -rn --include='*.ts' --include='*.js' -E '\[(req|request|params|query|body)\.' .
```
