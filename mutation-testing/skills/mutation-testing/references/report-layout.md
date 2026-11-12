# Report layout

The analysis job writes `$TMPDIR/mutation-testing-<repo>-N/mutation-testing-report.md`, outside the repository. Length follows the
findings: a tier with no findings may be left out, and the Unresolved section exists only when
something is unresolved. Ids run per tier: `C-n` Tier 1, `H-n` Tier 2, `M-n` Tier 3, `L-n` Tier 4.

````markdown
# Mutation Testing Report: <project>

| | |
|---|---|
| Project | <name> |
| Repository | <path or URL> |
| Date | <YYYY-MM-DD> |
| Tool | <tool and version> |
| Analysed by | <who or what> |

## Executive Summary

| Metric | Value |
|---|---|
| Mutants generated | N |
| Tested | N |
| Killed | N |
| Survived | N |
| Equivalent | N |
| Real gaps | N |
| Unresolved | N |
| Skipped / timed out | N / N |
| Raw kill rate | killed / tested = x % |
| Adjusted kill rate | killed / (tested − equivalent) = y % |

<Two or three sentences: what was analysed, the denominators behind the rates, and that the
findings are weaknesses in the tests, not confirmed vulnerabilities. No verdict on overall suite
quality.>

| Tier | Real gaps | Share |
|---|---|---|
| Tier 1 Critical | n | p % |
| Tier 2 High | n | p % |
| Tier 3 Medium | n | p % |
| Tier 4 Low | n | p % |

## Equivalent Mutants

| # | File | Line | Original → Mutated | Reason |
|---|---|---|---|---|
| 1 | `src/x.rs` | 42 | `n > 0` → `n != 0` | `n` is `u32`; no input distinguishes them |

## Tier 1: Critical

### C-1: <short title>

- **Location:** `src/x.rs`, line 23
- **Mutation:** `cond` → `false` (IF)
- **Context:** <what the code does and why it is in this tier>
- **Tests that touch it:** `tests/x.rs`: `test_name`
- **Why it survived:** <missing assertion / branch never entered / edge value unused>
- **Recommended test:** <prose: input, call, expected result>

## Tier 2: High

## Tier 3: Medium

## Tier 4: Low

## Recommendations

<Grouped by test file, highest tier first: the tests to add or strengthen in that file and the
finding ids each one closes.>

## Unresolved Cases

| Location | Behaviour in doubt | Evidence needed |
|---|---|---|

## Appendix

- **Inputs:** <result files read, source and test files read>
- **Survivors per source file:**

  | File | T1 | T2 | T3 | T4 | Equivalent | Unresolved |
  |---|---|---|---|---|---|---|

- **Method:** survivors are tiered by the impact of the mutated code, not the mutation operator;
  equivalence was decided by type, reachability and downstream-use analysis plus an attempt to
  construct a distinguishing input.
````

Check before saving: every survivor in the input appears exactly once (in a tier, the equivalent
table or the unresolved table), the tier counts add up to the real-gap count, and the rates match
their stated denominators.
