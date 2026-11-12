---
name: reproduce-bug
description: Shows one reported bug is real on the current build before any edit — builds the pinned baseline in a scratch worktree with the project's own command, runs the built artifact through a PoC harness printing PATCH_LOADED, PATCH_CASE and PATCH_REACHED (or the exact compiler diagnostic), and stores its stdout, stderr and exit codes beside reproduce.json and a hash manifest under $TMPDIR. Use when a bug must be shown on the current build with raw output someone else can rerun, or for the reproduce stage of patching-bugs:patching-bugs. Not for whether a scanner alert is real — use fp-check:fp-check.
argument-hint: "<bug report or finding.json> [checkout] [run-dir]"
allowed-tools: Read Grep Glob Write Bash(git rev-parse:*) Bash(git status:*) Bash(git log:*) Bash(git show:*) Bash(printenv TMPDIR) Bash(mkdir -p:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/markers.py:*)
---

Request: $ARGUMENTS

# Reproduce one bug on the unchanged build

The question is narrow: does the built program, at the pinned commit, do the wrong thing the
report describes? Reading the code and agreeing with the report is not an answer. A unit test that
imitates the bug is not an answer either. Run the real artifact (or the real compiler) and keep
what it printed.

Scripts (shared by the plugin's skills): `${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/`. Record
fields: `${CLAUDE_SKILL_DIR}/../patching-bugs/references/records.md`. Stack recipes and the harness
contract: [recipes.md](references/recipes.md).

Write every path in commands literally and absolutely; never put the run directory, the scripts
or the checkout in a shell variable. The transcript is part of the evidence.

## Inputs

- From `patching-bugs:patching-bugs`: checkout, run directory, baseline commit, identity string,
  the user's approval quote, guidance text, `finding.json`. Use them as given.
- Used directly: the checkout is the current repo; baseline is `git rev-parse HEAD` (the tree must
  be clean: `git status --porcelain` empty). Run directory: `printenv TMPDIR` (empty: `/tmp`), then
  `<TMPDIR>/patching-bugs-<repo>-<short-sha>/`, `-2`, `-3`… if taken, never inside the checkout.
  Write `finding.json` yourself from the user's words (status `hypothesis`, a `repair_scope` with
  at least one representative and one control). Identity: `reproducer@<run-name>`.

Never edit the checkout. Write only inside the run directory.

## Gate

The harness and the build run the user's code. Show the plan first: build argv, artifact, harness
path, each planned input, and that everything runs in temporary worktrees beside the run directory.

- Brief from the coordinator with an approval quote that explicitly allows running the project's
  commands: show the plan in your output and go on.
- Otherwise: show the plan and stop until the user says yes. "Reproduce it" alone does not allow
  running code.

Absent build tools stay absent: never install anything. That is `blocked`.

## 1. Pick the recipe

From [recipes.md](references/recipes.md): failure type (`runtime` or `compile`), build argv,
artifact, how the harness loads it. A claim that needs real hosts, a state backend or a cluster is
`blocked`; provision nothing.

## 2. Write the PoC package

Under `<run>/reproduce/poc/`:

- the harness, following the contract in recipes.md: `{tree}` `{scratch}` and the input JSON as
  arguments; `PATCH_LOADED` for the exact file it runs; `PATCH_CASE`; `PATCH_REACHED` as the last
  line; exit non-zero exactly when the invariant is broken;
- `cases.json`: one `{check_id, argv}` per `repair_scope` case, representatives and controls,
  argv calling the harness with that case's input.

Compile claims need no harness: `cases.json` is `[]`.

## 3. Run on the baseline

```bash
GOCACHE=<TMPDIR>/gocache GOFLAGS=-buildvcs=false python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/arms.py cases \
  --repo /abs/checkout --baseline <sha> --build '<build argv JSON>' \
  --plan /abs/run/reproduce/poc/cases.json --artifact <relative artifact> --out /abs/run/reproduce
```

Drop `--artifact` for compile claims and the Go variables for other stacks. The command prompts;
that is intended. A setup failure (harness bug, wrong path) is not evidence: move
`reproduce/receipts/cases` to `reproduce/receipts/setup-failed/<n>/`, fix the harness, run again.
Never delete failed receipts.

## 4. Read the receipts yourself

For each representative and control, with the artifact path and hash from the command's JSON
output (`build.baseline.artifact`):

```bash
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/markers.py check-stdout /abs/run/reproduce/receipts/cases/<id>/baseline.stdout \
  --input '<planned input JSON>' --runtime-identity <artifact path> <sha256>
```

Then open the stdout and `.exit.json`. Outcome:

| What you see | outcome |
|---|---|
| markers valid, every representative exits non-zero with the wrong `actual`, controls exit 0 with the expected `actual` | `reproduced` |
| markers valid, the representative behaves correctly | `not_reproduced` |
| no `PATCH_REACHED`, crash before it, build failure, timeout, a control that fails | `blocked` (keep the real failure text) |
| compile: build fails and stderr holds the claimed diagnostic | `reproduced` |
| compile: build passes, or fails with an unrelated diagnostic | `not_reproduced` / `blocked` |

## 5. Record

Write `<run>/reproduce/reproduce.json` with the Write tool: `outcome`, `baseline_commit`,
`build_argv`, `poc_argv` (the first representative's argv, placeholders kept), `target_artifact`,
`observed` (what the receipts show, ≤400 chars), `blocker` (null unless blocked), `agent`,
`failure_type`, and for compile `expected_diagnostic` (the exact line), `poc_argv` `[]`,
`target_artifact` null.

Set `finding.json` `status` to `reproduced` or `not_reproduced`; leave `hypothesis` when blocked.

## 6. Seal and check

```bash
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py manifest /abs/run/reproduce
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py check /abs/run
```

Both exit 0, or you report the error text. Nothing may be added to `reproduce/` after the manifest.

## Return

`reproduce.json` path, the outcome word, the receipt paths of each case, and the blocker text if
any. No advice on how to fix.

## Limits

- Pre-approved commands only read, plus the record and marker scripts. Forbidden flags: `--output`
  on `git log` and `git show`; `--textconv` on `git show`.
- `arms.py`, `mv` and every build or test command prompt; that is the gate.
- Never edit, stash, reset or commit in the checkout. PoC source stays in `reproduce/poc/`.
- No installs, no network fetches beyond what the approved project build itself does, no real
  infrastructure.
