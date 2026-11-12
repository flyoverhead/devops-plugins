# git-cleanup

Finds the local branches and worktrees whose work already lives elsewhere, shows the proof for
each, and deletes them only after you have picked them and approved the exact commands. It works
in repositories with no remote at all. Squash merges are recognised from the default branch's
commit messages and a content check, and `gh` is an optional extra source.

```text
/plugin install git-cleanup@devops
```

## Usage

The skill never starts on its own. Run it by name:

```text
/git-cleanup:git-cleanup                 # repository in the current directory
/git-cleanup:git-cleanup ~/src/portal    # another repository
```

Anything typed after the path is read as a note. It never replaces a confirmation.

## What you get

| Section | Meaning | Command offered |
|---|---|---|
| Delete with `-d` | reachable from the default branch | `git branch -d`, after an ancestry check |
| Delete with `-D` | squash-merged (PR, merge request or squash commit named) or superseded by a newer branch | `git branch -D` |
| Needs review | upstream gone and no proof, or a claim that failed refutation | none |
| Keep | protected names, unpushed commits, in sync with the remote, local-only work | none |
| Worktrees | stale (clean, branch being deleted) or dirty, with the changed files | `git worktree remove` |
| Unanalyzed | anything the run did not get to | none |

Protected and never offered: the default branch, the current branch, `main`, `master`, `trunk`,
`develop`, `dev`, `devel`, `integration`, `staging`, `stage`, `production`, `prod`, `preprod`,
`qa`, `uat`, `next`, `canary`, `stable`, and `release/`, `release-`, `hotfix/`, `support/`,
`maint/`, `maintenance/` prefixes.

## How it decides

1. **Survey** with read-only git: branches, upstream tracking, `--merged`, worktrees and their
   status, the recent default-branch messages. It runs `git fetch --prune` only when a remote
   exists.
2. **Sort** what git state settles alone: merged, unpushed, in sync.
3. **Investigate** the rest. It reads merge and squash messages on the default branch first,
   then runs `gh pr list --state merged --head <branch>` if gh works for a GitHub remote, then
   compares the branch's files with the cited commit and checks supersession by ancestry or
   cherry. Branches sharing two leading name segments are examined together. For more than
   eight such branches it hands batches to the `branch-investigator` agent.
4. **Refute** every squash or supersession claim by trying to find one branch commit whose
   change is not accounted for. Doubt sends the branch to needs review.
5. **Gate 1:** the full analysis, then "which to delete?". **Gate 2:** the exact commands in
   order, then "yes or no?". A dirty worktree is removed only after you acknowledge its files
   by name.
6. **Execute** one command at a time and report deleted, failed and remaining branches.

## Safety

- Read-only until gate 2. `git branch -d/-D` and `git worktree remove` are not pre-allowed, so
  each also raises a permission prompt.
- No push, no remote branch deletion, no pull request changes, no rebase, reset or gc.
- Branch names and commit text are treated as data. Every name goes into commands in single
  quotes.
- Nothing is written to disk and nothing is installed.

## Not this plugin

- "Why does `git branch -d` refuse my squash-merged branch?" is a question; ask it plainly and
  you get an answer, not a cleanup run.
- Remote branches, pull requests, history rewriting, reflog or gc are out of scope.

## Tests and evals

```bash
python3 -m pytest git-cleanup/tests -q
claude plugin eval ./git-cleanup --trust-plugin --scaffold --no-publish --allow-tools Bash
```

## License

MIT
