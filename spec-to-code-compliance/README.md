# spec-to-code-compliance

Checks whether code keeps the promises its documents make. It pulls each requirement out of
a README, design note, OpenAPI file, doc comment, role `argument_specs`, Terraform variable
description, CI input description or `--help` text, checks it against the code, and decides
for every gap whether the code or the document is wrong. The repository is only read; the
result is a report in `$TMPDIR` and a short answer in chat.

```text
/plugin install spec-to-code-compliance@devops
```

## Usage

```text
/spec-to-code-compliance:spec-to-code-compliance                    # find the documents, top 10 requirements
/spec-to-code-compliance:spec-to-code-compliance docs/design.md     # one named spec
/spec-to-code-compliance:spec-to-code-compliance limit=25 roles/mq   # more requirements, one path
```

Or in plain words: "does the code do what the README says?", "check the implementation
against the design doc", "which of these guarantees actually hold?", "give me a verdict per
guarantee before we release".

Stacks: Go and Python services, CLIs and Bash, Ansible roles, Terraform modules, and CI
pipelines (GitHub Actions, then GitLab CI).

## How it works

1. **Documents.** Found by what they say, not their file names. Changelogs, contributor guides
   and build instructions are skipped. Unreadable documents are listed.
2. **Requirements.** Each one is quoted with its location. Compound sentences are split, and
   force comes from the document's own wording (MUST / NEVER / ALWAYS, SHOULD, descriptive).
   Ids run `REQ-01`, `REQ-02`, …. The top 10 are kept, mandatory first, then by consequence;
   up to 30 on request. The rest are listed as not checked.
3. **Check.** One `spec-compliance-checker` agent per requirement, five at a time. Each one
   reads the enforcement, its callers and callees, walks every path, logs its searches, and
   writes `requirements/<id>.md`. The verdict is one of `implemented`, `partial`,
   `contradicted`, `stronger-than-spec`, `absent` or `undecidable`.
4. **Refute.** Every verdict other than `implemented` gets two `divergence-refuter` agents,
   one reading the code again and one reading the document again. If either refutes it, the
   gap is dropped. If both fail, it is reported as unverified.
5. **Reverse direction.** Routes, flags, variables and inputs that an outside actor can reach
   but no document mentions.
6. **Report.** Severity is critical, high, medium or low, judged by consequence. Each finding
   has `path:line` evidence and the quoted requirement.

The agents run even on tiny repositories. Checking inline gets shallower after a few
requirements without looking any different, and a gap that nobody tried to refute is not
worth reporting.

## Output

`$TMPDIR/spec-compliance-<repo>-<short-sha>/` (falls back to `/tmp` when `TMPDIR` is unset):

- `REPORT.md` has these sections: findings, held, document problems, undocumented
  behaviour, refuted, unverified, not checked, unreadable documents and open questions;
- `requirements/REQ-NN.md` holds one analysis per checked requirement.

The chat reply gives the report path, the surviving divergences by severity, what held and
what was not checked.

## Not for

| Task | Use |
|---|---|
| bug hunting with no document: defaults, hardcoded credentials | `insecure-defaults:audit` |
| pattern scanning | `static-analysis:semgrep` |
| mapping unfamiliar code first, or no document exists | `audit-context-building:audit-context-building` |
| a PR or commit range | `differential-review:differential-review` |

## Safety

- Read-only: no edits, no execution of the code, no network, no `gh`.
- Files are written only in the output directory. Checker agents write only their own
  analysis file, and refuter agents write nothing.
- Secret values are never quoted, only their locations.
- Pre-approved shell commands: `git ls-files`, `git rev-parse`, `git log` (never with
  `--output`) and `printenv TMPDIR`.

## Tests

```text
python3 -m pytest spec-to-code-compliance/tests -q
claude plugin eval ./spec-to-code-compliance --trust-plugin --scaffold --no-publish --allow-tools Write Edit Bash
```
