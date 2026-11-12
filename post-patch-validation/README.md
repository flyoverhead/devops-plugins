# post-patch-validation

Checks a security fix that already exists by executing it. The unpatched and the patched
revision each get their own scratch git worktree; the same checks run on both; a small runner
decides from exit codes, a reach marker and byte comparisons. The answer is one of four
statuses, findings with log paths, gaps listed separately, and the evidence level. It never
says "safe to merge".

```text
/plugin install post-patch-validation@devops
```

## Usage

```text
/post-patch-validation:post-patch-validation "SEC-88: ../ in upload name escapes the root" v2.3.0 4c1e9a7
/post-patch-validation:post-patch-validation SEC-88 main fix.patch
/post-patch-validation:post-patch-validation SEC-88 41            # GitHub PR, needs gh
```

Or in plain words: "check the fix in PR 41 holds before I merge it", "validate this patch",
"did the last commit miss a variant?". The skill runs project code, so it needs your consent;
for a read-only look at a diff use `differential-review:differential-review` instead.

## Workflow

1. **Inputs.** A finding (id and root cause) and the change: fix commit, branch pair, patch
   file, or a GitHub PR read with `gh pr view` / `gh pr diff` once
   `git remote get-url origin` shows GitHub. Any other host, or a `gh` that does not work,
   gets one message asking for a commit range, branch pair or patch file.
2. **Pin.** `scaffold` records the base and patched commits (or the patch hash), the changed
   files and submodules in `plan.json` under
   a run directory in `$TMPDIR` named after the plugin, the repo and the short fix sha.
3. **Coverage.** Four lenses: root cause and variants, unchanged behaviour, adjacent security,
   harness. A multi-function patch fans out to four `coverage-mapper` agents.
4. **Plan.** At least one check of each kind (`control`, `exploit`, `variant`, `behavior`,
   `regression`, `security`, `suite`); `validate-plan` until it passes.
5. **Approval.** The plan is always shown before `run`. A yes given up front counts only when
   the request explicitly authorises running the project's commands or checks; otherwise
   nothing runs until you say yes.
6. **Run.** Base and patched in random order under random names; exploit and variant checks
   cannot learn their side and must print `PPV_REACHED` before asserting.
7. **Review.** Two `evidence-reviewer` agents (coverage completeness, evidence integrity),
   skippable only when a finding already demands repair.
8. **Report.** `NEEDS_REPAIR`, `BLOCKED`, `REVIEW_REQUIRED` or `READY_FOR_HUMAN_REVIEW`.

## Runner

`skills/post-patch-validation/scripts/post_patch_validation.py`, Python 3.11+ standard library
and git 2.36+.

| Command | Does | Pre-approved |
|---|---|---|
| `scaffold` | pins both sides, writes a plan with empty `checks` | yes |
| `validate-plan` | schema, kinds, argv rules, pins | yes |
| `print-schema` | plan JSON Schema | yes |
| `run` | executes the checks, writes `results/` | no, always prompts |

`run` exits 0 (complete, nothing found), 1 (complete, findings), 10 (incomplete) or 64
(invalid input, nothing ran).

Safety properties:

- output only under `$TMPDIR` or a directory you name outside the repository; evidence is
  never overwritten;
- files in your worktree are never edited. The runner adds its own worktrees to the
  repository's `.git` and removes them afterwards; checks share that `.git` (objects, refs,
  config). Runner git calls have hooks and Git LFS smudge filters disabled;
- argv arrays only, shell strings refused;
- fixed minimal environment; extra variables only through `--allow-env NAME`, credential-like
  and loader-hijack names refused, forwarded values recorded;
- moved refs, a changed patch or a different changed-file set stop the run before anything
  executes;
- runner worktrees carry an owner tag; the next run removes only tagged leftovers of a dead
  runner process on this host that sit in a runner directory under the temp root, and never
  prunes other worktrees;
- submodules come from local objects only, never from `.gitmodules` URLs;
- the isolation protects the evidence, not your machine: checks run as you, so run an untrusted
  patch inside a container.

## Not covered

Anything that needs real infrastructure: `terraform plan/apply` against a backend, playbooks
against hosts, cloud molecule scenarios, `kubectl`/`helm` on a cluster. For Terraform, Ansible
and GitHub Actions changes the skill offers source or build evidence and states the gap.

## Tests

```bash
cd post-patch-validation && tests/run-all.sh
```

Uses `python3` with `pytest` and `pyyaml` when both import; otherwise falls back to
`uv run --with pytest --with pyyaml`, which fetches them into the uv cache.

## Evals

```bash
claude plugin eval ./post-patch-validation --trust-plugin --scaffold --no-publish \
  --allow-tools Write Edit Bash
```

| Case | Proves |
|---|---|
| `trigger-validate-pr-fix` | "check the PR fix holds before merge" loads the skill |
| `outcome-go-missed-variant` | a one-shot replace in a Go log sanitizer is reported incomplete with a variant finding in `result.json` |
| `negative-read-only-review` | "just look at the diff, run nothing" does not load it |
| `fallback-non-github-remote` | a PR on a non-GitHub remote ends in one request for a range, branch pair or patch file |
