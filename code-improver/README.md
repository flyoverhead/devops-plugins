# code-improver

Runs a review, fixes what it found, and reviews again, until a review comes back clean. You
choose the reviewer: any review skill or agent you have installed, such as `golang:review`,
`ansible:role-checker` or `differential-review:differential-review`. The plugin ships no
reviewer of its own. Every finding and verdict is kept in a ledger across rounds, a guard proves
that nothing outside the agreed scope changed, and the run stops and asks you when the loop
starts going in circles. Nothing is committed: you read the diff and commit yourself.

```text
/plugin install code-improver@devops
```

## Usage

The skill never starts on its own. Run it with a JSON object:

```text
/code-improver:code-improver {"target": "internal/store", "reviewer": {"kind": "skill", "name": "golang:review"}}
/code-improver:code-improver {"target": "roles/chrony", "reviewer": {"kind": "skill", "name": "ansible:role-checker"}, "scope": ["roles/chrony/**"], "maxRounds": 3}
```

| Key | Default | Meaning |
|---|---|---|
| `target` | required | directory to improve |
| `reviewer` | required | `{"kind": "skill" or "agent", "name": "<plugin>:<name>", "notes": "..."}`; `notes` goes to every review |
| `scope` | enclosing plugin dir, else the target, as `<dir>/**` (asked first) | repo-relative globs the loop may change; `**` spans directories, `*` stays in one segment |
| `maxRounds` | 5 | fix rounds, 1–20 (anything else is asked again); one more review-only round follows the last |
| `out` | `$TMPDIR/code-improver-<target name>` | ledger and diffs |
| `finalize` | bump only inside a plugin; strip and docs on | `version_bump`, `narration_strip`, `docs_pass` |
| `decision` | none | your ruling on an earlier escalation |

Before it starts, the repository needs a commit and no uncommitted changes to tracked files.
Untracked files may stay; the guard hashes them. With `version_bump` on, the plugin's
`plugin.json`, its `CHANGELOG.md` and a marketplace entry that repeats the version join the scope
before the baseline pins it. A run resumes over its own earlier edits only when you pass a
`decision` and the tree is exactly as the last check left it.

## How a run goes

1. **Baseline:** HEAD, untracked file hashes, the plugin version if the target is in a plugin.
2. **Reviewer probe:** if the reviewer is not installed, the run halts as `reviewer-unavailable`
   and tells you which plugin to install. It never reviews in the reviewer's place.
3. **Rounds:** review → merge into the ledger → stop if clean → escalation check → `fixer` agent
   fixes the critical and major findings → scope guard. Minor and info findings are recorded,
   never fixed by the loop.
4. **Finalize** (clean runs only): the fixer strips loop narration from lines the run added,
   makes exactly one version bump (plugin.json, marketplace entry and CHANGELOG together), and
   corrects docs the run made false. The read-only `finalize-auditor` agent checks that pass.
5. **Report:** converged, capped, escalated or halted, with open findings and next steps.

## Escalation

The loop stops and hands the decision to you when the open blocking count has not gone down in
three reviews, a finding shows up in three reviews in a row, the fixer says a finding can only
be met by weakening a documented guarantee, or a finding gets "fixed" in two different rounds.
Resume with the same `target` and `reviewer` plus `"decision": "<your ruling>"`.

## Out directory

`ledger.json`, `ledger.md`, `status.md`, `baseline.json`, `fixes-round-N.diff` (cumulative against
the baseline), `pre-finalize.diff`, `post-finalize.diff`.

## Safety

- No commit, push, stash, reset, clean, checkout or `git init`, ever.
- Only the `fixer` agent edits, only inside the scope. After every fix round and after finalize,
  `scope_guard.py` compares changed tracked paths and untracked file hashes with the scope. Any
  change outside it halts the run; nothing is reverted for you.
- The guard also halts on a commit or stash (HEAD moved, `refs/stash` present), on
  assume-unchanged or skip-worktree flags set during the run, and on any change to `.git/config`
  or `.git/hooks/*`. The scope is pinned at the baseline; a check with another scope fails.
- Blind spots: files ignored by `.gitignore`, and everything else under `.git/` (refs other than
  HEAD and the stash, `info/`, the object store), are outside the guard's view.
- The fixer's git limits are instructions, not a hook: Claude Code ignores `hooks` in plugin
  agent frontmatter, and a plugin-wide hook would block those commands for your whole session.
  Detection by the guard is the enforcement.
- The fixer's shell is limited to `git add -N`, `git diff`, `git status`, `go test`, `go vet` and
  `scope_guard.py match`. A pin in another toolchain (pytest, npm) is written but reported as not
  run, so run it yourself before you keep the change.
- A review that changes files halts the run.

## Not this plugin

- "Anything wrong with this file?" is a one-off review: run the reviewer directly.
- One known fix: just ask for it.
- Committing, pushing, opening a PR: yours, after reading the diff.

## Tests and evals

```bash
python3 -m pytest code-improver/tests -q
claude plugin eval ./code-improver --trust-plugin --scaffold --no-publish --allow-tools Write Edit Bash
python3 code-improver/evals/check_contamination.py .eval-out/code-improver.json
```

The contamination check needs traces, so run the eval with `--keep-temp` for it to read agent
traces; without them it checks judge text only and warns.

## License

MIT
