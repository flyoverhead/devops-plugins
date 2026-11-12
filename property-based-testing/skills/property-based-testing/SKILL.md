---
name: property-based-testing
description: Turns code with an algebraic shape (codecs, parsers, normalizers, validators, collections, numeric functions) into property tests in Go (native fuzz or rapid), Python (Hypothesis) or TypeScript (fast-check), audits property suites for tests that prove nothing, and sorts a shrunk counterexample into bug, wrong property, ambiguous spec or strategy artifact. Use when asked to cover a whole input space, add or audit property tests or classify a shrunk failure. Not for mutation campaigns or kill rate — use mutation-testing:mutation-testing; not for plain Go unit tests — use golang:test.
argument-hint: "[function | package | test file | failure output]"
effort: low
allowed-tools: Read Grep Glob Write Edit Bash(go test:*) Bash(go vet:*) Bash(rg:*) Bash(git ls-files:*) Bash(git rev-parse:*)
---

Target: $ARGUMENTS

# Property-based testing

An example test checks one point. A property test states a rule and lets the library hunt for
an input that breaks it, then shrinks that input to the smallest one that still breaks it. That
pays off only when the code has a rule worth stating. This skill does three jobs: **write**
property tests, **review** a suite that already exists, **triage** a shrunk failure. Pick the
job from the request; a path to a test file means review, pasted failure output means triage.

## Right skill?

| Request | Where it belongs |
|---|---|
| benchmarks, allocation counts | not a property test; answer directly |
| end-to-end or integration tests | not this skill |
| mutation campaign, surviving mutants, kill rate | `mutation-testing:mutation-testing` |
| line coverage | not a property test; answer directly |
| plain Go unit or table tests | `golang:test` |

## Ground rules

- **The repo's library wins.** Detect it first (below) and write in it. Never bring in a second one.
- **No new dependency without an answer.** If none is present, see [Dependency gate](#dependency-gate).
- **Production code stays as it is.** A failing property is a finding. Report it; do not patch
  the code under test to make the test green, and do not weaken the test to hide it.
- **Report every classification**, the unsure ones included. A finding left out of the report
  cannot be triaged by anyone else.
- Run what you write. A property file that was never executed is not a deliverable.

## Libraries

| Language | Default | Notes |
|---|---|---|
| Go | native fuzz test (`testing.F`) | `pgregory.net/rapid` when `go.mod` already requires it |
| Python | Hypothesis | |
| TypeScript, JavaScript | fast-check | |

Python or TypeScript without Hypothesis or fast-check: run the dependency gate; without a yes, write
a seeded loop over pinned edge values and random draws from the standard library, and say it
shrinks nothing. Other languages and libraries: use whichever the repo already imports, and say that the
detail below was written for the three above. [references/libraries.md](references/libraries.md)
has the idioms, settings and a skeleton for each.

**Detect before writing.** Search imports and manifests: `rg -n 'hypothesis|fast-check|pgregory.net/rapid|func Fuzz'`
over source plus the manifests (`go.mod`, `requirements*.txt`, `pyproject.toml`, `package.json`).
Read the manifest, then decide.

## Job 1: write

1. **Find the shape.** Read the target and name the strongest rule it supports, from the
   ladder in [references/properties.md](references/properties.md): roundtrip or inverse, oracle,
   idempotence, invariant, easy-to-check postcondition, algebraic law, and last, "does not crash".
2. **No shape?** Check whether one is buried: arithmetic tangled with I/O, a string assembled by
   concatenation, in-place mutation, a hidden global. If so, offer the matching rearrangement
   from [references/refactors.md](references/refactors.md) and let the author decide. If nothing
   is buried, say it is a poor candidate, recommend example tests, and stop. That is a valid result.
   "Does not crash" alone rarely justifies a dependency; look for something stronger first.
3. **Pick the library** (detect, then the table above). With none present and a third-party one
   wanted, run the dependency gate.
4. **Write it.**
   - Put constraints in the generator. Reserve `assume`/`t.Skip` for a relation between values
     that were already drawn; filtering after generation burns the budget and ends in a health
     check failure.
   - Pin the known edges as explicit examples: empty, one element, all duplicates, zero,
     negatives, the extremes of the type.
   - Dependent fields come from a composite generator (build the list, then draw the index),
     not from a filter.
   - Set effort deliberately: about 10 examples locally, about 200 in CI, about 1000 nightly.
     Switch the per-example deadline off for real suites; slow-machine timeouts get tests deleted.
   - A determinism property (`f(x) == f(x)`) counts only where the output could really vary:
     map or set serialization, hashing, iteration order, the clock.
   - A decoder gets an error-path property: arbitrary bytes in, and the only outcomes are
     success or the documented error. Catch that error type only, never a blanket catch.
5. **Run it to completion.** Go: plain `go test`, then a time-boxed fuzz run, with the exact
   invocation in [references/libraries.md](references/libraries.md#go-native-fuzz). Python and
   TypeScript: the project's own runner.
6. **A failure is a result.** Go to Job 3 with it before touching anything.
7. **Report** the property chosen and why that one and not a weaker one, what ran and how long,
   what was found, and any refactor you would suggest.

## Job 2: review

1. Locate property tests: `@given(`, `from hypothesis import`, `fc.assert`, `fc.property`,
   `func Fuzz`, `rapid.Check`.
2. Grade each test against the severity table in
   [references/review-and-triage.md](references/review-and-triage.md#review-severities), and flag
   flake sources: float equality without tolerance, assertions on map or set order, clock reads.
3. Name the strongest property the code supports and the suite lacks (a typical gap: the length
   is checked and the order never is).
4. List every issue with its severity. Do not drop a MEDIUM or LOW item on the author's behalf.

## Job 3: triage

Ground the property before believing the failure. Authority, strongest first: an external spec
or RFC, type annotations, the docstring or doc comment, existing tests, the function name.
Then classify with the table in [references/review-and-triage.md](references/review-and-triage.md#triage-table):

- code bug: a documented guarantee is violated; report the shrunk input and quote the guarantee;
- wrong property: the assertion disagrees with the docs or types; fix the assertion;
- strategy artifact: the input is outside a stated precondition or unrealistic; narrow the generator;
- ambiguous: the spec is silent on this input; ask the maintainer, and do not file it as a bug.

Precondition violations and documented undefined behaviour are never bugs.

## Dependency gate

Applies when the repo has no property library and the strongest approach needs one.

1. Offer it once, naming the specific property you would write with it. Example: "a rapid
   generator would let the roundtrip run over structured values; native fuzz can only mutate raw
   bytes".
2. Accept yes or no. Under no, or no answer, work with what is there: for Go that is a native fuzz
   test, which needs no new module.
3. Without a yes, never edit `go.mod`, `go.sum`, `requirements*.txt`, `pyproject.toml` or
   `package.json`, and never run `go get`, `go mod tidy`, `pip install` or `npm install`.

## Limits

- `go test` and `go vet` are pre-approved. Never pass `-exec`, `-toolexec`, `-overlay`, `-o`,
  `-c`, `-vettool`, `-mod=mod`, `-modfile`, `-coverprofile`, `-cpuprofile`, `-memprofile`,
  `-blockprofile`, `-mutexprofile`, `-trace`, `-outputdir` or `-fuzzcachedir`; they run other
  programs, rewrite go.mod or write files outside the test files.
- Python tests run through `python3 -m pytest`, with no `-p` and no `--basetemp`. It is not
  pre-approved (conftest.py and plugins run arbitrary code), so each run asks first; so do other
  runners (`pytest`, `npm test`).
- `rg` is pre-approved: never pass `--pre`, which runs a command on every file.
- `git grep` is not pre-approved and asks first; never pass `-O` or `--open-files-in-pager`.
- No installs, no network, no commits, no edits outside test files (and the manifests only after a yes).
- Tests are written beside the code in the repo's own test location and naming. In Go a new
  file such as `<unit>_prop_test.go`; keep it a `_test.go` file so plain `go test` replays seeds
  and the saved `testdata/fuzz/` corpus.
