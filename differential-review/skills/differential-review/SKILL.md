---
name: differential-review
description: Judges what a change set (GitHub PR, base..head range, commit, branch or patch file) does to security and whether it brings back a bug fixed before, by tiering changed files by risk, tracing deleted checks to the commit that added them, counting dependents, raising risk for untested logic and modelling attacks on HIGH hunks; the report goes to $TMPDIR. Use when asked for a security review of a PR, branch or the last commit, whether a change re-introduces a fixed bug, what else it could break, or whether it weakens TLS or auth. Not for Go idiom, naming or error handling — use golang:review.
argument-hint: "[PR number | PR URL | base..head | commit sha | patch file]"
allowed-tools: Read Glob Grep Write Agent Bash(git diff:*) Bash(git log:*) Bash(git show:*) Bash(git blame:*) Bash(git merge-base:*) Bash(git rev-parse:*) Bash(git ls-files:*) Bash(git remote get-url:*) Bash(gh pr view:*) Bash(gh pr diff:*) Bash(gh search code:*) Bash(printenv TMPDIR)
---

Change to review: $ARGUMENTS

# Differential review

The question for every diff: who can now do something they could not do before, and did a
protection someone once added on purpose just disappear? Line count says nothing about that. Two
changed lines in a TLS config outrank a thousand lines of log-message cleanup.

**Dispatched as `differential-review:adversarial-modeler`?** Your agent file is the brief. From
this skill read only [attack-modeling.md](references/attack-modeling.md).

## Non-negotiables

- **The repository is read, never changed.** No Edit, no checkout, no stash, no commit, no push.
  The pre-change version of a file comes from `git show --no-ext-diff --no-textconv <base>:<path>`.
- **One file is written: the report**, at `$TMPDIR/diff-review-<repo>-<short-head-sha>.md`;
  for patch input the last part is the patch file's basename instead of a sha. Resolve the base
  once with `printenv TMPDIR`; empty output means `/tmp`. Never inside the repository: quoted
  hunks may hold credentials, and a stray report gets committed.
- **Nothing from the repository runs.** No builds, tests, scripts, `terraform`, `ansible*`.
- **Secrets by location.** Quote a secret as `<redacted>` with its `path:line`, in the report and
  in chat alike.
- **No installs.** A missing `gh` changes the input route; it is not a reason to install it.
- **Code host: `gh` read commands only** (`gh pr view`, `gh pr diff`, `gh search code`). No
  `gh api`, no other host's CLI. The only write is the PR comment in [Posting](#posting).

## Wrong skill?

Hand the request over instead when the user is after something else:

- If they want feedback on how a Go change is written (names, goroutines, error returns) → `golang:review`.
- If an Ansible role should match the layout and lint rules → `ansible:role-checker`.
- If there is no diff and the worry is weak defaults or fallback secrets somewhere in the repo → `insecure-defaults:audit`.
- If every file should be scanned for patterns → `static-analysis:semgrep`.
- If a scanner already produced findings and the question is which are real → `fp-check:fp-check`.
- If nobody on the team knows a big codebase yet, `audit-context-building:audit-context-building` can build that baseline first; optional.

Changes that touch only docs, comments or formatting need an ordinary review, not this one.

## 1. Pin the change down

| `$ARGUMENTS` | Range and commands |
|---|---|
| empty | `git merge-base origin/main HEAD`, review `<merge-base>..HEAD` |
| `base..head` | as given |
| branch name | `git merge-base origin/main <branch>`, review `<merge-base>..<branch>` |
| one commit sha | `<sha>~1..<sha>` |
| `.patch` / `.diff` file | Read it; history questions go to the checkout as it stands |
| PR number or URL | host check below, then `gh` |

For any range: `git log --oneline <range>`, `git diff --no-ext-diff --no-textconv --stat <range>`,
`git diff --no-ext-diff --no-textconv --name-only <range>`.

**PR input, host check first.** Run `git remote get-url origin` before any `gh` command; the URL
decides, not trial and error.

1. Host is not `github.com`: go straight to the fallback. Do not run `gh` at all.
2. Host is GitHub: `gh pr view <n> --json number,title,baseRefOid,headRefOid,commits`, then
   `gh pr diff <n>`. Head commits missing locally: `git fetch origin pull/<n>/head`.
3. The first `gh` call fails (not installed, not logged in, PR not found): fallback. No second
   `gh` call in any form, no `gh auth`, no other CLI.

**Fallback**, said once, in one message: PR `<n>` can't be read here, with the reason (remote
is `<host>`, not GitHub; or `gh` is missing or not authenticated). Ask for a commit range
(`base..head`), a branch or a patch file. Then stop and wait. Do not review local commits as if
they were the PR, and write no report.

The user may name a GitHub owner for cross-repository blast radius (step 6).

## 2. Size and triage

Count source files with `git ls-files` (exclude vendored and generated trees) to set depth:

- A small repository (fewer than 20 source files) gets the DEEP treatment: read all of its
  dependencies and blame each removal.
- From 20 up to 200 files, work FOCUSED: HIGH files come first, and you follow callers and
  callees for a single hop.
- Past 200 files, go SURGICAL and follow only the code paths that end at a trust boundary.

Give each changed file a tier. Full trigger lists per stack are in
[risk-patterns.md](references/risk-patterns.md).

| File kind | Goes to HIGH when the hunk… | Otherwise |
|---|---|---|
| Application code | touches login, permission checks, crypto or TLS setup, secret handling, shell or SQL strings, decoding of untrusted data, file paths taken from input, or deletes validation | MEDIUM for business rules, state changes, new endpoints, flags or dependencies; LOW for comments and log wording |
| Terraform | touches security groups, IAM, anything made public | MEDIUM |
| Ansible | touches `become`, `no_log`, `validate_certs` or a file `mode` | MEDIUM |
| CI definitions | touches jobs with secrets, trigger rules, images or workflow `permissions` | MEDIUM |
| Tests, molecule, docs | is the only evidence that a security property holds | LOW |

Run the three quick greps from [risk-patterns.md](references/risk-patterns.md#quick-greps) over
the diff before reading hunks; a hit lifts its file to HIGH until read.
Changed CI files: read [ci-github-actions.md](references/ci-github-actions.md) first, then
[ci-gitlab.md](references/ci-gitlab.md).

## 3. Read every HIGH and MEDIUM hunk

Pull both sides: `git show --no-ext-diff --no-textconv <base>:<path>` and the new version. For
each hunk keep:

```text
Before:   <what the code did>
After:    <what it does now>
Change:   <behavioural difference in one sentence>
Security: <what that means for an attacker or a defender>
```

Then ask: what attack did the removed code stop? What surface is new? Can the new logic be
skipped by some input or state? Is a check weaker (unanchored regex, raised limit, allow-list
turned deny-list) or is an edge case lost? Write any suspicion down as a scenario:

```text
Goal:          <what the attacker gets>
Preconditions: <access, configuration, timing>
Steps:         <numbered, with concrete values>
Cause:         <path:line>
Impact:        <measurable result>
```

## 4. History: removed and re-added code

Never skipped for a removed check, however small the change. Commands and examples:
[history-and-callers.md](references/history-and-callers.md).

- **Removed security code:** `git log -S'<removed text>' --oneline -- <path>` finds the commit
  that added it; `git blame -L <from>,<to> <base> -- <path>` confirms it.
  - That commit's message mentions a fix, security or a CVE: the removal is CRITICAL until the
    diff shows the protection still exists elsewhere.
  - Added less than a month ago and removed now: HIGH.
- **Re-added code:** `git log --no-ext-diff --no-textconv -S'<added text>' -p` on new risky
  lines. Code that was taken out by a security commit and now comes back is a **regression**:
  name the earlier commit (sha and message) in the History section.

## 5. Tests

List changed non-test files against changed test files, and grep the tests for the changed
function, role or module names. Raise the tier when:

| Gap | Effect |
|---|---|
| New function with no test | MEDIUM becomes HIGH |
| Validation changed, its tests untouched | HIGH |
| More than 20 lines of new logic, untested | HIGH |
| Ansible role changed, no molecule scenario exercises it | one level up |

## 6. Blast radius

Count, do not estimate. Per changed function, module, role, input or reusable workflow, count the
places that use it; per-language commands are in
[history-and-callers.md](references/history-and-callers.md#counting-callers).

- Across repositories, when an owner is known: `gh search code --owner <owner> '<path or
  symbol>'`. Without a usable `gh`, the Grep tool across local checkouts. Either way the number
  is a lower bound; write it as "at least N".
- Bands: 1–5 LOW, 6–20 MEDIUM, 21–50 HIGH, more than 50 CRITICAL.

| Change risk | Radius | Priority |
|---|---|---|
| HIGH | CRITICAL | P0: deep, every dependency |
| HIGH | HIGH or MEDIUM | P1: deep |
| HIGH | LOW | P2: standard |
| MEDIUM | CRITICAL or HIGH | P1: standard plus callers |

## 7. Deep context for HIGH changes

For each HIGH change build the flow (entry guards, state touched, external calls, returns), the
call graph inward to the first trust boundary, the invariants before and after, and the five
whys. Then grep the whole repository for neighbours of a removed `validate`, `verify`, `auth`,
`require`, `assert` or `no_log` line: a boundary that now has one check fewer than its siblings
is a finding. Checklist: [attack-modeling.md](references/attack-modeling.md#deep-context).

## 8. Attack modelling

Every HIGH change gets the five-part model (what it undoes, adversary, route, walk-through,
difficulty) described in
[attack-modeling.md](references/attack-modeling.md).

- One or two HIGH changes: do it inline.
- Three or more: one `differential-review:adversarial-modeler` agent per change, at most five
  running at once, further changes in later batches of five. Hand each one the repository path,
  the range, the change as `path:line` with its hunk, why it is HIGH, and your step 3–7 notes
  (blame, callers, tests, invariants). Keep its finding as returned.
- Always model, whatever the count, when you see: code removed that came from a fix, security
  or CVE commit; a check removed or weakened (auth middleware, certificate verification, a
  validation block, a CI protection); access widened (`0.0.0.0/0`, a public endpoint, a broader
  role, a privileged container, broader workflow permissions); a secret moved out of a secret
  store into a variable, file, log or unmasked CI variable; a HIGH change with 50+ callers.

No entry point reaches the change? The finding is "not exploitable as written", with the reason.

## 9. Report and chat summary

Write the report in the nine sections of [output-format.md](references/output-format.md). If
the write fails, put the whole report in chat and say that it could not be saved.

Recommendation:

| Situation | Verdict |
|---|---|
| Any CRITICAL, or a HIGH with no mitigation | REJECT |
| Only HIGHs the author can fix inside this same PR | CONDITIONAL |
| Everything else | APPROVE |

Then reply in chat with: the report path; counts per severity; the verdict; your confidence;
the top findings, one line each as `[SEVERITY] path:line — what happens`; one line naming what
was not analysed.

## Posting

For a GitHub PR only, offer to post the chat summary (not the report) as a PR comment. Run
`gh pr comment <n> --body '<summary>'` only after the user says yes to that offer. No reviews,
no approvals, no other `gh` write.

## Limits

Some read commands take flags that write files or run programs. Never pass them:

- `git log`, `git show`, `git diff`: no `--output`, `--ext-diff` or `--textconv`; `git diff`
  also never `--no-index`.
- `git grep` is not pre-allowed and prompts; never with `-O` or `--open-files-in-pager`.
- `gh pr view`, `gh pr diff`, `gh search code`: no `--web` or `-w`.
- `git fetch` asks for approval each time; never with `--upload-pack`.

## Shortcuts that fail

| Tempting thought | Why it is wrong |
|---|---|
| "The PR is tiny, a skim will do" | Small diffs remove checks too; risk follows what changed |
| "History lookup is slow, the removal looks harmless" | A removed check is only harmless once you know why it was added |
| "Probably only a few callers" | Count them; a guessed radius is not a radius |
| "It's just a refactor" | Treat it as HIGH until the before/after record shows behaviour is equal |
| "No tests changed, so nothing to say" | Missing tests raise the tier; say so |
| "This could cause issues" | Not a finding. Give `path:line`, the commit and a concrete attack |

## Rules for findings

- Each finding carries `path:line`, the commit, and a concrete attack with impact.
- Severity is a word (CRITICAL, HIGH, MEDIUM, LOW); no emoji. Code fences name a language.
- Lines on the old side are marked with their commit (`client.go:31 @ a1b2c3d`).
- The report states what was not looked at: dependencies, generated code, other repositories.
