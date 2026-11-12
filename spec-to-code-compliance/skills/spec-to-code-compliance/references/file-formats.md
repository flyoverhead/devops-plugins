# File formats

Two files: one analysis file per checked requirement (written by the checker agent) and one
`REPORT.md` (written by the orchestrator). Both live in
`<TMPDIR>/spec-compliance-<repo>-<short-sha>/`.

## Writing conventions

- Code cites as `file:L45` or `file:L89-L135`; document claims are quoted verbatim.
- Go deep only where the code earns it; a one-line getter needs one line.
- An empty section says it is empty ("No enforcement found anywhere.") instead of vanishing.
- No minimum counts of anything.
- A hedge word becomes either a cited claim or an open question.
- Ending with open questions written down counts as finished.
- Secret values are `<redacted>`.

## Analysis file: `requirements/<id>.md`

Sections in this order, separated by `---`:

```markdown
# REQ-04 — backups encrypted before upload

> "Backups are encrypted before they leave the host."
> — docs/design.md:42, section *Backups*

Verdict: partial · Confidence: medium

---

## What an implementation must do
<the bound, quantity or condition, with where each number comes from>

---

## Where enforcement lives
<path:L-range — what it checks — which routes, tasks or jobs reach it>

---

## Paths walked
- <path or role or input value> — pass | fail — <path:line>

---

## Searched
- `<pattern or symbol>` -> <files> -> <result, irrelevant hits included>

---

## How the verdict was reached
<why this verdict and not the neighbouring one; for absent, why the searches are exhaustive>

---

## Open questions
<what could not be established, and what would settle it>
```

## REPORT.md

```markdown
# Spec-to-code compliance: <repo> @ <short-sha>

Documents read: <list with paths>
Requirements: <n extracted>, <n checked>, limit <n>

## Findings
| Severity | Id | Verdict | Requirement (quoted) | Evidence | Fix belongs in |
|---|---|---|---|---|---|
<one row per surviving divergence, most severe first; Fix belongs in = code | document>

### <id> — <short name>
<quote with location; what fails, on which path, path:line; consequence only where shown;
the refuters' corrections applied; link to requirements/<id>.md>

## Held
<id — quote — the enforcing path:line>

## Document problems
<vague requirements (undecidable), two documents contradicting each other, a doc endorsing a bug>

## Undocumented behaviour
<reachable routes, flags, variables, inputs no document mentions, with consequence; or "None found.">

## Refuted
<id — what the checker claimed — which lens refuted it and why, with evidence>

## Unverified
<id — why both refuters failed, or the checker could not support its record>

## Not checked
<id — quote — reason: past the limit, outside the named sections, outside the path subset>

## Unreadable documents
<path — reason; or "None.">

## Open questions
<one line each: side issues outside the requirement at hand, and settings not in the repository>
```
