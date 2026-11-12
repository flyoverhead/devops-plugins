# Changelog

## 2026-11-11

### Added

- Skill `differential-review`: security review of a change set given as a GitHub PR (number or URL), a `base..head` range, a commit, a branch or a patch file; with no argument, the current branch against its merge-base with `origin/main`. Triage by repository size (DEEP, FOCUSED, SURGICAL) and per-file risk tier, before/after records for HIGH and MEDIUM hunks, `git log -S` / `git blame` history of removed and re-added security code with regressions named, test-gap tier bumps, caller counts with bands and a priority matrix, deep context and attack modelling for HIGH changes, and a nine-section report at `$TMPDIR/diff-review-<repo>-<short-head-sha>.md` plus a chat summary with a REJECT, CONDITIONAL or APPROVE verdict.
- PR input checks `git remote get-url origin` first. A non-GitHub remote, a missing or unauthenticated `gh`, or a failed first `gh` call ends in one message asking for a range, branch or patch; no retries and no other host CLI. Only `gh pr view`, `gh pr diff` and `gh search code` are pre-allowed; `gh pr comment` runs only after an explicit yes and posts the summary, not the report.
- `## Limits` in the skill and the agent: no `--output`, `--ext-diff`, `--textconv` (and `--no-index` for `git diff`), no `git grep -O`/`--open-files-in-pager`, no `gh --web`. `git grep` and `git fetch` are not pre-allowed; `git fetch` never takes `--upload-pack`.
- Agent `adversarial-modeler` (Read, Grep, Glob and `Bash(git show|log|blame|diff:*)`, `Bash(grep -rn:*)` in its tool list), one HIGH change per agent and at most five at once, returning one finding plus a confidence line.
- References: risk patterns for Go, Python, Bash, TypeScript, Terraform and Ansible with three quick greps; GitHub Actions and GitLab CI pattern files; history and caller-counting commands per stack; attack modelling with attacker models, exploitability scale, finding template and a worked example; the output format.
- `tests/test_plugin.py`: frontmatter, read-only tool lists, reference links, CI order, output sections, agent shape, manifest sync, eval regex scoping.
- Evals: two PR triggers, a regression outcome (removed CA pin replaced by an environment switch), a non-GitHub-remote fallback outcome, and a Go-idiom negative routed to `golang:review`.
- Every documented `git diff`, `git show` and patch-showing `git log` passes `--no-ext-diff --no-textconv`.
