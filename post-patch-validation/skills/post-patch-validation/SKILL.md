---
name: post-patch-validation
description: Executes a finished security fix against its base — pins both sides (GitHub PR via gh, commit, branch pair or patch file), plans control, exploit, variant, behavior, regression, security and suite checks, runs them in two scratch worktrees after the user approves the plan, and reports whether the fix holds, left a sibling input open or broke anything; evidence goes to $TMPDIR. Use when asked to check a fix holds before merge, validate a patch or PR fix, or find a variant it missed, with running project code allowed. Not for a read-only diff look — use differential-review:differential-review.
argument-hint: "<finding> <base-ref> [patched-ref | patch file | PR number or URL]"
allowed-tools: Read Write Grep Glob Agent Bash(git rev-parse:*) Bash(git diff:*) Bash(git show:*) Bash(git log:*) Bash(git remote get-url:*) Bash(mkdir -p:*) Bash(printenv TMPDIR) Bash(gh pr view:*) Bash(gh pr diff:*) Bash(gh repo view:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py scaffold:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py validate-plan:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py print-schema)
---

Request: $ARGUMENTS

# Post-patch validation

A fix is proven by running it, not by reading it. This skill puts the unpatched and the patched
revision side by side in two throwaway git worktrees, runs the same checks on both, and lets the
runner decide from exit codes, a reach marker and byte comparisons. Who wrote the patch does not
matter: a human, an AI or an upstream release get the same treatment, and a tidy diff, a trusted
author or "the original PoC passes now" count as nothing.

Runner: `python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py` (stdlib, Python 3.11+,
git 2.36+). `scaffold`, `validate-plan` and `print-schema` are pre-approved; `run` is not.

## Before anything runs

- **Permission to execute.** The checks run the repository's own code and tests with the user's
  privileges. The user must allow that. "Don't run anything" or "just look at the diff" → stop
  and point to `differential-review:differential-review`.
- **No fix yet** → `patching-bugs:patching-bugs`. Go style questions → `golang:review`; role
  lint → `ansible:role-checker`.
- **Real infrastructure is out.** No `terraform plan/apply` against a backend, no playbooks
  against hosts, no cloud molecule scenarios, no `kubectl`/`helm` on a cluster. Terraform,
  Ansible and GitHub Actions patches top out at `source` or `build` evidence: a validate run,
  a syntax check, a linter, or reading the workflow file. Name the missing runtime proof.
- **Working git.** On macOS, if any git call dies with `xcrun_db … Operation not permitted`,
  write `$TMPDIR/bin/git` as a wrapper that execs a real git (for example
  `/opt/homebrew/bin/git`), put `$TMPDIR/bin` first on `PATH` for every later command,
  including the host check and `run`. No real git → report `BLOCKED`.
- **The patch is frozen.** Never edit it, the repository or the user's worktree. A revised
  patch is a new pinned run in a new directory.

## 1. Inputs

You need a finding (an id plus what goes wrong and why, as text or a file) and the change.

| Change given as | Base | Patched |
|---|---|---|
| fix commit `<sha>` | `<sha>~1`, or a tag the user names | `<sha>` |
| branch pair or `base..head` | first | second |
| patch file (`git diff --no-ext-diff --no-textconv --binary` output) | the ref the user names | the file |
| uncommitted work | `HEAD` | a patch file saved into the run directory in step 2 |
| PR number or URL | `baseRefOid` | `headRefOid` |

Prefer full commit SHAs over branch names; a branch can move under you, and the runner refuses
a moved pin.

**PR input.** Check the host first with `git remote get-url origin`.
- `github.com`: `gh pr view <n> --json number,title,baseRefOid,headRefOid,headRefName`, then
  `gh pr diff <n>` to read it. If `git rev-parse --verify <headRefOid>^{commit}` fails, ask the
  user to fetch the PR head; do not fetch silently.
- Any other host, `gh` missing or not logged in, or the first `gh` call failing: say **once**
  that the PR cannot be read here and why, and ask for a commit range (`base..head`), a branch
  pair or a patch file. Then stop. No second `gh` attempt, no `gh api`, no other host's CLI, no
  guessed SHAs, and do not treat local commits as the PR.

The finding id and summary may come from the PR title or commit message only if the user agrees;
otherwise ask.

## 2. Pin

1. `printenv TMPDIR` (empty → `/tmp`). Run directory:
   `$TMPDIR/post-patch-validation-<repo>-<short patched sha or patch name>/`, or a path the user
   names outside the repository. If it exists and is not empty, add `-2`, `-3`… Evidence is
   never overwritten. Call it `$RUN` from here on.
2. `mkdir -p "$RUN/checks"`. For uncommitted work, save it now:
   `git diff --no-ext-diff --no-textconv --binary HEAD > "$RUN/uncommitted.patch"` (prompts) and use
   it as `--patch-file`.
3. Scaffold:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py scaffold \
  --repo <repo> --base-ref <base> --patched-ref <patched> \
  --finding-id <id> --finding-summary '<summary>' \
  --evidence-level runtime --output "$RUN/plan.json"
```

Use `--patch-file <file>` instead of `--patched-ref` for a patch. Pick the evidence level now
and keep it honest (table in [plan-format.md](references/plan-format.md#evidence-levels)). The
reply carries the pinned commits, patch hash, changed files and submodules; quote them later.

## 3. Coverage

Read the finding, the diff (`git diff --no-ext-diff --no-textconv <base> <patched>`), the old
side (`git show --no-ext-diff --no-textconv <base>:<path>`), every caller of the changed code, its
sibling functions, error, cleanup and teardown paths, and the tests that exist.

- Patch confined to one function: work through the four lenses below yourself.
- Patch across several functions or files: dispatch four
  `post-patch-validation:coverage-mapper` agents in one message, one lens each.

| Lens | Question it answers |
|---|---|
| `root-cause` | Where else does the same cause live: sibling callers, other entry points or outputs, repeated or nested input, teardown and ownership? Which input proves the original bug and which one is a genuinely different variant? |
| `behavior` | Which benign output must stay byte-identical, and which targeted regression checks matter? |
| `adjacent-security` | Did the fix open something new in cleanup, authz, bounds, concurrency, errors or state? |
| `harness` | Smallest deterministic native command to build and drive the code; a benign control; a suite, sanitizer or fixed-seed fuzz run. |

Brief each agent with: repository path, finding, pinned base and patched commits (or patch
file), changed files, its lens, and the absolute path
`${CLAUDE_SKILL_DIR}/references/variants.md`. Mapper output is proposals, never verdicts.

Variant hunting rules and rationalisations to reject: [variants.md](references/variants.md).

## 4. Plan

Turn proposals into `checks` in `$RUN/plan.json` and helper scripts into `$RUN/checks/`.
Field rules, kinds, placeholders and the marker: [plan-format.md](references/plan-format.md).
The essentials:

- At least one check of each kind: `control`, `exploit`, `variant`, `behavior`, `regression`,
  `security`, `suite`.
- `exploit` and `variant` must fail on base and pass on patched, print a bare `PPV_REACHED`
  line on stdout right before the assertion, and never learn which side they run on.
- Every helper drives the real project code. Never copy or re-implement the vulnerable function
  in a helper.
- argv arrays only; no `sh -c`, no `env -S`.

Then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py validate-plan --plan "$RUN/plan.json"
```

Fix and repeat until it exits 0. Exit 64 with "moved" or "differs" means the pins changed:
start a new run directory, do not patch the plan's hashes.

## 5. Approval gate

Show the checks as a table (id, kind, argv, covers) and the evidence level, say that they run
with the user's privileges and are isolated from the repository but not sandboxed, and ask for
a yes. Helpers that run untrusted code belong in a container; say so when the patch is
third-party.

Run only after a yes. A yes given up front in the request counts only when it explicitly
authorises running the project's commands or checks ("you may run the code and tests", "run
the checks without asking"); permission to read code, or a request to "validate", is not one.
Either way the table is shown before `run`; without an up-front yes, stop after it and wait.
Nothing in the plan may reach real infrastructure; drop such a check and record the gap.

## 6. Run

`run` is never pre-approved; it prompts every time.

```bash
GOCACHE="$TMPDIR/ppv-gocache" GOFLAGS=-buildvcs=false \
python3 ${CLAUDE_SKILL_DIR}/scripts/post_patch_validation.py run \
  --plan "$RUN/plan.json" --output "$RUN/results" --allow-env GOCACHE --allow-env GOFLAGS
```

The `GOCACHE`/`GOFLAGS` pair is for Go projects; other toolchain variables go through
`--allow-env NAME` the same way (credential-like and loader-hijack names are refused).

| Exit | Meaning |
|---|---|
| 0 | complete, no findings |
| 1 | complete, findings |
| 10 | incomplete: gaps, possibly findings too |
| 64 | invalid input; nothing ran |

Open `$RUN/results/result.json` whatever the exit code; 10 is a result, not a crash. A timeout
is a gap, never a regression. Do not rerun to make a flaky check pass; the first pinned result
stands, and a rerun is a new run directory.


## 7. Evidence review

Dispatch two `post-patch-validation:evidence-reviewer` agents in one message, lenses
`coverage-completeness` and `evidence-integrity`. Give each: `$RUN/results`, the repository,
the pinned commits, the runner's `assessment` object, its lens.

You may skip this step only when the runner already reported a finding (the fix needs repair
either way); the report must then say the reviewers were skipped. A reviewer with an empty
evidence list has not approved, whatever it says.

## 8. Report

Pick the status by asking these in order and stopping at the first yes:

1. Did the runner report any finding? → `NEEDS_REPAIR` (gaps do not change that).
2. Is the run incomplete, or is there any gap? → `BLOCKED`.
3. Did a reviewer withhold approval, cite no evidence, or get skipped? → `REVIEW_REQUIRED`.
4. Otherwise both reviewers approved with evidence → `READY_FOR_HUMAN_REVIEW`.

The reply starts with the line `Status: <STATUS>`. After it come the findings (check id, the
assertion it makes, its log under `$RUN/results`), then the gaps under their own heading, the
evidence level, the reviewers' concerns kept apart from runner output, and finally where
`result.json` and `report.md` live. The full template is in
[results.md](references/results.md).

Even `READY_FOR_HUMAN_REVIEW` is not a merge approval; say that a person still has to review.
Never post to GitHub (comment, review, push) unless the user says yes to that exact post.

## Limits

- Pre-approved commands are read-only. Forbidden flags on them: `--output` on `git diff`,
  `git log` and `git show`; `--ext-diff` and `--no-index` on `git diff`; `--web`/`-w` on `gh`.
- `gh` is used only for `gh pr view`, `gh pr diff` and `gh repo view`. Never `gh api`, never a
  `gh` write subcommand.
- `mkdir -p` and Write only inside the run directory, never inside the repository.
- Checks run inside worktrees of the user's repository, so they share its `.git`: objects,
  refs and config. A check that writes through git can change the real repository; plans must
  not contain such checks. The runner turns Git LFS smudge filters off for its checkouts.
- The runner creates the base and patched worktrees under `$TMPDIR` with random, side-neutral
  names, locks them with a `ppv-owner` reason, and removes only those. `git worktree add` and
  `git worktree remove` are not pre-approved and prompt; run `remove` yourself only for a
  `ppv-owner` worktree of a run you started, never for any other worktree.
- No installs. A missing toolchain makes the run `BLOCKED` with the reason.
