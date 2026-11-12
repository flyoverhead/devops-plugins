# Finalize pass and its check

The finalize pass runs only after a clean review. The `code-improver:fixer` agent does the edits in
finalize mode; the `code-improver:finalize-auditor` agent checks them and edits nothing. Both read
this file by absolute path. Each duty runs only when its flag is on.

## Duty 1: narration strip (`narration_strip`)

Loop runs leave text that talks about the loop instead of the code. Search only in-scope files,
case-insensitively, for:

| Pattern | Example hit |
|---|---|
| `\b(round\|iteration\|pass)[ #-]*\d+\b` | "handled since round 2" |
| `\bprevious (fix\|attempt\|version\|round)\b` | "unlike the previous attempt" |
| `\b(was\|were) (added\|moved\|changed\|renamed\|removed) (here\|to\|from)\b` | "this check was moved here" |
| `\bper the (review\|reviewer\|finding)\b` | "renamed per the reviewer" |

- Touch only hits on lines the run itself added: the `+` lines of `pre-finalize.diff`. Text that
  was there at the baseline is the author's, not loop residue.
- Rewrite a hit so it states what the code does now, or delete it when it says nothing else.
- Leave legitimate uses: "round-trip", "pass 2 of the parser", a rounding function, an existing
  CHANGELOG entry. When it is arguable, leave it.

## Duty 2: one version bump (`version_bump`)

Applies only when the target sits in a plugin (a `.claude-plugin/plugin.json` above it or at it).

- Compare with the baseline version recorded by the skill. The end state must be exactly one
  patch step above it (`1.4.2` → `1.4.3`), however many rounds ran. The user's decision may ask
  for a minor step instead; then exactly one minor step.
- No bump yet: add one. More than one: collapse to one.
- When the repo-root `.claude-plugin/marketplace.json` repeats the plugin's version, write the
  same new version there. The two must match.
- When the plugin keeps a `CHANGELOG.md`, the bump comes with one entry under a heading dated
  today (`## YYYY-MM-DD`, create it or extend it) that lists the fixes in a line or two each.
  Never write the word "Unreleased".

With the flag off, no version or changelog line changes at all.

## Duty 3: docs match code (`docs_pass`)

Read the run's diff (`pre-finalize.diff`) and the in-scope docs: README, reference files,
skill and agent text, doc comments. Fix a statement only when the loop's changes made it false
(a renamed flag, a changed default, a removed step). Do not polish, restructure or add claims.

## Snapshot

The skill writes `post-finalize.diff` after the fixer returns. The fixer does not.

## Audit checklist (finalize-auditor)

Inputs: `pre-finalize.diff`, `post-finalize.diff`, the baseline and new versions, the flags, the
scope. Compare the two diffs and read the files around every place they differ. Report as a
regression:

1. text that was legitimate rewritten or deleted as if it were narration;
2. a doc statement made false, or a claim added that the code does not support;
3. a version that is not exactly one step above the baseline, a plugin.json and marketplace
   entry that disagree, or any version change while `version_bump` was off;
4. any change that is none of the three duties (logic, tests, formatting, unrelated docs).

Each regression is `{"file": "...", "line": n, "why": "..."}`. No regressions is a valid answer.
