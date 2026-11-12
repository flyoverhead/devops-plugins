---
name: mutation-testing
description: Sorts each surviving mutant into equivalent, real test gap or unresolved, tiers the gaps by what the code does in mutation-testing-report.md, follows the worst gaps to reproducible bugs, and sizes a new campaign whose run waits for an explicit yes. Reads mewt, muton, gremlins, mutmut and Stryker output; installs none of them. Use when mutants lived or survived, a kill rate needs explaining, a campaign is too slow, or someone asks which test a survivor calls for. Not for line coverage (answer directly) or new property tests — use property-based-testing:property-based-testing.
argument-hint: "[results file | project dir | 'setup' | 'hunt']"
allowed-tools: Read Write Grep Glob Bash(command -v:*) Bash(mewt status:*) Bash(mewt results:*) Bash(mewt print:*) Bash(muton status:*) Bash(muton results:*) Bash(muton print:*) Bash(mutmut results:*) Bash(printenv TMPDIR)
---

Request: $ARGUMENTS

# Mutation testing

A mutation tool plants small faults in the code and reruns the tests. A fault the tests notice is
caught (killed); one they miss survived (lived, uncaught). A survivor is either a fault no input
can expose (an *equivalent* mutant) or a hole in the tests. This skill decides which, ranks the
holes by what the code does, and follows the worst ones to real bugs.

## Pick the job

| The user has | Job | Load |
|---|---|---|
| code and a test command, no campaign yet; or a campaign that is too slow | **Setup** | [references/campaign-setup.md](references/campaign-setup.md) |
| finished results (any tool, any format) and wants them explained | **Analysis** | [references/survivor-analysis.md](references/survivor-analysis.md), [references/report-layout.md](references/report-layout.md), [references/input-formats.md](references/input-formats.md) |
| finished results and wants bugs, not a test to-do list | **Bug hunt** | [references/bug-hunt.md](references/bug-hunt.md) |

Load only the files for the chosen job. A question about one or two survivors is a small analysis:
answer it in chat with the same rules and skip the report file unless asked.

## Somewhere else

| Request | Goes to |
|---|---|
| line or branch coverage with no mutants in sight | not this skill; answer directly (`go test -cover`, `coverage.py`, `c8`) |
| write new property-based tests | `property-based-testing:property-based-testing` |
| review Go code with no mutation data | `golang:review` |
| implement the tests a report recommends | not this skill; the report recommends, someone else writes them |
| "which mutation tool is best" in the abstract | answer briefly from the table below; no analysis job |

## Tools by stack

| Stack | Tool | Start (gated) | Read results (free) |
|---|---|---|---|
| Go | gremlins | `gremlins unleash ./...` (add `--output results.json` for JSON) | read the text or JSON output |
| Go | mewt | `mewt run`, with `include = ["**/*.go"]` in `mewt.toml` | `mewt results`, `mewt status` |
| Python | mutmut | `mutmut run` | `mutmut results` |
| TypeScript | Stryker | `npx stryker run`, only when `@stryker-mutator/core` is already a devDependency | read `reports/mutation/mutation.json` |
| Rust, others | mewt or muton | `mewt run` | `mewt results --format json` |

mewt and muton take the same subcommands and flags; this skill writes `mewt`, so for muton swap the
binary and the file names (`muton.toml`, `muton.sqlite`). The examples follow the mewt 4.x
interface. Where the installed binary's `--help` disagrees, the binary is right.

Saved results need no tool at all. Never ask for an install to analyse a file that is already here.

## Gates

1. **Look first.** `command -v mewt muton gremlins mutmut` (and the Stryker package in
   `package.json`) shows what is present. Nothing else runs before the plan.
2. **Installing is the user's call.** If a tool is missing, name it and the exact install command
   once (`go install github.com/go-gremlins/gremlins/cmd/gremlins@latest`, `pip install mutmut`,
   `npm install -D @stryker-mutator/core`, or the install line from the mewt or muton README), then
   wait. Never run it.
3. **Campaign plan before any run.** Before `init`, `mutate`, `run`, `test`, `purge`,
   `gremlins unleash`, `mutmut run` or `npx stryker run`, show: the tool, the exact command, the
   targets, the mutant count (or the best estimate), the time estimate from
   [references/campaign-setup.md](references/campaign-setup.md#sizing), and what it writes
   (config, database, mutated source in place). Then stop and wait for an explicit yes. Silence,
   "looks fine" about something else, or a yes to a different plan is not a yes. These commands
   are deliberately not pre-approved, so each one also prompts.
4. **One yes, one command.** A later run, a re-test of survivors or a config change is a new plan.
5. **Shared services.** A campaign reruns the suite hundreds of times on this machine. If the tests
   reach a shared database, a staging API or anything in production, say so and do not propose the
   run until those tests are excluded or stubbed.
6. **Purge discards outcomes.** Before `mewt purge`, list what will be lost, offer to export it
   (`mewt results --all --format json`), and get a yes for the discard itself.

## Reading outcomes

| Status | Means |
|---|---|
| Caught / TestFail / KILLED | a test failed on the mutant: detected |
| Uncaught / LIVED / Survived | every test passed: a gap or an equivalent mutant; read the code to tell |
| Timeout | inconclusive; neither coverage nor a gap |
| Skipped | a weaker mutant on a line where a stronger one already survived; not run |
| NOT COVERED (gremlins), NoCoverage (Stryker) | no test executes the line at all |

mewt mutation slugs and what a survivor says about the tests:

| Slug | Mutation | A survivor means |
|---|---|---|
| ER (high) | an error is returned or raised instead | the tests accept an injected failure |
| CR (medium) | a statement is commented out | nothing checks that statement's effect |
| IF / IT (medium) | a condition forced false / true | the branch outcome is not checked; both surviving on one line usually means the branch never runs or nothing asserts after it |
| NR (medium) | a negation is dropped | the condition's polarity is not checked |
| AOS, COS, LOS, BOS, shift and assignment variants (low) | operator swaps | boundary or arithmetic values are not pinned |
| BL, AS, LC, WF (low) | literal, assignment and loop-control tweaks | values or loop limits are not pinned |

The slug's severity ranks the *mutation*, not the risk. A low-severity `>` → `>=` in an access check
outranks a high-severity ER in a log helper. `mewt print mutations --language <lang>` lists the
operators the installed version really applies.

## Analysis in brief

The full procedure is in [references/survivor-analysis.md](references/survivor-analysis.md). Its
non-negotiables:

- Every survivor gets its own verdict: **equivalent**, **real gap** or **unresolved**. Nothing is
  batched, sampled or summarised away.
- **Equivalent** needs all five checks passed and a failed attempt to build an input that tells the
  versions apart. Any such input makes it a real gap, and that input becomes the recommended test.
  Doubt makes it **unresolved**, with the missing evidence named; doubt is never a gap either.
- Real gaps get Tier 1 to Tier 4 by **what the mutated code does** (access control, money, workflow,
  logging), not by the slug. A tier ranks test work; it does not claim the program is vulnerable.
- Each real gap names the responsible test file, why it missed the mutant, and the test that would
  kill it, in prose. The analysis never edits source, tests or fixtures.
- Statistics come from the parsed data, each rate with its denominator, skipped and timed-out
  counted apart. Never turn a kill rate into a verdict on the whole suite.

Write the report to `$TMPDIR/mutation-testing-<repo>-N/mutation-testing-report.md` using
[references/report-layout.md](references/report-layout.md): `printenv TMPDIR` once (empty
means `/tmp`), `<repo>` is the basename of the working directory, and `N` is one more than the
highest existing suffix, starting at 1. Never inside the repository, even when asked for "this
directory": say where it went instead. Close in chat with a short summary
that stands on its own: the counts; one line per finding with id, file:line, the tier spelled out
("Tier 2"), what the tests miss and the test that would kill it; the equivalent and unresolved mutants with the reason; and the
raw and adjusted kill rates with their denominators.

## Bug hunt in brief

Survivors show where nobody looks; a missing test is a lead, not a bug. Rank code by sensitivity
and score, take ER in auth, crypto, parsing and validation first, read the code for its intent,
and try to reproduce with a throwaway test written under `$TMPDIR` (fall back to `/tmp` when
`TMPDIR` is unset), never in the repo. Only a reproduced issue is **confirmed**; unreproduced is
**likely**; unreachable is **dead code**; the rest is **not a bug**. Details and the write-up shape:
[references/bug-hunt.md](references/bug-hunt.md).

## Limits

- Pre-approved shell is read-only: `command -v`, `mewt|muton status`, `mewt|muton results`,
  `mewt|muton print`, `mutmut results`. They print to the terminal. Do not redirect or pipe them into
  a file (`>`, `>>`, `tee`); writing an ids file is part of a gated plan.
- Every other command prompts: `init`, `mutate`, `run`, `test`, `purge`, `gremlins unleash`,
  `mutmut run`, `npx stryker run`, and any build or test command used for timing.
- Never install a tool, add a dependency or edit a manifest.
- The analysis job writes one file, `mutation-testing-report.md`, in
  `$TMPDIR/mutation-testing-<repo>-N/`. Scratch notes and interim progress go in that same
  directory.
- Never commit or push.
