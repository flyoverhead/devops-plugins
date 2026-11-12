# property-based-testing

Tests that state a rule instead of a point. The skill writes property tests for code that has a
rule worth stating, reviews existing property suites for tests that prove nothing, and
classifies a shrunk counterexample as a code bug, a wrong property, an ambiguous spec or a
strategy artifact.

```text
/plugin install property-based-testing@devops
```

## Usage

```text
/property-based-testing:property-based-testing internal/codec          # write
/property-based-testing:property-based-testing tests/test_codec.py     # review
/property-based-testing:property-based-testing <paste failure output>  # triage
```

Or in plain words: "cover the whole input space of this parser", "add property tests for the
normalizer", "do these Hypothesis tests assert anything", "is this shrunk failure a real bug".

## Libraries

| Language | Used |
|---|---|
| Go | native fuzz test (`testing.F`); `pgregory.net/rapid` only when `go.mod` already requires it |
| Python | Hypothesis |
| TypeScript, JavaScript | fast-check |

The repo's existing library always wins and a second one is never added. With none present, the
skill offers a library once, naming the property it would write, and accepts either answer. It
does not edit `go.mod`, `go.sum`, `requirements*.txt`, `pyproject.toml` or `package.json`, and does
not run `go get`, `pip install` or `npm install`, without a yes. Go works with no new module
through native fuzzing.

## Behaviour

- It looks for the strongest property the code supports (roundtrip, oracle, idempotence,
  invariant, law) and says so when there is none; example tests are then the right answer.
- When the shape is buried it offers a rearrangement, such as extracting a pure core or adding the
  missing inverse. Those are suggestions only.
- It runs what it writes; for Go that includes a time-boxed fuzz run.
- `go test` runs without a prompt; `python3 -m pytest` asks first, because conftest.py and
  pytest plugins run arbitrary code.
- A failing property is reported as a finding with the shrunk input and the quoted guarantee. The
  code under test is not changed unless asked.
- Review reports every issue with a severity (CRITICAL to LOW); nothing is filtered out.

Not covered: mutation campaigns, surviving mutants and kill rate (`mutation-testing:mutation-testing`),
plain Go unit tests (`golang:test`), line coverage, benchmarks, and end-to-end tests.

## Tests

```bash
python3 -m pytest property-based-testing/tests -q
```
