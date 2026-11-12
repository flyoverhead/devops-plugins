# Merge evidence and refutation

`<g>` below is the git invocation chosen in step 1: `git`, `git -C '<root>'`, or a full-path
git. `<d>` is the default branch written as the full ref `refs/heads/<default>` (never
`origin/<default>`). `<b>` is the bare name of the branch under investigation. In every git
revision expression (`merge-base`, `diff`, `cherry`, `log` ranges, `--is-ancestor`) it is written
`refs/heads/<b>`, and so are `<older>` and `<newer>`: a bare name resolves to a same-named tag
first, and a tag on merged content would make every check below pass for unproven work. The bare
name appears only in `--grep` text, `gh pr list --head` and `git branch -d/-D`. Everything goes
in single quotes.

## Contents

- Reading the default branch's messages
- Asking gh
- Confirming content
- Supersession
- Refutation
- Worked example

## Reading the default branch's messages

Start from the 40-commit window collected in the survey. Then search the whole default branch
for this one branch:

```bash
<g> log --format='%h %s' --fixed-strings --grep='<b>' '<d>'
<g> log --format='%h %s' -E --grep='\(#[0-9]+\)$' -n 200 '<d>'
<g> log --oneline '<d>..refs/heads/<b>'
```

Shapes that count as a lead:

| Message on the default branch | Lead |
|---|---|
| `Merge pull request #31 from someone/<b>` | PR #31, merge commit sha |
| `Merge branch '<b>'` or `Merge branch '<b>' into main` | merge commit sha |
| `<subject> (#57)`, a squash from a hosted PR | PR #57, squash sha, if the subject matches the branch's own subjects or name words |
| body line `See merge request group/project!88` | merge request !88, that commit's sha |

A lead is only a lead. Whatever the shape, confirm the content before you call it evidence.

## Asking gh

Ask only when the remote is on github.com and `gh auth status` succeeded during the survey. Make
one call per branch. `<owner>/<name>` comes from the target repository's `origin` URL
(`git@github.com:<owner>/<name>.git` or `https://github.com/<owner>/<name>`):

```bash
gh pr list --repo '<owner>/<name>' --state merged --head '<b>' --json number,title,mergeCommit,headRefOid
```

- No PR → no lead from gh. That is not proof of anything either way.
- `headRefOid` differs from the local tip → the local branch has commits the PR never saw. Check
  `<g> log --oneline '<headRefOid>..refs/heads/<b>'`. Any output means those commits are not accounted for.
- `mergeCommit.oid` gives you the sha to confirm against.

## Confirming content

For a lead commit `<sha>` and the branch's fork point `<mb>` (`<g> merge-base '<d>' 'refs/heads/<b>'`):

```bash
<g> show --stat '<sha>'
<g> diff --no-ext-diff --name-only '<mb>' 'refs/heads/<b>'
<g> diff --no-ext-diff --stat 'refs/heads/<b>' '<sha>' -- <each file from the line above, single-quoted>
```

Empty output from the last command means the evidence commit holds the branch's version of every
file the branch touched. Compare against `<sha>`, not against the tip of `<d>`. Later commits on
default may have changed those files again.

Rebase merges and cherry-picks:

```bash
<g> cherry -v '<d>' 'refs/heads/<b>'
<g> log --cherry-pick --right-only --oneline '<d>...refs/heads/<b>'
```

`-` lines in `git cherry` have an equivalent patch on default. `+` lines do not. A squash of two
or more commits always shows `+`, so for squashes use the file comparison above.

## Supersession

```bash
<g> merge-base --is-ancestor 'refs/heads/<older>' 'refs/heads/<newer>'
<g> cherry -v 'refs/heads/<newer>' 'refs/heads/<older>'
```

Exit 0 on the first command, or only `-` lines from the second, means every commit of `<older>`
lives on in `<newer>`. Name `<newer>` as the evidence. The newer branch itself is judged on its
own: superseding something does not make it deletable. If both tips are the same commit, the
check passes both ways; only one of the pair may be marked SUPERSEDED, by the other.

## Refutation

Take the role of someone trying to keep the branch. List its commits with
`<g> log --oneline '<mb>..refs/heads/<b>'` and try to place each one:

- Squash, merge request or PR claim: the commit's files must match inside the cited commit (the
  file comparison above). One file that differs → refuted. Name the commit and the file.
- Supersession claim: the commit must be in `<newer>` (ancestry or `-` in cherry). It does not
  have to be in default.
- A local tip newer than the PR head (`headRefOid`) → refuted.
- A command that failed, or a result you cannot read → refuted. Doubt counts as refuted.

Refuted branches become REMOTE_GONE (needs review) with the reason written out.

## Worked example

Default `trunk` has `a41c9e0 Speed up thumbnail cache (#212)`. Local branch `perf/thumb-cache`
has no upstream and three commits. The message matches the branch name words and a PR number,
so it is a lead. `diff --name-only` on the fork point gives `cache/thumbs.py` and
`tests/test_thumbs.py`. `diff --no-ext-diff --stat 'refs/heads/perf/thumb-cache' 'a41c9e0' -- …` comes back empty, so the
content is confirmed. Refutation: all three commits touch only those two files, so nothing is
left over. The verdict is SQUASH_MERGED, evidence `#212, squash a41c9e0`, command `-D`.

A sibling, `perf/thumb-cache-webp`, starts from that branch and adds `cache/webp.py`. The same
lead fails for it, because `cache/webp.py` does not exist in `a41c9e0`. It has no upstream and
no other evidence, so the verdict is LOCAL_WORK, keep.
