# Review and triage

## Contents

- Review severities
- Flake sources
- Triage table
- Grounding
- Recurring patterns

## Review severities

| Severity | Finding | Test for it |
|---|---|---|
| CRITICAL | tautological: true whatever the implementation does | could any broken implementation falsify it? |
| CRITICAL | vacuous: the filter rejects nearly everything, contradicts itself, or pins one value (`assume(x == 42)` is an example in disguise) | count how many generated inputs reach the assertion |
| HIGH | no assertion: calls the function and stops | |
| HIGH | reimplementation: the assertion recomputes the function | swap in an algebraic law |
| MEDIUM | a weaker property than the code supports | compare with the property ladder reference |
| MEDIUM | over-filtered: stacked `assume` calls where a generator bound belongs | |
| LOW | settings: very few examples (`max_examples=5`), or a deadline left on an expensive generator | |

Exception to the tautology rule: `x == x` on a function that may be nondeterministic (pickling an
object with an odd reduce, serializing a map) is a real determinism property.

Report all of them with their severity. The author decides what to ignore.

## Flake sources

Float equality without a tolerance, assertions about map or set order, and reads of the clock.
Note each as an issue even when the suite passes today.

## Triage table

| Observation | Classification | Action |
|---|---|---|
| a documented guarantee is violated | code bug | report with the shrunk input and the quoted text |
| the generated input is outside a stated precondition | strategy artifact | narrow the generator |
| the assertion disagrees with the docs or the types | wrong property | correct the assertion |
| the spec is silent on this input | ambiguous | ask the maintainer; not a bug report |
| the failure disappears with realistic inputs | strategy artifact | repair the generator |
| differs from a sibling function's behaviour | possible inconsistency | raise it, with the uncertainty stated |

Precondition violations and documented undefined behaviour are never bugs.

## Grounding

Read the contract before the failure. Authority, strongest first: an external spec or RFC, type
annotations, the docstring or doc comment, existing tests, the function name.

Contrast: a text codec fails on `"\x00"`. If the docs say any Unicode string is accepted, it is a
code bug. If they say printable ASCII, the alphabet in the generator is wrong.

## Recurring patterns

- Lone surrogates break text roundtrips. Real only if the format claims to carry any string, not
  just valid UTF-8.
- Denormals such as `1e-320` break numeric range invariants. Real against a documented `[0, 1]`.
- `a == b` with unequal hashes violates a language-level contract: report it with no further grounding.
- An iterator that drops its last element is almost always real.
- Sign lost on values close to zero (an integer division that truncates toward zero and a
  remainder formatted separately) is real wherever the format claims to carry negatives.
