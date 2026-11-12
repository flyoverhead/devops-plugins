---
name: variant-analysis
description: Hunts down copies of a confirmed bug. From its path:line and why it is wrong, states the root cause, splits the search into axes, widens an exact match one element at a time with rg and local Semgrep rules, argues against every hit, and leaves a report with severity, confidence and a guard rule in $TMPDIR. Use when asked whether the same bug, mistake or pattern exists elsewhere in the repo or across an owner's repos, for a per-location verdict after a known finding, or to turn one bug into a rule for its whole family. Not for a first audit with no known bug — use insecure-defaults:audit.
argument-hint: "<path:line> <why it is wrong> [owner=<github-owner>] [extra checkout paths]"
allowed-tools: Read Grep Glob Write Agent Bash(rg:*) Bash(grep -rnE:*) Bash(git ls-files:*) Bash(git log:*) Bash(git blame:*) Bash(git rev-parse:*) Bash(gh search code:*) Bash(gh repo view:*) Bash(semgrep scan --metrics=off:*) Bash(semgrep --version) Bash(printenv TMPDIR)
---

Known bug: $ARGUMENTS

# Variant analysis

One bug is a sample. The question here is what produced it, and where else that produced
the same thing. Variants rarely live next to the original: the copy is in another handler,
the wrapper script, the Ansible task that templates the same value, or the CI job that runs
it. So the search always starts at the repository root, in every language the repo has.

**Dispatched as `variant-analysis:axis-sweeper`?** Your agent file is the brief. From this
skill read only [ladder.md](references/ladder.md).

## Ground rules

- **Read and search only.** No Edit, no checkout, no build, no test run, no execution of the
  target or its scripts. `go run`, `go test`, `python`, `ansible-playbook`, `terraform`, the
  repo's own scripts and requests to a running service are never proof of a variant.
  Whatever only execution could settle goes to "Worth a manual check" with the command.
- **Files written: only under `$TMPDIR`.** Resolve it once with `printenv TMPDIR`; empty
  output means `/tmp`. The report is `$TMPDIR/variants-<repo>-<short-sha>.md`, rule versions
  go in `$TMPDIR/variants-<repo>-<short-sha>/`, both written with the Write tool, never with
  shell redirection. Nothing goes into the repository.
- **Semgrep runs local rule files only**, always as
  `semgrep scan --metrics=off --disable-version-check --config <file> <repo root>`, results on
  stdout.
  Registry configs (`auto`, `p/…`, `r/…`) download rules: announce that and use them only
  after a yes. No semgrep → say so once, continue with `rg`. Never install anything.
- **CodeQL is not part of this skill.** For OSS-licensed code, `static-analysis:codeql` has
  the licence check.
- **GitHub: `gh search code` and `gh repo view` only.** No `gh api`, no writes of any kind.
- **Secrets**: quote as `<redacted>` with the location, in the report and in chat.

## Is this the right skill?

It needs a bug in hand: a location and a reason. Without one, do not invent one; route:

| The user wants | Go to |
|---|---|
| a first security pass over code with nothing reported | `insecure-defaults:audit` or `static-analysis:semgrep` |
| to know which scanner findings are real | `fp-check:fp-check` |
| a review of a PR, a branch, or whether a fresh fix brings something back | `differential-review:differential-review` |
| a verdict on a CVE or advisory in a dependency | `vulnerability-triage-brocards:vulnerability-triage-brocards` |
| an explanation of what a function does | answer directly, no skill |

A CVE, issue or PR id is fine as input if you can resolve it to a `path:line` in this
repository; otherwise ask for the location.

## 1. Understand the original

Read the location and the whole enclosing function, then its callers. Answer the four
questions in [axes.md](references/axes.md#the-root-cause-sentence) and write the single
statement *untrusted X reaches dangerous Y without protection Z*. For a logic bug with no
data flow, write the broken invariant instead. Record the repository name
(`git rev-parse --show-toplevel`) and `git rev-parse --short HEAD`.

## 2. List the axes

Go through the six axis kinds in [axes.md](references/axes.md#axis-kinds) and keep every
axis that names concrete identifiers or constructs, overlaps no other axis, and has at
least one `rg` lead in this repo. Always consider the other-layers axis: handler, wrapper
script, config-management task, CI job.

## 3. Exact match first

Write a pattern that hits the known instance and nothing else, and run it from the repo
root. **Zero hits means the bug was misunderstood**: go back to step 1 before searching
anything else. More than one hit at this level is already a copy-paste finding.

## 4. Inline or fan out

Steps 1–3 always run here, in this thread. Then decide who does step 5. Count the main
language's source files from the lines `git ls-files` prints (or with Glob), leaving out
`vendor/`, `node_modules/` and fixtures; do not pipe to `wc`.

- **Inline** (under about 40 files, or only one axis): do step 5 yourself, axis by axis.
- **Fan out** (larger): dispatch one `variant-analysis:axis-sweeper` per axis, at most 5 at a
  time. Each sweeper does step 5 for its axis with regex patterns only (levels 0–1,
  plus level-2 shapes written as regex) and returns candidates, not verdicts. It gets: repo root, the root-cause statement, the exact-match
  pattern, its one axis (identifiers, sink APIs or constructs), and for cross-repo hunts the
  owner or checkout paths. Semgrep levels (structure, taint) stay in this thread.

Either way, triage (step 6) happens here. With sweepers: merge their lists, drop duplicates by
`path:line`, then triage. If triage confirms a variant on an axis nobody listed, add the axis
and sweep it once more. Stop when a sweep adds nothing new.

## 5. Widen one element at a time

Follow [ladder.md](references/ladder.md): names → structure → operation → data flow, one
change per run, every new match read before the next change. Record each version, the
reverted ones too, as a methodology row (version, pattern, tool, matches, TP, FP). Past about
half noise, revert and widen a different element. Use `rg` for Bash, Jinja2, CI YAML and
recon; Semgrep for structure and taint in Go, Python, TS/JS and HCL. Level 3 starts from the
bundled templates:

- `${CLAUDE_SKILL_DIR}/templates/variant-taint-go.yaml`
- `${CLAUDE_SKILL_DIR}/templates/variant-taint-python.yaml`
- `${CLAUDE_SKILL_DIR}/templates/variant-taint-ts.yaml`

Copy one into the run directory under `$TMPDIR`, put the root-cause statement in its
message, narrow sources and sinks to the original's, and add protection Z as a sanitiser.

Exclude `vendor/`, `node_modules/`, `.git/` and test trees from candidates.

Ways a hunt goes blind, each seen in practice: scope narrowed to the original's module; a
pattern too literal to generalise; one vuln class only; one language only; happy-path only
(ignoring empty, zero and error branches); several elements generalised at once.

## 6. Triage every candidate

Argue against each one as in [triage.md](references/triage.md): enclosing function,
callers, guards, sanitisers, safe APIs, type constraints, caller set. Try the edge cases on
every candidate (both sides empty, inverted name, anonymous caller, zero, empty
collection, type boundary).

- Reachable, controllable, unprotected → confirmed variant.
- Unprotected but no caller today → still a variant at lower severity; say what would make
  it reachable. "No callers" is not a refutation.
- A different protection present → false positive, recorded with that protection.
- Every verdict carries two labelled fields: severity (info, low, medium, high, critical) and
  confidence (low, medium, high; no in-between values). Informational findings stay.
- Group false positives by reason with counts: they become `pattern-not` clauses.

## 7. Spread across repositories (only when asked)

Run this step only when the user names a GitHub owner or other checkouts.

1. `gh search code --owner <owner> '<most distinctive literal>'`, narrowed with
   `--language` or `--filename`. It searches literals, not regexes; pick the literal from
   the best level-1 or level-2 pattern.
2. When `gh` is missing, not logged in, the first call fails, or the code lives on a
   non-GitHub host: say once that you are switching to the local fallback, then run
   `rg -n -e '<pattern>' <checkout>` over each checkout the user gave, or the Grep tool on
   its path. `git grep` inside a checkout also works but is not pre-approved and asks first.
   No second `gh` attempt, no other host CLI.
3. Hits from other repositories go through the same triage; read their code from the local
   checkout or the search result, and lower confidence where a hop could not be read.

## 8. Report, guard, answer

Write the report with the eight sections of
[output-template.md](references/output-template.md), then the regression guard: a ready
Semgrep rule built from the best-yielding version, or for Bash, Jinja2 and CI YAML an `rg`
expression, plus where to wire it (the repo's own Semgrep config or lint setup, a
pre-commit hook, a CI job). The guard is proposed in the report, not added to the repo.

In chat, answer per location:

```text
Original  billing/views.py:88        invoice id f-string'd into cursor.execute
Variant   billing/refunds.py:41      severity high, confidence high      same f-string, refund id from the URL
Variant   tools/reindex.sh:17        severity medium, confidence medium  psql -c "$1", called by a cron task
Ruled out billing/export.py:30       bound parameter (%s, (id,))
Ruled out billing/stats.py:12        literal query, no input
Report: /tmp/variants-ledger-9f0e2d1.md
```

Name both the real variants and every ruled-out candidate with its reason. If the report
cannot be written, say so and give it in chat.

## Limits

- Static reading only. Execution-dependent questions go to "Worth a manual check".
- Semgrep taint is intraprocedural; cross-function flow is traced by reading callers, and
  confidence says so when a hop was inferred.
- `gh search code` covers only indexed default branches of repositories you can see.
- Pre-approved commands carry flags that would break the read-only contract:
  - `git log`: never `--output`;
  - `git grep` (not pre-approved, asks first): never `-O` or `--open-files-in-pager`;
  - `rg`: never `--pre`;
  - `gh`: never `--web`;
  - `semgrep scan`: never `--autofix`, `-o`/`--output`, or any `--*-output` flag
    (`--json-output=`, `--sarif-output=`, `--text-output=`, `--junit-xml-output=`,
    `--emacs-output=`, `--vim-output=`, `--gitlab-sast-output=`, `--gitlab-secrets-output=`);
    each writes a file or posts to a URL. Always add `--disable-version-check`; registry
    configs only after a yes.
- No CodeQL, no installs, no edits, no pushes, no comments on GitHub.
