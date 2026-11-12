# Campaign setup

## Contents

- [The order of work](#the-order-of-work)
- [mewt command card](#mewt-command-card)
- [Config file](#config-file)
- [Sizing](#sizing)
- [Making it faster](#making-it-faster)
- [Test command and timeout](#test-command-and-timeout)
- [Ready check](#ready-check)
- [When things go wrong](#when-things-go-wrong)
- [Other tools](#other-tools)

Every command below that writes (`init`, `mutate`, `run`, `test`, `purge`) goes through the campaign
plan gate in SKILL.md: plan shown, explicit yes, one command per yes.

## The order of work

1. **Targets.** Create the config (`mewt init`, gated), then read it back with `mewt print config`.
   The include globs must hit production source only (`src/`, `lib/`, `pkg/`, `internal/`,
   `contracts/`). The ignore list matches by substring: `"test"` drops `tests/` and also
   `test_utils.rs` and `latest.go`. Fix `[targets]` until `mewt print targets` lists exactly the
   source you mean.
2. **Generate and count.** `mewt mutate src/` (gated) creates mutants without running anything.
   `mewt status` and `mewt print targets` give the count per file.
3. **Time the suite** once, by hand, from the project directory (gated like any command).
4. **Estimate** (see [Sizing](#sizing)) and pick a path by the estimate.
5. **Validate the test command and timeout** ([Test command and timeout](#test-command-and-timeout)).
6. **Ready check**, then the run plan for `mewt run`.

Configure through the toml, not command-line flags, so the next run repeats this one; suggest
committing it with a comment on each non-obvious choice. Measure before optimising, and prefer
fewer files over fewer mutation types.

## mewt command card

| Need | Command |
|---|---|
| create a config | `mewt init` |
| create mutants only | `mewt mutate [paths]` |
| run the campaign | `mewt run [paths]` |
| progress and per-target counts | `mewt status` |
| survivors (the default view) | `mewt results` |
| every outcome | `mewt results --all` |
| machine-readable | `mewt results --format json` (also `sarif`, `ids`, `table`) |
| one mutant in full | `mewt print mutant --id N` |
| re-test some mutants | `mewt test --ids 4,9,12` or `mewt test --ids-file FILE` (`-` reads stdin) |
| effective config / target list | `mewt print config`, `mewt print targets` |
| operators for a language | `mewt print mutations --language rust` |
| use another config | `--config path/to/mewt.toml` (its directory becomes the working directory) |

Filters accepted by `results` and `print mutants`: `--target 'src/auth/**'` (quote the glob),
`--severity high,medium`, `--mutation-types ER,CR`, `--status Uncaught` (or `TestFail`, `Skipped`,
`Timeout`), `--line 42`. Language labels are a family or `family/dialect`: `rust`, `javascript/ts`,
`move/sui`, `move/iota`.

## Config file

```toml
db = "mewt.sqlite"

[log]
level = "info"

[targets]
include = ["src/**/*.rs"]          # globs, source only
ignore = ["mock", "generated"]     # substrings, see the warning above

[run]
mutations = ["ER", "CR", "IF", "IT", "NR"]   # optional: restrict slugs

[test]
cmd = "cargo test"
timeout = 120                       # seconds; omit to let mewt pick

[[per_target]]                      # optional, first match wins
glob = "src/parser/**"
test.cmd = "cargo test parser::"
test.timeout = 30
```

## Sizing

Worst case = mutants × seconds per suite run. 500 mutants × 10 s is about 1 h 23 min. Real runs
finish sooner because a failing test stops early, so present the worst case as the ceiling.

| Estimate | What to do |
|---|---|
| under 1 h | go ahead (after the plan gate) |
| 1 h to 16 h | ask: run as is (end of day, overnight), or optimise first |
| over 16 h | optimise before proposing a run |

Scheduling hints: under an hour fits any time; 1 to 16 h is an end-of-day start; 16 to 48 h is a
Friday-evening start; longer is two phases on two days.

## Making it faster

Diagnose in this order:

1. **Target selection** is the usual culprit. Look for tests, mocks, fixtures, `vendor/`,
   `node_modules/`, generated code and protobuf output inside the targets.
2. **Shape of the work.** Count per component and per severity:
   `mewt print mutants --target 'src/auth/**' --format ids` and count the lines it prints.
3. **Pick an option**, present each with its estimate, and recommend one.

| Option | How | Estimate to give |
|---|---|---|
| Full run | no change | the worst case; suggest a weekend start |
| Critical first | narrow `include` to the sensitive components (auth, crypto, parsing), widen later | per-component counts × suite time |
| Higher severities only | `[run].mutations` limited to high and medium slugs; low slugs are roughly 60-70 % of mutants, so this keeps about 30-40 % | the reduced count × suite time. Alternative with no database change: run everything, filter later with `--severity` |
| Two phases | only for suites dominated by slow integration tests; see below | phase 1 firm; phase 2 = survivors × full suite time, known only after phase 1 |

**Two phases.** Phase 1 uses fast per-component commands in `[[per_target]]` blocks (`glob`,
`test.cmd`, `test.timeout`; first match wins, so put the catch-all last, and keep a full-suite
fallback unless the globs cover every target exactly). Phase 2 re-tests only the survivors with the
full suite: save `mewt results --status Uncaught --format ids` to a file (a gated write), comment out
the `[[per_target]]` blocks, keep the global `[test]`, then `mewt test --ids-file <file>`.
Per-target commands pay off only when a targeted run is clearly faster; time both first. Their risk
is missing a failure in another module, which is what phase 2 is for.

**Updating the database after a config change** (gated; both discard data, so the purge rule in
SKILL.md applies):

| Change | Then |
|---|---|
| narrower targets | `mewt purge`, then `mewt mutate src/` |
| fewer mutation types | `mewt purge --all`, then `mewt mutate src/` |

## Test command and timeout

- Run the command by hand from the project directory first. If it fails, look at the Makefile,
  justfile, `package.json` scripts or README for the real one; a monorepo may need a workspace
  subdirectory.
- Leave `[test].timeout` unset by default: mewt uses about twice the measured baseline.
- Exception: compiled projects where rebuilding dependents dominates (Foundry/Solidity, large Rust
  workspaces). Time a warm run, touch one source file, time again. If the two differ a lot, set
  `timeout` by hand to the slower time × 2, rounded up.

## Ready check

- [ ] `mewt print config` parses and shows the intended targets
- [ ] the mutant count matches what the target list predicts
- [ ] no tests, mocks or third-party code among the targets
- [ ] the test command passes by hand on unmutated code
- [ ] timeout set, or left to auto on purpose
- [ ] the suite touches no shared or production service
- [ ] the user accepted the estimated duration

Then present the plan for `mewt run`.

## When things go wrong

- **No mutants.** Check the language is supported (`mewt print mutations --language <lang>`) and
  the globs. List files with `find src -name '*.rs'`, not a shell `**` glob: macOS bash 3.2 has no
  globstar and silently under-counts. Keep `**` inside the toml, where mewt expands it.
- **Test command fails under mewt but not by hand.** The config directory is the working
  directory; check relative paths and environment variables.
- **Many timeouts.** The timeout is too tight for rebuilds; apply the exception above.

## Other tools

| Tool | Plan items specific to it |
|---|---|
| gremlins | `gremlins unleash ./...` from the module root; `--output results.json` for JSON; it first gathers coverage, and NOT COVERED lines are reported, not mutated |
| mutmut | `mutmut run` mutates files in place while running and keeps a cache; `paths_to_mutate` and the runner live in `setup.cfg` or `pyproject.toml`; read with `mutmut results` |
| Stryker | only when `@stryker-mutator/core` is already a devDependency; `npx stryker run` uses `stryker.config.*`; JSON lands in `reports/mutation/mutation.json` |
