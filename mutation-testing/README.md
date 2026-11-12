# mutation-testing

Makes sense of mutation testing. The skill sizes and scopes a campaign before anything runs, turns
finished results into a report that tells equivalent mutants from real test gaps, and follows the
worst gaps to bugs you can reproduce.

```text
/plugin install mutation-testing@devops
```

## Usage

```text
/mutation-testing:mutation-testing mewt-results.json     # analyse saved results
/mutation-testing:mutation-testing setup                 # plan a campaign
/mutation-testing:mutation-testing hunt                  # look for bugs behind survivors
```

Or in plain words: "two gremlins mutants lived in internal/auth, do they matter", "our mutmut run
takes all night", "what test would kill these survivors", "write up the Stryker results".

## Jobs

| Job | Input | Output |
|---|---|---|
| Setup | code and a test command | tuned `mewt.toml` (or the tool's config), mutant count, time estimate, verified test command and timeout; nothing runs without a yes |
| Analysis | results from any tool (mewt/muton JSON, gremlins, mutmut, Stryker `mutation.json`, cargo-mutants, mull, dextool and others) | `$TMPDIR/mutation-testing-<repo>-N/mutation-testing-report.md`, outside the repository |
| Bug hunt | finished results | findings classed confirmed, likely, dead code or not a bug; only a reproduced finding is confirmed |

Every survivor gets a verdict: **equivalent** (five checks passed and no distinguishing input
found), **real gap** (with the test that would kill it) or **unresolved** (with the evidence that is
missing). Real gaps are tiered by what the code does: Tier 1 access control and validation, Tier 2
money and state, Tier 3 workflow and capacity, Tier 4 logging and display.

## Tools

| Stack | Tool |
|---|---|
| Go | gremlins, or mewt |
| Python | mutmut |
| TypeScript | Stryker, if `@stryker-mutator/core` is already a devDependency |
| Rust and others | mewt or muton |

All optional. The skill never installs a tool: it names the tool and the install command once and
waits. Saved results need no tool.

## Safety

- Pre-approved shell is read-only: `command -v`, `mewt|muton status|results|print`, `mutmut results`.
- Campaign commands (`init`, `mutate`, `run`, `test`, `purge`, `gremlins unleash`, `mutmut run`,
  `npx stryker run`) always prompt, and the skill first shows the plan and time estimate and waits for
  an explicit yes.
- A campaign reruns the suite many times on this machine; it is never pointed at tests that reach
  shared or production services.
- `purge` discards outcomes and needs its own confirmation.
- Config writes such as `mewt.toml` are gated in prose only: `Write` is pre-approved, so the skill
  treats every config change as a new plan that needs its own yes.
- The analysis writes only the report; it does not touch source, tests or fixtures.

Not covered: line or branch coverage (answered directly), new property tests
(`property-based-testing:property-based-testing`), plain Go review (`golang:review`), and writing the
tests a report recommends.

## Tests

```bash
python3 -m pytest mutation-testing/tests -q --import-mode=importlib
(cd mutation-testing/tests && DETERMINISTIC_ONLY=yes ./smoke-test.sh)
```

`tests/validate_report.py REPORT.md [--expect-fail]` checks a report written on the eval fixture
(exit 0 pass, 1 fail, 2 usage or read error). Without `DETERMINISTIC_ONLY`, `smoke-test.sh` also runs
the `outcome-weak-suite-analysis` eval for real (needs `claude` and `ANTHROPIC_API_KEY`; `RUNS`,
`MODEL`, `JUDGE_MODEL`, `MAX_COST_USD`, `KEEP_ARTIFACTS`, `SMOKE_RUN_ROOT_BASE` (default `/tmp`) tune it) and validates every report it wrote.
