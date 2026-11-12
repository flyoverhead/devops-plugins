---
name: implement-patch
description: Repairs one confirmed bug where its invariant breaks, inside the finding's repair_scope — before-repair gate, a hunt for same-invariant variants, suite before and after, a regression test seen failing on the unpatched code first, the smallest reviewable fix, then one local `git commit -s` plus fix.patch, tests.patch and patch.json under $TMPDIR. Use when patching-bugs:patching-bugs hands over a patch attempt, or a confirmed finding.json needs that fix. Not for a quick fix with no confirmed finding (just edit the code) nor for judging the commit — use patching-bugs:prove-patch.
argument-hint: "<run-dir> <attempt 1-3> [checkout]"
allowed-tools: Read Grep Glob Bash(git rev-parse:*) Bash(git status:*) Bash(git log:*) Bash(git show:*) Bash(git diff:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py:*)
---

Request: $ARGUMENTS

# Fix the invariant, not the example

The reported input is one symptom. Find the rule the code is supposed to keep (the `invariant` in
`finding.json`), find every place inside the `repair_scope` boundary that breaks it the same way,
and restore the rule there with the smallest change a reviewer can read in one sitting. Then
commit once, locally, signed off.

Scripts: `${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/`. Record fields:
`${CLAUDE_SKILL_DIR}/../patching-bugs/references/records.md`.

Write every path in commands literally and absolutely; never put the run directory, the scripts
or the checkout in a shell variable. The transcript is part of the evidence.

## Preconditions

1. Gate, before anything else:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py check /abs/run --before-repair
   ```
   Exit 1 → stop and return the error text; the coordinator reports INCONCLUSIVE.
2. `finding.json` status is `confirmed` and `validate/validate.json` says `confirmed`. Without a
   confirmed finding record there is nothing for this skill to do: tell the user to fix it
   directly, without this workflow.
3. The approval in your brief (or the user's yes after seeing the plan) explicitly covers running
   the project's tests and making one local commit. Show the plan: test command, files you expect
   to touch, the commit. No approval, no edits.
4. Checkout clean (`git status --porcelain` empty). HEAD is the baseline for attempt 1, or the last
   earlier attempt's `patch_commit`. Anything else: stop and say what you found.

`run.attempts` equals your attempt number N; your directory is `<run>/patch/attempt-N/` and must
not exist yet. Earlier attempt directories are read-only history: read their proof failures, fix
what they found, never rewrite them.

## 1. Name the invariant and its boundary

Write down, for yourself: the invariant, the `repair_scope.boundary`, the `exclusions`. The threat
model in the guidance tells you what behaviour is intended; it does not limit where you look
inside the boundary, and it is not a reason to skip a case.

## 2. Hunt variants inside the boundary

Search the baseline code for every path that breaks the same invariant the same way: sibling
functions, other entry points into the same sink, the same helper copied elsewhere, error and
cleanup paths. Grep for the sink and for the pattern, not just the reported function name. Each
hit becomes a `variants` entry: `location` (`path:line`), `status` `fixed` or `not_fixed`, `reason`
(why it is the same violation, or why it stays: outside the boundary, an exclusion, a deliberate
behaviour). Bugs outside the boundary are not yours this time; list them as `not_fixed` only if
they break this invariant.

## 3. Suite before

Run the project's own test command in the checkout (e.g. `go test -v ./...`), saving the full
output to `<run>/patch/attempt-N/receipts/suite-before.txt`. Count passed, failed and skipped
tests from that file. Go: lines `--- PASS:`, `--- FAIL:`, `--- SKIP:`. Python: pytest's summary
line. Leave no stray files in the checkout (`-p no:cacheprovider` for pytest).

## 4. Regression test first

Write a test in the project's own style and test framework that encodes the invariant for the
reported input and for every variant you will fix (a table-driven test is fine), plus at least one
control that must keep working. Run it before touching production code and save the output to
`receipts/regression-test-baseline.txt`. It must fail, and fail for the bug, not for a compile
error in the test itself. A test that passes on the unpatched code proves nothing: rewrite it.
Never `git stash`, `git checkout -- <file>` or `git reset` to get back to the unpatched code: the
test comes first, so the code is still unpatched when it runs.

## 5. The fix

- At the level of the invariant: enforce the rule where every path in the boundary goes through it
  (the shared helper, the constructor, the single sink), not by filtering the one bad string.
- Smallest reviewable change; no refactors, renames, formatting sweeps or drive-by fixes.
- Keep the controls working: the legitimate inputs in `repair_scope` must behave as before.
- Follow the project's conventions from the guidance text.

## 6. Suite and test after

Rerun the regression test (now passing) and the full suite into `receipts/suite-after.txt`.
Compare failures before and after. A new failure is yours to fix. A failure that was already in
`suite-before.txt` stays, with the receipt as proof that it predates you.

## 7. One commit

```bash
git -C /abs/checkout add <each changed file>
git -C /abs/checkout commit -s -m "fix(<scope>): <what the invariant now guarantees>" -m "<body>"
```

- Exactly one commit per attempt. Conventional subject, a body with the invariant, the variants
  fixed and the test; follow the checkout's `CLAUDE.md` if it sets other rules.
- The `-s` trailer must match the committer identity. No AI attribution, no co-author lines.
- A signing or hook failure ends the attempt: record the error, `patch_commit` null. Never
  `--no-verify`, `--no-gpg-sign`, `-c commit.gpgsign=false`, `--amend` of an earlier attempt, or
  a second commit.
- Never push. Never open a PR.

## 8. Patch files and record

From the baseline, not from HEAD~1 (an attempt may sit on top of earlier ones):

- `git diff --no-ext-diff --no-textconv <baseline> <patch_commit> -- <production files>` into
  `patch/attempt-N/fix.patch`;
- `git diff --no-ext-diff --no-textconv <baseline> <patch_commit> -- <test files>` into
  `patch/attempt-N/tests.patch`;
- `git diff --no-ext-diff --no-textconv --numstat <baseline> <patch_commit>` for `files_changed`,
  `lines_added`, `lines_removed`.

Write `patch.json`: `attempt` N, `baseline_commit`, `patch_commit` (full SHA from
`git rev-parse HEAD`, or null), the counts, `variants`, `suite_before`, `suite_after` (`command` as
run, plus the counts), `agent`. Then:

```bash
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py manifest /abs/run/patch/attempt-N
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py check /abs/run
```

## Return

`patch.json` path, `patch_commit` (or "failed" with the error), variants fixed / not fixed, suite
before → after. Do not claim the fix is proven; proving is another agent's job.

## Limits

- Pre-approved commands only read, plus the record script. Forbidden flags: `--output` on
  `git log`, `git show` and `git diff`; `--ext-diff` and `--no-index` on `git diff`; `--textconv`
  on `git show`.
- Edits, test runs, staging and committing all prompt. No `git stash`, `git reset`, `git checkout`
  or `git restore` in the checkout.
- Change files only inside the checkout's repair boundary and the attempt directory. Never touch
  `reproduce/`, `validate/` or an earlier attempt.
- No push, no PR, no installs, no real infrastructure.
