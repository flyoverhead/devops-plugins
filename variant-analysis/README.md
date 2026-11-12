# variant-analysis

You found one bug. This plugin finds its siblings: the other handlers, scripts, tasks and CI
jobs where the same root cause shows up. It reads and searches only, and leaves a report in
`$TMPDIR` with a verdict per location and a rule that stops the class coming back.

```text
/plugin install variant-analysis@devops
```

## Usage

```text
/variant-analysis:variant-analysis pkg/sync/pull.go:52 branch name interpolated into git via sh -c
/variant-analysis:variant-analysis app/views.py:88 f-string SQL owner=my-org
```

Or in plain words after naming a location: "is this bug anywhere else in here?", "same
mistake in other services?", "verdict per location please", "turn this into a rule for the
whole family".

## How it works

1. **Root cause.** Four questions (operation, data, missing protection, context) become one
   sentence: *untrusted X reaches dangerous Y without protection Z*. Logic bugs get an
   invariant instead.
2. **Axes.** Other identifiers in the same role, other sinks for the same operation, logic
   shape errors, empty and boundary values, names that contradict behaviour, other layers
   (service, script, Ansible task, CI job).
3. **Exact match.** A pattern that hits only the known bug. No hit means the bug was
   misunderstood.
4. **Ladder.** Widen one element at a time (names, structure, operation, data flow), read every
   match, stop past about 50 % noise. Every version, the failed ones too, goes into the
   methodology table.
5. **Fan-out.** Above about 40 source files, one `axis-sweeper` agent per axis (five at a
   time) collects candidates; the skill merges, de-duplicates and triages.
6. **Triage.** Each candidate is argued against: guards, sanitisers, safe APIs, type limits,
   callers, plus edge cases such as both-empty comparisons. Severity and confidence are
   separate. Unprotected code with no caller today is still reported.
7. **Report and guard.** Eight sections in `$TMPDIR/variants-<repo>-<short-sha>.md`, ending
   in a Semgrep rule (or an `rg` expression for Bash, Jinja2 and CI YAML) and where to wire it.

## Cross-repository

Name a GitHub owner and it runs `gh search code --owner <owner>`. Without `gh`, without a
login, or on another git host, it says so once and runs `rg` over checkouts you list.

## Safety

- Nothing in the target is edited, built, tested or run; dynamic questions go to a
  "Worth a manual check" table with the command for a human.
- Semgrep runs local rule files with `--metrics=off`. Registry packs (`--config auto`,
  `p/…`) download rules, so they are used only after you agree.
- Only `gh search code` and `gh repo view`; no `gh api`, no GitHub writes.
- Files are written only under `$TMPDIR`. Secrets are shown as `<redacted>`.
- Nothing is installed. CodeQL is not used; see `static-analysis:codeql`.

## Not this plugin

- No bug found yet, want an audit → `insecure-defaults:audit` or `static-analysis:semgrep`.
- Which scanner findings are real → `fp-check:fp-check`.
- Review of a PR or commit range, or whether a fix brings something back →
  `differential-review:differential-review`.
- A CVE in a dependency → `vulnerability-triage-brocards:vulnerability-triage-brocards`.

## Bundled templates

`skills/variant-analysis/templates/variant-taint-{go,python,ts}.yaml`, Semgrep taint rules
with sources (request values, CLI args, environment) and sinks (shell, SQL, file paths,
unescaped markup). Each has a test file next to it.

## Required tools

`git` and `rg` (or `grep`). `semgrep` and `gh` are optional.

## Tests

```bash
python3 -m pytest variant-analysis/tests -q
semgrep --test --metrics=off variant-analysis/skills/variant-analysis/templates
```
