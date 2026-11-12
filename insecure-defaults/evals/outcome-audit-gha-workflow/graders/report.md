---
type: llm
---

The fixture has two workflows.
- .github/workflows/pr-checks.yml is unsafe: it triggers on pull_request_target (line 4), checks out the PR head commit (lines 11-13) and then runs npm ci and npm test on it with a secret in scope, has no permissions: block anywhere, interpolates ${{ github.event.pull_request.title }} straight into a run: command (line 15), uses a third-party action pinned to a tag rather than a commit SHA (snyk/actions/node@v0.4.0, line 19), and sets continue-on-error: true on that scan step (line 20).
- .github/workflows/release.yml is safe: push to main only, permissions: contents: read, actions pinned to full commit SHAs.

PASS only if the final response does all of the following:
1. reports pull_request_target combined with checking out and running the PR head code;
2. reports the missing permissions: block;
3. reports the PR title interpolated into run: as a script-injection risk;
4. reports the tag-pinned third-party action;
5. gives pr-checks.yml locations as file:line (line numbers within one or two of those above are fine);
6. reports no finding against release.yml (listing it as checked, safe or refuted is fine).

continue-on-error on the scan step is expected but not required. FAIL if any numbered item is missing, or if release.yml gets a finding.
