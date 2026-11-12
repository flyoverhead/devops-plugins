# Output format

The review file is one Markdown document at `$TMPDIR/diff-review-<repo>-<short-head-sha>.md`
(`/tmp` when `TMPDIR` is unset). `<repo>` is the basename of `git rev-parse --show-toplevel`;
`<short-head-sha>` is `git rev-parse --short <head>`. For a patch file there is no head commit:
use the patch's basename without its extension (`fix-auth.patch` gives
`diff-review-<repo>-fix-auth.md`). It never goes inside the repository.

Nine sections, in this order. Keep every heading, even when a section only says "none".

## Contents

- 1. Summary
- 2. What changed
- 3. Findings
- 4. Test coverage
- 5. Blast radius
- 6. History
- 7. Recommendations
- 8. Method and limits
- 9. Commits
- Chat summary

## 1. Summary

```markdown
## Summary

| CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|
| 1 | 0 | 1 | 2 |

Recommendation: REJECT
Overall risk: CRITICAL; the PR removes the CA pin added by a security fix.
Coverage: 3 of 3 changed files read, 2 removals blamed, callers counted in this repo only.
```

## 2. What changed

Range (`base..head` with shas), PR number if any, commit count, then one row per file:

```markdown
| File | + | − | Risk | Blast radius |
|---|---|---|---|---|
| internal/auth/session.go | 12 | 30 | HIGH | 14 (MEDIUM) |
| docs/session.md | 4 | 1 | LOW | — |
```

## 3. Findings

CRITICAL first, then HIGH, MEDIUM, LOW. CRITICAL and HIGH use the full finding template from
[attack-modeling.md](attack-modeling.md#finding-template). MEDIUM and LOW may be one line:

```markdown
- MEDIUM: `api/export.go:88` — export size limit raised from 10 MB to 2 GB; one request can fill the disk.
```

Old-side lines carry their commit: `session.go:41 @ 7c1e0aa`.

## 4. Test coverage

Changed source files against changed tests, which changed functions have no test, and the tier
bumps applied because of that.

## 5. Blast radius

Per changed function, module, role, input or workflow: the count, the band, the command used.
Cross-repository numbers are "at least N" with the owner or checkouts searched.

## 6. History

Every removed security line with the commit that added it (sha, date, subject), and every
re-added line with the commit that had removed it. Regressions are named as such:

```markdown
- `internal/auth/session.go:41` (removed) came from `7c1e0aa` "fix(security): expire sessions on password change".
- Regression: `InsecureSkipVerify` returns; `b20f9e1` "fix(security): pin the store CA" had removed it.
```

## 7. Recommendations

Three lists: blocking (must change before merge), before production, follow-ups.

## 8. Method and limits

Depth used (DEEP, FOCUSED, SURGICAL) and why, what was read, which commands, and what was not
analysed: dependencies, generated code, other repositories, runtime configuration not in the
repo.

## 9. Commits

`git log --oneline <range>` output.

## Chat summary

After writing the file, reply with:

```text
Saved: /var/folders/xy/abc123/T/diff-review-payments-4f9c2d1.md
Findings: 1 CRITICAL, 0 HIGH, 1 MEDIUM, 2 LOW
Recommendation: REJECT (confidence HIGH)
[CRITICAL] internal/auth/session.go:41 — sessions survive a password change again
[MEDIUM] api/export.go:88 — one export request can fill the disk
Not analysed: vendored modules and the two services that import this package
```

If the file could not be written, say so on the first line and put the whole review in chat.
