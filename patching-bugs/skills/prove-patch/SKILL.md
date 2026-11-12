---
name: prove-patch
description: Judges a new local fix commit without trusting its author — every repair_scope case through one retained side-blind harness on clean baseline and patched worktrees, the project checks that matter on both, then the three-arm check (baseline fails, patch passes, patch reset to baseline fails again) — writing prove.json, receipts and a hash manifest under $TMPDIR. Use when patching-bugs:patching-bugs hands over a commit to prove, or the user wants proof that one local fix commit changes the outcome. Not for a merged fix, a PR or a patch file — use post-patch-validation:post-patch-validation.
argument-hint: "<run-dir> <attempt 1-3> [checkout]"
allowed-tools: Read Grep Glob Write Bash(git rev-parse:*) Bash(git status:*) Bash(git log:*) Bash(git show:*) Bash(git diff:*) Bash(printenv TMPDIR) Bash(mkdir -p:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/markers.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/verdict.py:*)
---

Request: $ARGUMENTS

# Prove one patch commit

The patcher believes the fix works. That belief is not evidence. You decide from runs you launch
yourself on pinned trees, with expectations fixed before you see any output. A missing or
ambiguous observation is a gap, and a gap is never written down as a pass.

Scripts: `${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/`. Record fields:
`${CLAUDE_SKILL_DIR}/../patching-bugs/references/records.md`. Judging rules:
[judging.md](references/judging.md). Harness contract:
`${CLAUDE_SKILL_DIR}/../reproduce-bug/references/recipes.md`.

Write every path in commands literally and absolutely; never put the run directory, the scripts
or the checkout in a shell variable. The transcript is part of the evidence.

## Inputs and gate

From the brief: checkout, run directory, attempt N, baseline commit, `patch_commit`, identity
string, approval quote, guidance. Your directory is `<run>/prove/attempt-N/`; it must be new.

- `patch/attempt-N/patch.json` names the same commits; `git rev-parse --verify <sha>^{commit}` both.
- An uncommitted tree is never proven: if the commit is missing, stop.
- Run code only under an approval that explicitly covers running the project's commands, or the
  user's yes after seeing the plan. Show the plan either way: cases, checks, three-arm command.
- Never edit the patch, the checkout or any other stage's files. A failure goes back as a finding
  for a new attempt; it is not yours to repair.

## 1. Look afresh

Read `finding.json` (`invariant`, `repair_scope`),
`git diff --no-ext-diff --no-textconv <baseline> <patch_commit>`, and the PoC package under
`reproduce/poc/`. Ignore what the patcher concluded. Ask: does the diff restore the invariant at its
source, or only reject the reported string? Which inputs would tell those apart? They belong in
`unproven` if no planned case covers them.

## 2. One retained harness

Copy the reproduce harness into `prove/attempt-N/receipts/harness/` (or write a new one there under
the same contract when it cannot express a planned case). Every case runs through that one file,
one command shape, on both trees. It stays side-blind: no commit ids, branch names or paths in its
decisions.

Write `prove/attempt-N/cases.json`: one `{check_id, argv}` per `repair_scope` case (all of them,
representatives and controls), argv calling the retained harness with the planned input.

## 3. Cases on both trees

```bash
GOCACHE=<TMPDIR>/gocache GOFLAGS=-buildvcs=false \
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/arms.py cases \
  --repo /abs/checkout --baseline <baseline> --patch <patch_commit> --build '<build argv JSON>' \
  --plan /abs/run/prove/attempt-N/cases.json --artifact <artifact> --out /abs/run/prove/attempt-N
```

The JSON it prints holds a RUN object per side for each case, ready for `prove.json`.

## 4. Project checks

Write `prove/attempt-N/checks.json` with the checks that matter for this change: the full suite
(`go test ./...`), focused packages, a `behavior` check whose output must stay byte-identical (a
control input printed by the real artifact), security tests if the project has them. Run them on
both trees with `--label checks` and the same command shape as step 3. Each becomes a
`project_checks` entry with its `kind`.

## 5. Three arms

```bash
GOCACHE=<TMPDIR>/gocache GOFLAGS=-buildvcs=false \
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/arms.py run \
  --repo /abs/checkout --baseline <reproduce.baseline_commit> --patch <patch_commit> \
  --build '<build argv JSON>' --poc '<reproduce.poc_argv JSON>' --artifact <artifact> \
  --out /abs/run/prove/attempt-N
```

Compile claims: `--failure-type compile --expected-diagnostic '<text>'`, no `--poc` or
`--artifact`. Needed: `reverted` `pass` (baseline fails, patched passes, reverted fails the same
way), `build_identity` `pass` for runtime. Its output gives `reverted`, `build_identity`, `hashes`
and `reverted_hash_note` for `prove.json`; `receipts/source.json` pins the commits and trees.

## 6. Check that it really ran

Receipts alone cannot show what was launched. Confirm yourself:

- `receipts/cases/launch.json` and `receipts/checks/launch.json`: the argv is the one you ran, the
  commits are the pinned baseline and patch, the plan names your retained harness;
- `receipts/source.json`: commits match, `reverted` tree equals `baseline` tree, `patched` differs;
- for each case and side, `markers.py check-stdout <stdout> --input '<planned>' --runtime-identity
  <that side's artifact path> <sha256>` (from the `build` part of the step 3 output);
- open a few raw stdout and stderr files and read them.

## 7. Record, seal, judge

Write `prove/attempt-N/prove.json` (`schema_version` 2): `attempt`, `failure_type` (same as the
reproduction), both commits, the three-arm fields, `cases` (each with `source` =
`receipts/harness/<file>`), `project_checks`, `unproven` (concrete limits you did not prove; never
empty), `agent`. Then:

```bash
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py manifest /abs/run/prove/attempt-N
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py check /abs/run
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/verdict.py /abs/run
```

The manifest replaces the helper's interim one and must cover every receipt. Read the `gap:` and
`finding:` lines of the verdict output; [judging.md](references/judging.md) explains each.

## Return

`prove.json` path, the three-arm result, build identity, every case and check that is not a pass
(with its receipt path and the reason), and `unproven`. Exact failures, no reassurance.

## Limits

- Pre-approved commands only read, plus the record, marker and verdict scripts. Forbidden flags:
  `--output` on `git log`, `git show` and `git diff`; `--ext-diff` and `--no-index` on `git diff`;
  `--textconv` on `git show`.
- `arms.py`, `cp` and every build or test command prompt; that is the gate.
- Worktrees belong to the helper, which removes them; never `git worktree` by hand.
- No edits to the checkout or the patch, no push, no installs, no real infrastructure.
