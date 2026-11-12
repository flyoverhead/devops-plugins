# Report layouts and records

## Contents

- Gate 1
- Gate 2
- Final report
- Records

## Gate 1

One message, in this order. Leave out an empty section but keep its line in the summary.

```markdown
## Branch cleanup — gate 1 of 2

Repository: <root> · default: <default> · evidence from: local history | local history + gh

### Related groups
- `perf/thumb-cache*`: perf/thumb-cache (delete, squash #212), perf/thumb-cache-webp (keep, local work)

### Delete with -d (merged into <default>)
| Branch | Evidence | Worktree |
|---|---|---|
| `docs/typo-intro` | tip 5d0e1a2 reachable from trunk (merge 77ab310) | — |

### Delete with -D (squash-merged or superseded)
| Branch | Category | Evidence | Worktree |
|---|---|---|---|
| `perf/thumb-cache` | SQUASH_MERGED | #212, squash a41c9e0, files match | — |

### Needs review
| Branch | Category | Why |
|---|---|---|
| `try/grpc` | REMOTE_GONE | upstream deleted, no merge evidence found |

### Keep
| Branch | Status | Unpushed |
|---|---|---|
| `trunk` | PROTECTED | 0 |
| `perf/thumb-cache-webp` | LOCAL_WORK | unknown |

### Worktrees
| Path | Branch | State |
|---|---|---|
| ../wt-docs | docs/typo-intro | clean, stale; ignored files deleted with it: `site/_build/` |

> **Dirty worktree ../wt-api** (`feat/api-v2`): uncommitted `api/routes.go`, `api/new.go`;
> ignored `api/.env.local`. Removing it loses these changes and the ignored files.

### Unanalyzed
none

Summary: 1 to delete with -d, 1 with -D, 1 needs review, 2 keep, 1 worktree stale, 0 unanalyzed.

Which should I delete — all recommended, a group or category, or pick branches by name?
```

## Gate 2

Only the branches and worktrees the user chose, in execution order, with each command written
exactly as it will run:

```markdown
## Branch cleanup — gate 2 of 2

1. git worktree remove '../wt-docs'
2. git merge-base --is-ancestor 'refs/heads/docs/typo-intro' 'refs/heads/trunk'
3. git branch -d 'docs/typo-intro'        (runs only if 2 exits 0)
4. git rev-parse 'refs/heads/perf/thumb-cache'   (must still print 9b2e7d4…, the analysed tip)
5. git branch -D 'perf/thumb-cache'        (runs only if 4 matches)

Run these 5 commands? (yes / no)
```

A dirty worktree appears here only after the user has acknowledged the loss of its listed files.
Its removal then carries `--force`, and the line says why.

## Final report

```markdown
## Branch cleanup — done

Deleted: docs/typo-intro (-d), perf/thumb-cache (-D); removed worktree ../wt-docs
Failed: none | <branch>: <git's error text, verbatim>
Skipped: <branch>: ancestry check failed, now needs review

Remaining:
| Branch | Status |
|---|---|
| trunk | PROTECTED |
| perf/thumb-cache-webp | LOCAL_WORK |
| try/grpc | REMOTE_GONE, needs review |
```

## Records

Kept in the conversation only. Nothing is written to disk.

Survey, per branch: `name`, `merged` (bool), `tracking` (upstream or empty), `remoteGone`
(bool), `unpushedCommits` (int, -1 when unknown), `uniqueCommits` (int), `lastCommit`
(sha and subject), `worktreePath`.

Worktree: `path`, `branch`, `dirty` (bool), `dirtyFiles` (list), `ignoredFiles` (list), `stale` (bool).

Result groups:
- `deleteCandidates`: `branch`, `category`, `evidence`, `command`, `worktreePath`, `group`, and
  `verifyWith` (the ancestry command) for SAFE_TO_DELETE only;
- `needsReview`, `keep` (PROTECTED included), `worktrees`;
- `unanalyzed`, a list of branch names.

Investigator record, per branch: `branch`, `category` (SQUASH_MERGED, SUPERSEDED, REMOTE_GONE or
LOCAL_WORK), `evidence` (PR number, merge request id, sha, superseding branch, or `none found`),
`group` (shared prefix or empty). Refutation record: `branch`, `refuted` (bool), `reason`
(naming the unaccounted commit).
