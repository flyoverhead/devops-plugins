# Changelog

## 2026-11-11

### Added

- Skill `code-improver`, started only by the user (`/code-improver:code-improver {...}`, model invocation disabled): runs a reviewer the user names (an installed skill or agent) over one directory, merges its findings into a ledger under `$TMPDIR/code-improver-<target>`, hands blocking findings to the fixer, and reviews again until a review is clean, the round budget (`maxRounds`, default 5, review-only last round) runs out, an escalation fires or a guard halts the run.
- Preconditions: a git repository with a baseline commit and no tracked changes; the plugin never runs `git init` and never commits, pushes, stashes, resets or cleans.
- Reviewer probe before any review: a reviewer that is not installed halts the run as `reviewer-unavailable` with an empty ledger and a pointer to the plugin to install; no stand-in review.
- Ledger rules: stable finding ids with coarse-key matching, fixed/rejected/deferred transitions, the `REVIEWER-UNAVAILABLE:` sentinel, and four escalation triggers (counts not decreasing, recurrence, structural rejection, relocation). Continued runs reload the ledger with a `decision` and archive old round numbers.
- `scripts/scope_guard.py` (stdlib): baseline with the scope pinned, the plugin version, and git blob hashes of untracked files, `.git/config` and `.git/hooks/*`; a scope check after every review, fix round and finalize that also catches a moved HEAD, a stash and new assume-unchanged or skip-worktree flags; resume only over the exact state the last check saw; diff snapshots; glob matching. Out-of-scope edits halt the run; nothing is reverted automatically.
- Agents: `fixer`, the only editing agent, with its own scope, pin and git limits and a scoped tool list (`git add -N`, `git diff`, `git status`, `go test`, `go vet`, `scope_guard.py match`; pins in other toolchains are reported as not run, and the skill writes each `fixes-round-N.diff` snapshot), also used for the finalize pass (narration strip, one version bump, docs fixes); `finalize-auditor`, read-only, which lists finalize regressions.
- `evals/check_contamination.py` (stdlib): flags eval runs whose trace or judge text shows grader material.
- Tests for both scripts and for the skill, agents and graders. Evals: reviewer not installed (required), and a one-off review request that must not start the loop.
- Every documented `git diff`, `git show` and patch-showing `git log` passes `--no-ext-diff --no-textconv`.
