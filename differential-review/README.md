# differential-review

Security review of a change rather than a codebase. Give it a GitHub PR, a `base..head` range,
a commit, a branch or a patch file; it asks what the change does to security and whether it
brings back something that was fixed before. The repository is only read. The result is a
report in `$TMPDIR` and a short summary in chat with a REJECT, CONDITIONAL or APPROVE verdict.

```text
/plugin install differential-review@devops
```

## Usage

```text
/differential-review:differential-review                 # current branch vs merge-base with origin/main
/differential-review:differential-review 42              # GitHub PR number (needs gh)
/differential-review:differential-review https://github.com/acme/app/pull/42
/differential-review:differential-review v1.8.0..HEAD
/differential-review:differential-review 3f2a91c         # one commit
/differential-review:differential-review ~/Downloads/fix.patch
```

Or in plain words: "security review of this branch", "does the last commit re-introduce the
TLS bug we fixed?", "what else could this PR break?".

## What it does

1. **Resolves the change.** Ranges, branches, commits and patches use plain git and work on
   any host. A PR goes through `gh pr view` / `gh pr diff`, but only after
   `git remote get-url origin` shows GitHub.
2. **Triages.** Repository size sets the depth (under 20 source files DEEP, up to 200 FOCUSED,
   above that SURGICAL). Each file gets HIGH, MEDIUM or LOW; three greps over the diff catch
   dangerous additions, removed checks and CI trigger changes.
3. **Reads HIGH and MEDIUM hunks** side by side with the base (`git show <base>:<path>`).
4. **History.** Every removed check is traced with `git log -S` and `git blame` to the commit
   that added it. Removing code from a fix or security commit starts at CRITICAL. Code that a
   security commit once removed and this change adds back is reported as a regression.
5. **Tests.** Untested new logic and validation changes with untouched tests raise the tier.
6. **Blast radius.** Callers are counted per language, plus `gh search code --owner` (or
   Grep over local checkouts) across repositories, reported as a lower bound.
7. **Attack modelling** for every HIGH change: what it undoes, adversary, route to the changed
   line, walk-through, difficulty. Three or more HIGH changes go to `adversarial-modeler`
   agents, one change each, five at a time.
8. **Report** in nine sections, then the chat summary. Posting the summary as a PR comment is
   offered and runs only after you say yes.

CI coverage: GitHub Actions first (`pull_request_target` with PR checkout, `${{ github.event.* }}`
in `run:`, unpinned actions, token permissions, secrets reachable from forks), then generic
GitLab CI (widened rules, mutable images and includes, silenced security jobs).

## No GitHub?

With no `gh`, no `gh` login, or an `origin` that is not GitHub, a PR number cannot be read. The
skill says so once and asks for a commit range, branch or patch; it does not retry or try other
tools.

## Safety

- No edits, checkouts, commits or pushes. Nothing from the repository is built or run.
- The only file written is `$TMPDIR/diff-review-<repo>-<short-head-sha>.md`, outside the repo.
  If that write fails, the full report goes to chat.
- Secrets are shown as `<redacted>` with their location.
- `gh api` and `gh` write commands are not pre-allowed; `gh pr comment` needs your yes.
- `git fetch` asks for approval each time. Flags that write files or run programs
  (`--output`, `--ext-diff`, `--textconv`, `git grep -O`, `gh --web`) are never used.
- Nothing is installed.

## Not this plugin

- Want comments on Go style, error returns or goroutines? → `golang:review`.
- Checking that an Ansible role follows layout and lint rules? → `ansible:role-checker`.
- Hunting weak defaults in a repository without any diff? → `insecure-defaults:audit`.
- Scanning every file for patterns? → `static-analysis:semgrep`.
- Deciding which scanner findings are real? → `fp-check:fp-check`.
- Getting oriented in a large codebase first? → `audit-context-building:audit-context-building`.

## Required tools

`git`. `gh` is optional, only for PR input, cross-repository counts and posting.

## Tests

```bash
python3 -m pytest differential-review/tests -q
```
