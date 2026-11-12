# Survivor analysis

## Contents

- [Steps](#steps)
- [Equivalent or not](#equivalent-or-not)
- [Patterns](#patterns)
- [Impact tiers](#impact-tiers)
- [Finding the test that should have caught it](#finding-the-test-that-should-have-caught-it)
- [Numbers](#numbers)
- [Excuses to refuse](#excuses-to-refuse)

The analysis works on any tool's output and any language. It reads code and tests; it changes
nothing in the repository except writing the report.

## Steps

1. **Parse.** Identify the format (`input-formats.md`). If the structure is
   unclear, read the first 50 lines before guessing. Confirm each record carries a path, a line and
   a status; if one is missing, say what cannot be done. Keep the survivors, each with file, line,
   original text, mutated text and operator. Keep the totals for the statistics.
2. **Context.** Group survivors by file and read every mutation site with enough surroundings to
   know what the code is for: types, callers, whether the line can be reached, and whether it is
   security, money, business logic or observability.
3. **Equivalence.** Run the five checks below on each survivor. Verdict: equivalent, real gap or
   unresolved.
4. **Tier.** Give every real gap a tier by what the code does.
5. **Test gap.** For every real gap, find the responsible tests and say why they missed it and what
   would catch it.
6. **Report.** Write it with `report-layout.md`.

Work tier by tier, top tier first, so the important verdicts exist even if the session ends early.
On a long run, save interim notes in `$TMPDIR/mutation-testing-<repo>-N/` after each file. Write formally: third person,
active voice, present tense, inline code for paths and identifiers. Recommended tests are described
in prose, never as code.

## Equivalent or not

A survivor is equivalent only when all five checks hold:

1. **Types.** Does the operand's type make the two versions agree (unsigned, non-null, bounded
   enum)?
2. **Reachability.** Can the line run at all, and with which values?
3. **Downstream use.** Does anything read what the mutated code produces?
4. **Semantics.** Over the whole input domain the code allows, are the two versions the same
   function, side effects included?
5. **Distinguishing input.** Try to build one concrete input that makes them differ. Write the
   attempt down.

Any distinguishing input → **real gap**; that input is the recommended test. Unable to settle a check
→ **unresolved**, with the evidence that would settle it. Never default an unresolved case to either
side.

Keep two things apart: *no test covers it* is a gap; *no input reaches it* is equivalence. The
second needs proof from types or control flow; "no test hits that line" is not proof.

## Patterns

Equivalent, provided the stated condition holds:

| Original → mutant | Condition |
|---|---|
| `n > 0` → `n != 0` | `n` is unsigned; for a signed type it is a real gap (negative input) |
| `!!x` → `x` | `x` is already a boolean |
| `n >= 0` → `true` | `n` is unsigned and evaluating it has no side effect |
| anything in unreachable code | unreachability is proven, not assumed |
| `v = expr` removed | `v` is never read afterwards and `expr` has no side effect |
| `a + b` → `b + a`, `a * b` → `b * a` | built-in, side-effect-free, same type; overloaded operators and floats (NaN) need their own check |

Look equivalent, are not:

| Original → mutant | Why it is real |
|---|---|
| `>` ↔ `>=`, `<` ↔ `<=` | differs at the boundary value; equivalent only if the boundary is provably unreachable. Example: `n > 0` → `n >= 0` on unsigned `n` is always true, so `n == 0` tells them apart |
| `i < len` → `i <= len` in a loop | one extra iteration, often out of bounds |
| a log, event or metric call removed | something downstream may need it: Tier 4, Tier 3 when a consumer depends on it; never equivalent |
| `a - b` → `b - a`, `a / b` → `b / a` | operand order matters |
| C or C++ mutants that create undefined behaviour | real whatever the tests say |

## Impact tiers

The tier is set by what the mutated line does, never by the slug, and ranks where tests are needed
most. It is not a claim that the program is exploitable. When the impact is unclear, say so instead
of raising the tier.

| Tier | Code it covers | Ids |
|---|---|---|
| 1 Critical | access control and authorization, authentication, signature and credential checks, locks and reentrancy guards, input validation at a trust boundary, crypto, privilege changes | C-1, C-2 … |
| 2 High | moving value, fee, rate, share and interest maths, balances and ledgers, state-machine ordering, price feeds, slippage and deadlines, collateral and liquidation limits | H-1 … |
| 3 Medium | non-security config validation, data-structure operations, workflow and protocol steps, callbacks and return values from integrations, error handling off the security path, caches, retry and capacity limits | M-1 … |
| 4 Low | logging, tracing, metrics, events, display-only getters, the text (not the condition) of error messages, constants that only feed docs | L-1 … |

Tie-breakers:

- a config value that sets a security threshold → Tier 1;
- error handling around a call that moves value → Tier 2; around any other call → Tier 3;
- a getter whose result feeds state-changing logic → Tier 2;
- a log or event that a downstream consumer requires → consider Tier 3;
- Tier 2 or 3? Ask whether a wrong result loses money or corrupts accounting. Yes → Tier 2.

## Finding the test that should have caught it

Look in the usual places first:

| Source | Tests |
|---|---|
| `src/x.rs` | `tests/x.rs`, `tests/*.rs` importing the crate, or `mod tests` in the same file |
| `x.py` | `test_x.py`, `tests/test_x.py` |
| `x.go` | `x_test.go` in the same directory |
| `x.ts` | `x.test.ts`, `x.spec.ts`, `__tests__/` |
| `X.sol` | `X.t.sol` |

Otherwise grep for imports of the module or calls of the function. Then read the tests that touch
the code and name why the mutant lived:

- the code runs but nothing asserts on its result or side effect;
- the branch is never entered;
- the edge value (zero, empty, equal to the limit, negative) is never used;
- the inputs are too uniform to tell the versions apart;
- the function is called only as a setup step for something else.

State the fix concretely: which input, which call, which assertion. When no test touches the code at
all, say so plainly; that is a stronger finding than a weak assertion.

## Numbers

- Compute every figure from the parsed data, never from memory or the tool's summary alone; if the
  two disagree, report both and the difference.
- Give each rate with its denominator: raw kill rate = caught / tested.
- Count skipped, timed out and unresolved separately; they are in no numerator.
- Adjusted kill rate = caught / (tested − equivalent). Give it only when the equivalent count is
  settled.
- Worked example: 40 mutants, 32 tested, 24 caught, 8 survived, 8 skipped, 2 equivalent → raw
  24/32 = 75.0 %, adjusted 24/30 = 80.0 %.
- A kill rate says nothing about the quality of the whole suite; do not write that it does.
- Findings are weaknesses in the tests, not confirmed vulnerabilities.

## Excuses to refuse

| Tempting thought | Answer |
|---|---|
| "The kill rate is high, so the suite is fine." | A rate hides which mutants lived. One Tier 1 survivor outweighs it. |
| "It is probably equivalent." | Probably is unresolved. Run the five checks or say what is missing. |
| "Boundary flips are always equivalent." | They differ at the boundary unless it is provably unreachable. |
| "Other tests would catch this in practice." | The campaign ran those tests; they did not. |
| "Only Tier 1 matters, skip the rest." | Every survivor gets a verdict; tiers order the work, they do not filter it. |
| "The operator tells me enough." | Read the source at the line before any verdict. |
