---
name: spec-to-code-compliance
description: Measures code against the promises its own documents make — README guarantees, design notes, OpenAPI, doc comments, role argument_specs, Terraform variable descriptions, CI input text, --help — with one checker agent per requirement and two refuter agents per divergence, then reports verdict, severity and path:line evidence per requirement in $TMPDIR. Use when asked whether code does what its README or design doc says, which documented guarantees hold, or for a per-guarantee sign-off before a release. Not for bug hunting without a spec — use insecure-defaults:audit.
argument-hint: "[spec file] [limit=N] [path subset]"
allowed-tools: Read Grep Glob Write Agent Bash(git ls-files:*) Bash(git rev-parse:*) Bash(git log:*) Bash(printenv TMPDIR)
---

Request: $ARGUMENTS

# Spec-to-code compliance

A document is a promise; the code either keeps it or does not. Every gap found here ends up
as one of two things: a code bug, or a document that needs fixing. Saying which is the job.

**Running as `spec-to-code-compliance:spec-compliance-checker` or
`spec-to-code-compliance:divergence-refuter`?** Your agent file is your brief. Follow it and
skip everything below.

## Does this request belong here?

There has to be a document stating intent. Without one there is nothing to hold the code to,
and code compared with itself proves nothing.

| The user actually wants | Send them to |
|---|---|
| bugs found with no document in play: defaults, hardcoded credentials, fail-open config | `insecure-defaults:audit` |
| a pattern or ruleset scan | `static-analysis:semgrep` |
| a map of unfamiliar code before anything else | `audit-context-building:audit-context-building` |
| a PR, branch or commit range vetted | `differential-review:differential-review` |
| requirements inferred from code because no document exists | `audit-context-building:audit-context-building` |

A bug that neither the document nor the requirement mentions is out of scope (one line under
Open questions at most). A bug the document itself endorses is a finding against the document.

## Ground rules

- **Read-only.** No Edit, no execution of the target: no builds, tests, `go run`, scripts,
  playbooks, `terraform`, requests to a running service. No network, no `gh`.
- **Writes only under the output directory**, with the Write tool and absolute paths. Resolve
  `$TMPDIR` with `printenv TMPDIR`; if it prints nothing, use `/tmp`. Nothing goes into the
  repository.
- **Secrets**: a requirement about a secret is checked by location. Values are written
  `<redacted>`, in files and in chat.
- **No approval gates**: nothing is downloaded or run, so the skill goes straight through.
- **Agents are not optional, whatever the repository size.** Checking inline looks the same
  for the first two or three requirements and then quietly gets shallower; a fresh agent per
  requirement does not. A divergence nobody tried to knock down is not reported as one.

## 1. Set up

- Repository root: `git rev-parse --show-toplevel`; repo name is its last path segment.
- Short sha: `git rev-parse --short HEAD`.
- Output directory: `<TMPDIR>/spec-compliance-<repo>-<short-sha>/`, with `REPORT.md` and
  `requirements/<id>.md` inside. Pass this resolved absolute path to every agent.

## 2. Find the documents

Look by content, not by file name: a `NOTES.md` may hold the real guarantees and a
`SECURITY.md` may hold none. Use `git ls-files` and Grep for wording such as *must*,
*never*, *guarantee*, *only*, *at most*, *required*, *expires*. The kinds that count, and
where each stack keeps them, are in [sources.md](references/sources.md).

- Skip changelogs, contributor guides and build instructions; they describe process, not
  behaviour.
- A user-named spec file replaces the search; a path subset narrows it.
- A document that cannot be read (binary, broken encoding, missing link target) goes in the
  Unreadable documents list with the reason.
- Standards (RFC, FIPS, IEEE and the like): work only on the sections the user names and
  record which sections were not covered. Definitions often sit in a different section from
  the requirement that uses them; read both.

## 3. Extract the requirements

For each claim, record: id, the exact sentence quoted, and `file:line` plus section.

- **Split** compound sentences: "signed and expires after an hour" is two requirements.
- **Force** comes from the document's own words: MUST / NEVER / ALWAYS / "only" are
  mandatory, SHOULD is advisory, plain description is descriptive. Emphasis (bold, capitals)
  does not change force.
- **Vague claims** ("handles load gracefully") are still extracted and flagged vague; they
  usually end as `undecidable`.
- **Ids** `REQ-01`, `REQ-02`, … unique across all documents.
- **Two documents disagreeing** with each other is a document finding by itself.
- **Rank**: mandatory first, then by what breaks if the claim is false (access, secrets,
  data loss above cosmetics). Keep the top 10; up to 30 when the user asks; a limit the user
  names wins. Everything past the cut goes to Not checked, quoted, with its id.

For each kept requirement, note the code paths a checker should start from (Grep for the
nouns and numbers in the quote). These are starting points, not conclusions.

## 4. Check: one agent per requirement

Dispatch `spec-to-code-compliance:spec-compliance-checker` once per kept requirement, at most
5 at a time (send up to five Agent calls together, wait, then the next batch). Each prompt
carries:

- repository root;
- id, verbatim quote, document location;
- documents and code paths found for it;
- output path `<out>/requirements/<id>.md` (absolute).

Each returns a record: `id`, `verdict`, `confidence`, `analysisFile`, `evidence`, `searched`,
`documentProblem`, `reasoning`. The six verdicts and what each needs are in
[verdicts.md](references/verdicts.md); three easy-to-misjudge cases are worked through in
[calibration.md](references/calibration.md). A record missing evidence for its verdict is
sent back once to the same requirement with the gap named; a second miss is reported as
Unverified.

## 5. Refute every divergence

Every verdict other than `implemented` is a divergence. For each, dispatch two
`spec-to-code-compliance:divergence-refuter` agents: one with `lens: code`, one with
`lens: document`. At most 5 refuters run at once. Each gets the requirement (id, quote,
location), the checker's record, the analysis file path and its lens.

Apply the outcomes exactly; you never overrule a refuter:

- either lens returns `refuted: yes` → the divergence is dropped and listed under Refuted
  with the refuter's evidence;
- `revisedVerdict` set → use it (an `absent` that is really `partial`);
- `correction` set → the divergence stands with the corrected description;
- both refuter agents failed or returned nothing usable → the item goes to Unverified, not
  to the findings.

## 6. Reverse direction (your own pass)

From the code outward: what can an outside actor reach that no document mentions? Routes and
handlers, CLI flags and env vars, role variables, module inputs, CI inputs, admin or debug
paths. List only what has a consequence (it moves data, grants access, disables a check).
An empty list is a valid result; say it is empty.

## 7. Severity

Grade each surviving divergence with the scale in
[verdicts.md](references/verdicts.md#severity). Severity follows consequence, not how far the
code's wording is from the document's. A verdict is not automatically a finding: `absent` on
a mandatory access rule is one; `absent` on a roadmap sentence is not.

## 8. Report, then reply

Write `REPORT.md` in the layout of [file-formats.md](references/file-formats.md) before
answering. Every code claim cites `path:line`; every document claim is quoted. A claim that
cannot be cited is either dropped or turned into an Open question; hedge words are not a
substitute.

Then reply in chat:

```text
Report: /tmp/spec-compliance-billing-api-4c1d9e0/REPORT.md
High    REQ-02  partial       "refunds require a second approver" — skipped when amount < 100 (internal/refund/approve.go:57)
Low     REQ-05  stronger-than-spec  doc says 30 s timeout, code enforces 10 s (pkg/client/http.go:22); fix the doc
Held    REQ-01 REQ-03 REQ-04
Refuted REQ-06 (enforced in middleware, cmd/api/routes.go:31)
Not checked: REQ-11..REQ-14 (limit 10); docs/rfc-draft.md unreadable
```

Surviving divergences by severity first, then what held, what was refuted, and what was not
checked or could not be verified. Two lines are never dropped:

- `Report:` with the resolved absolute path from step 1, never the literal `$TMPDIR`;
- `Not checked:` with what was left out, or `nothing` when every requirement was checked.

If the report could not be written, say why and give it in chat.

## Limits

- Static reading only. A question only execution could settle becomes an Open question
  naming what would need to run.
- Settings outside the repository (CI project settings, branch protection, gateway config)
  are named as unseen, never assumed.
- `git log` is pre-approved for history only: never pass `--output`, which writes a file.
- No edits, no network, no installs, no pushes, no comments anywhere.
