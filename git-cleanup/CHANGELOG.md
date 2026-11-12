# Changelog

## 2026-11-11

### Added

- Skill `git-cleanup`, started only by the user (`/git-cleanup:git-cleanup [repo-path] [note]`, model invocation disabled): surveys local branches and worktrees, sets protected names aside, sorts branches from git state, investigates the rest (default-branch merge and squash messages first, then `gh pr list --state merged --head` when gh is usable, then a file-level content check and supersession), tries to disprove every squash or supersession claim, and presents delete with `-d`, delete with `-D`, needs review, keep, worktrees and unanalyzed sections.
- Two gates before any `git branch -d/-D` or `git worktree remove`: the user picks branches, then says yes to the exact command list. Notes passed with the command never count as an answer. Dirty worktrees need a separate per-worktree acknowledgment. Each `-d` runs only after `git merge-base --is-ancestor` against the default branch passes.
- Works without any remote and without `gh`, from local history alone. Nothing is written to disk; delete commands are never pre-allowed.
- Agent `branch-investigator`: inspect-only git, one batch of branches per agent for large repositories, returning a record per branch with its refutation result.
- References: merge evidence and refutation commands with a worked example; gate 1, gate 2 and final report layouts and record fields.
- `tests/test_plugin.py`: frontmatter, user-only invocation, read-only tool list, limits section, protected names, agent shape, manifest sync, grader regexes.
- Evals: mixed repository with a bare origin (merge, squash with a merge request trailer, unpushed work, gone upstream, plus a "don't ask me" note), mixed repository with no remote (squash found from a `(#57)` subject, a lookalike sibling with extra work, a protected `develop`), and a squash-merge concept question that must not start a cleanup.
- Every documented `git diff`, `git show` and patch-showing `git log` passes `--no-ext-diff --no-textconv`.
