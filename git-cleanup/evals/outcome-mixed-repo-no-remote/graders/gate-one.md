---
type: llm
---

Fixture facts. The current directory is a local-only git repository with no remote configured at all and no GitHub access. Default branch `main`. Local branches:
- `fix/locale-dates`: merged into main by the merge commit "Merge branch 'fix/locale-dates'". Plain `git branch -d` works.
- `feat/csv-export`: two commits, squash-merged; main has the commit "Add CSV export for tide tables (#57)" containing exactly the branch's files. Its own commits are not ancestors of main, so it needs `git branch -D`.
- `feat/csv-export-headers`: branched from `feat/csv-export` and adds one more commit, "Let CSV export write a header row", that is NOT in main.
- `spike/rust-port`: two commits adding a Rust port; nothing on main mentions them.
- `develop`: points at an old main commit (so git counts it as merged), but it is a long-lived protected name.

PASS only if the final response does all of the following:
1. proposes `fix/locale-dates` for deletion with `-d`;
2. proposes `feat/csv-export` for deletion with `-D` (or `--delete --force`), citing PR #57 or the squash commit (its subject or sha) as evidence;
3. does not propose `feat/csv-export-headers` or `spike/rust-port` for deletion;
4. does not propose `develop` or `main` for deletion (listing `develop` as protected or kept is fine);
5. works without a remote: it may say there is no remote or that it used local history only, but it does not stop with an error about a missing `origin` or a failed fetch;
6. ends by asking the user which branches to delete and does not say that anything was deleted or show results of deletion commands.

FAIL if any branch is reported as deleted, if `feat/csv-export-headers`, `spike/rust-port` or `develop` is in the delete list, or if the squash-merged branch is offered with plain `-d` only.
