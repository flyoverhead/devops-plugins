# regression-hunt

Answers one question about a change: did it break something that was correct and supported
before, and can that be shown on real builds of both sides?

A change is a GitHub PR, a commit or a commit range. The coordinator pins the state before the
change (S0) and after it (S1), then hands each stage to its own fresh agent:

```
prepare → hunt → per candidate: reproduce → replay → adjudicate → report
```

Reproduction, replay and adjudication of a candidate are always three different agents. Only a
candidate whose S0 build behaves correctly and whose S1 build fails, with the same PoC and input
in both the reproduction and an independent replay, and with incomplete-fix, latent-bug,
pre-existing-bug, intentional-change and unsupported-expectation explanations ruled out, is
reported as `REPRODUCED_REGRESSION`. Everything else is an exclusion or `UNRESOLVED`.

## Skills

| Skill | Role |
|---|---|
| `regression-hunt` | coordinator: inputs, plan and approval, campaign directory, dispatch, acceptance, reply |
| `prepare-regression` | S0/S1 boundary, frozen PR or commit context, exports, security-doc search |
| `hunt-regressions` | traces the diff to real interfaces, writes candidate files; no PoCs |
| `reproduce-regression` | builds S0 and S1 copies, runs one PoC against both |
| `replay-regression` | independent rebuild and run of the unchanged PoC |
| `adjudicate-regression` | outcome, ratings and nine cited checks |
| `report-regressions` | `index.html`, `report.md`, `report.json` |

## Inputs

- A PR URL or number: read with `gh pr view --comments` and `gh pr diff`. Review threads need a
  `gh api` GET that you approve at the time; `gh api` is never pre-approved.
- No `gh`, not logged in, or a remote that is not GitHub: the coordinator says so once and works
  from a commit range (`base..head`) or a single commit (its parent is S0).
- Optional: a campaign directory (outside the repository), CPU, memory or time limits, or an
  existing campaign to resume.

## Safety

- The plan is always shown first. Project code runs only after a yes that explicitly allows it.
- Nothing is pushed, commented, approved or opened on GitHub. Nothing is installed.
- Builds happen in copies inside the campaign's attempt directories; the target checkout is never
  modified and no worktree is created.
- Everything runs on this machine. Cloud, clusters, Terraform backends and Ansible hosts are out of
  scope; candidates that need them stay `UNRESOLVED`.
- A brief's `Approval:` line carries only the user's own words; agents never widen an
  authorisation, and a harness or classifier denial is reported as a blocker.
- Snapshots refuse trees that would not export faithfully (submodules, LFS, export attributes,
  case or Unicode path collisions, paths below symlinks, escaping symlinks).
- Records are SHA-256 sealed and an append-only registry ties each one to its launched agent. A
  seal proves the evidence did not change, not that a conclusion is right: reports are agent
  conclusions pending human review.

## Campaign directory

Default `$TMPDIR/regression-hunt-<repo>-<short-sha>/` (`/tmp` when `TMPDIR` is unset): `scope.json`,
`registry.json`, `campaign.json`, `progress.md`, `guidance/`, `runtime/`, `attempts/aNNN/`. Record
formats: `skills/regression-hunt/references/records.md`.

## Scripts

Python 3 standard library only, in `skills/regression-hunt/scripts/`: `registry.py`, `evidence.py`,
`snapshot.py`, `report.py`, `runtime.py`, `guidance.py`. This version produces the `shared-host`
verification level only.

## Tests and evals

```bash
tests/run-all.sh
claude plugin eval ./regression-hunt --trust-plugin --scaffold --no-publish --allow-tools Write Edit Bash
```

`outcome-go-auth-regression` is a remote-less Go CLI whose second commit drops an empty-key check;
the campaign must confirm the regression from runs of both builds, using the commit range.
