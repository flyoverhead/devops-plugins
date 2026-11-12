---
type: llm
---

Fixture facts for .github/workflows/ci.yml:
- line 4: the trigger is `pull_request_target`, and lines 11-13 check out `${{ github.event.pull_request.head.sha }}`, so fork code then runs (`pip install -e .`, `pytest`, lines 19-20) with the base repository's token and context;
- line 15: `${{ github.event.pull_request.title }}` is interpolated straight into a `run:` command (script injection);
- line 22: the third-party action `quillworks/pr-coverage-note@main` is pinned to a branch, not a full commit SHA;
- there is no `permissions:` block at workflow or job level, so the token gets the repository default.

PASS only if the final response does all of the following:
1. reports `pull_request_target` combined with checking out and running the PR head code, with a fix;
2. reports the PR title interpolated into `run:` as an injection risk, with a fix (for example pass it through `env:` and quote the shell variable);
3. reports the action pinned to `@main` (a mutable branch ref), with a fix (pin to a full commit SHA);
4. reports the missing `permissions:` block, with a fix (explicit least-privilege permissions);
5. gives `path:line` style locations for items 1-4 (line numbers within one or two of those above are fine); for item 4 that means `.github/workflows/ci.yml:<n>` pointing at the top of the workflow (lines 1-4), `jobs:` (line 7) or the `test` job (lines 8-9).

Extra findings (tag-pinned first-party actions, `github.token` handed to a third-party action, persisted checkout credentials) are fine. FAIL if any numbered item is missing, or if the response says it edited or created files in the repository.
