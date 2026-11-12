---
name: validate-bug
description: Repeats a reproduce-bug package as a second, independent observer — same pinned baseline and recorded build argv in a fresh worktree, the unchanged PoC on the same inputs, only the files and never the reproducer's transcript — and records confirmed, not_confirmed or inconclusive in validate.json with its own receipts and manifest. Use when a reproduction should be repeated from its files alone before code changes, or for the validate stage of patching-bugs:patching-bugs. Not for mending a PoC that fails to run or for changing code — use patching-bugs:implement-patch.
argument-hint: "<run-dir> [checkout]"
allowed-tools: Read Grep Glob Write Bash(git rev-parse:*) Bash(git status:*) Bash(git log:*) Bash(git show:*) Bash(printenv TMPDIR) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py:*) Bash(python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/markers.py:*)
---

Request: $ARGUMENTS

# Validate a reproduction, blind

You are the second witness. Someone built a PoC and says the bug is real; you have their files,
not their story. Repeat exactly what the files say, look at what comes out, and decide whether it
shows the claim in `finding.json`. You may conclude that it does not.

Scripts: `${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/`. Record fields:
`${CLAUDE_SKILL_DIR}/../patching-bugs/references/records.md`. Harness contract:
`${CLAUDE_SKILL_DIR}/../reproduce-bug/references/recipes.md`.

Write every path in commands literally and absolutely; never put the run directory, the scripts
or the checkout in a shell variable. The transcript is part of the evidence.

## What you read, and what you do not

Read: `finding.json`, `reproduce/reproduce.json`, everything under `reproduce/poc/` and
`reproduce/receipts/`, the guidance text in your brief, and the code at the baseline commit
(`git show --no-ext-diff --no-textconv <sha>:<path>`).

Do not read or ask for: the reproducer's conversation, notes or summary. If your brief contains
one, ignore it and say so in your return.

Never edit the PoC, `cases.json`, `finding.json` or anything under `reproduce/`. Never edit the
checkout. Write only `validate/`.

## Gate

Same rule as reproduction: run the build and the PoC only with an approval quote in the brief that
explicitly allows running the project's commands, or a yes from the user after seeing the plan.
Show the plan (build argv, PoC, inputs) either way. Install nothing.

## 1. Check the package first

```bash
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py check /abs/run
```

Exit 1 (a changed or extra file in `reproduce/`, a malformed record) → `inconclusive` with that
error as the reason. Also confirm the baseline commit exists: `git rev-parse --verify <sha>^{commit}`.

## 2. Rerun it unchanged

Same build argv, same plan file, same artifact, your own output directory:

```bash
GOCACHE=<TMPDIR>/gocache GOFLAGS=-buildvcs=false \
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/arms.py cases \
  --repo /abs/checkout --baseline <baseline_commit> --build '<build_argv as JSON>' \
  --plan /abs/run/reproduce/poc/cases.json --artifact <target_artifact> --out /abs/run/validate
```

Compile claims: no `--artifact`; the evidence is `validate/receipts/cases/_build/baseline.stderr`.

## 3. Judge

For each case, run `markers.py check-stdout` on your own stdout with `--input` (the planned input)
and `--runtime-identity` (your build's artifact path and hash from the command output). Then read
the stdout and `.exit.json` yourself and ask:

1. Did the PoC exercise the built artifact (identity line valid), not a copy of the code?
2. Does the representative's `actual` show the exact claim, and does it break the stated
   `invariant`, not merely something nearby?
3. Do the controls pass, so the harness is not failing on everything?
4. Compile: is the claimed diagnostic present, verbatim, in the failing build's output?

| Answer | outcome |
|---|---|
| all yes | `confirmed` |
| the observation is trustworthy and the claim does not hold | `not_confirmed` |
| PoC broken, markers invalid, timeout, crash before `PATCH_REACHED`, build failure, a package check error, ambiguous output | `inconclusive` |

A broken PoC is `inconclusive` with the reason. Do not fix it, rewrite it or try a variant of
your own: that would turn you into a second reproducer.

## 4. Record and seal

Write `<run>/validate/validate.json`: `outcome`, `agent` (your identity string), `reason` (≤400
chars, citing receipt paths). Then:

```bash
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py manifest /abs/run/validate
python3 ${CLAUDE_SKILL_DIR}/../patching-bugs/scripts/records.py check /abs/run
```

## Return

`validate.json` path, the outcome word, your receipt paths, and the reason. The coordinator, not
you, updates `finding.json`.

## Limits

- Pre-approved commands only read, plus the record and marker scripts. Forbidden flags: `--output`
  on `git log` and `git show`; `--textconv` on `git show`.
- `arms.py` prompts; that is the gate.
- No edits outside `validate/`, no installs, no real infrastructure.
