# patching-bugs

Takes one named bug in a local git repository and ends with a fix that is committed locally and
proven by someone other than its author, plus the evidence to recheck it. Four stages run in four
separate fresh agents: the reproducer, a validator that never sees the reproducer's transcript,
the patcher, and a prover. All records, receipts and SHA-256 manifests stay in a run directory under
`$TMPDIR`; the only change to your repository is one `git commit -s` per attempt. Nothing is pushed.

```text
/plugin install patching-bugs@devops
```

## Usage

```text
/patching-bugs:patching-bugs "SV-14: snipvault save ../../x writes outside SNIPVAULT_HOME"
/patching-bugs:patching-bugs "$(cat issue-212.md)" ~/src/ledger
```

The coordinator starts only by slash command. The stage skills also work on their own:
"reproduce this on the current build and keep the raw output", "rerun this PoC package blind",
"fix the confirmed finding at the invariant level", "prove this patch commit".

| Skill | Does | Writes |
|---|---|---|
| `patching-bugs` | look, approval gate, intake, dispatch, verdict, report | `run.json`, `finding.json`, `report.md` |
| `reproduce-bug` | builds the pinned baseline, runs the PoC harness | `reproduce/` |
| `validate-bug` | reruns the unchanged package, judges it | `validate/` |
| `implement-patch` | variants, failing-first regression test, fix, one commit | `patch/attempt-N/` and the commit |
| `prove-patch` | cases and checks on both trees, three-arm check | `prove/attempt-N/` |

Not this plugin: an ordinary fix with no proof wanted (just fix it); unknown bugs in a change
(`regression-hunt:regression-hunt`); is a scanner alert real (`fp-check:fp-check`); a fix that already
exists as a commit, PR or patch file (`post-patch-validation:post-patch-validation`); batches of
bugs, deployments, or claims only real infrastructure can show.

## Workflow

1. **Look.** Clean checkout, pinned baseline SHA, stack and build command, guidance files
   (`CLAUDE.md`, `AGENTS.md`, `PATCHING_GUIDELINES.md`, `THREAT_MODEL.md`) copied from the baseline
   commit's objects.
2. **Approval.** The plan (build, PoC, tests, the local commit) is always shown. Code runs only after
   a yes; an up-front yes counts only when it explicitly allows running the project's commands.
3. **Preflight build** of the baseline in a throwaway worktree.
4. **Intake.** One falsifiable claim, the invariant, and a `repair_scope`: a bounded class (two or
   more representatives and a control) or the exact example.
5. **Reproduce**, then **validate blind**. Stops at not reproduced, blocked, not confirmed or
   inconclusive.
6. **Patch and prove**, up to three attempts, each with a fresh patcher and a different fresh prover.
7. **Regression pass** with `regression-hunt` when it is installed; otherwise skipped and listed as a
   concern.
8. **Verdict and report**: `NOT_REPRODUCED`, `NOT_READY`, `READY_WITH_CONCERNS` or `READY`, decided
   by `verdict.py`, and `report.md` (plus `handoff.md` for the two READY verdicts).

## Evidence

A PoC or case harness drives the real built artifact and prints three marker lines:
`PATCH_LOADED {"path", "sha256"}` for the exact file it runs, `PATCH_CASE {"input", "actual"}`, and
`PATCH_REACHED` as its last line right before it decides its exit status. A crash before that line
is a missing observation, not a reproduction.

The three-arm check builds the baseline, the patch commit, and the patch commit reset to the
baseline tree, each in its own detached worktree. Proof needs the baseline to fail, the patch to
pass and the reverted tree to fail the same way, with every arm's `PATCH_LOADED` matching the bytes
it built.

## Scripts

`skills/patching-bugs/scripts/`, Python 3 standard library only.

| Command | Does | Pre-approved |
|---|---|---|
| `records.py check <run> [--before-repair]` | every record and manifest; with the flag, also the repair-scope plan and a free attempt | yes |
| `records.py manifest <step-dir>` | writes `manifest.json` | yes |
| `records.py guidance <run> --repo R --commit SHA` | copies or re-verifies guidance files, prints the hand-over text | yes |
| `markers.py loaded / case / reached / check-stdout` | prints or judges marker lines | yes |
| `verdict.py <run>` | verdict, reasons, claim breadth | yes |
| `arms.py cases` | planned runs on the baseline (and patched) tree | no, prompts |
| `arms.py run` | baseline / patched / reverted check | no, prompts |

`records.py` exits 0 when valid, 1 with the first problem on stderr, 2 on a usage error.

## Safety

- Run state, receipts, PoC source and reports live outside the repository under `$TMPDIR`.
- Reproduction, validation and proof never edit your checkout; the helper's worktrees live in a
  private temp directory outside the run directory and are removed afterwards, even on error. Only
  their own `.git/worktrees` entries are cleaned up; there is no global `git worktree prune`.
- One `git commit -s` per attempt, conventional message, no AI attribution. Signing or hook failures
  end the attempt; `--no-verify` and turning signing off are never used. No push, PR or issue.
- No installs, no network calls from the scripts, no `terraform plan/apply` against a backend,
  playbooks against hosts, cloud molecule scenarios or cluster commands.
- Build, test and helper commands are not pre-approved; each prompts.

## Tests

```bash
cd patching-bugs && tests/run-all.sh
```

Uses `python3` with `pytest` and `pyyaml` when both import; otherwise falls back to
`uv run --with pytest --with pyyaml`, which fetches them into the uv cache. The arms tests need
`git` and `sh`.

## Evals

```bash
claude plugin eval ./patching-bugs --trust-plugin --scaffold --no-publish \
  --allow-tools Write Edit Bash
```

| Case | Proves |
|---|---|
| `trigger-reproduce-first` | "show it on the current build, keep raw output for someone else" loads `reproduce-bug` |
| `negative-plain-fix` | "just fix the traversal and add a test" loads none of the five skills |
| `outcome-approval-gate` | "fix it and commit it" without a yes: the plan is shown and nothing is built, run or committed |
| `outcome-upfront-yes` | an explicit up-front yes still gets the plan shown before the first build, then the run goes ahead |
| `outcome-go-path-escape` | a Go `../` escape is reproduced, fixed with a failing-first test, proven on three arms, and committed once with `-s`, no hook or signing bypass, no push, records sealed under the temp root |
