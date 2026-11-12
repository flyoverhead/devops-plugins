# Output template

Write the hunt's results to `$TMPDIR/variants-<repo>-<short-sha>.md`, sections in this order.
Quote only code you read at the stated location, copied exactly; never paraphrase code.
Secrets appear as `<redacted>` with their `path:line`.

## Contents

- [1. Summary](#1-summary)
- [2. Original bug](#2-original-bug)
- [3. How the search ran](#3-how-the-search-ran)
- [4. Variants](#4-variants)
- [5. Ruled out](#5-ruled-out)
- [6. Worth a manual check](#6-worth-a-manual-check)
- [7. Recommendations](#7-recommendations)
- [8. Regression guard](#8-regression-guard)

## 1. Summary

| Field | Value |
|---|---|
| Original bug | `<path:line>`, one-line description |
| Date | ISO date of the hunt |
| Codebase | repo name, short sha, extra checkouts or GitHub owner searched |
| Variants | N confirmed (by severity), M ruled out, K for manual check |

## 2. Original bug

- Root cause: the one-line statement ("untrusted X reaches dangerous Y without Z", or the
  broken invariant).
- Location: `path:line`.
- Code:

```text
<the lines as read, with line numbers>
```

## 3. How the search ran

Axes, one line each. Then one row per pattern version, failed ones included:

| Version | Pattern | Tool | Matches | TP | FP |
|---|---|---|---|---|---|
| v1 | … | ripgrep | 1 | 1 | 0 |
| v2 | … | semgrep | 3 | 2 | 1 |

Tool is `ripgrep` or `semgrep`. Add a line when sweepers ran, or when the local-checkout
fallback replaced `gh search code`.

## 4. Variants

One block per confirmed variant, most severe first:

```markdown
### V1: <short title>

- Severity: info | low | medium | high | critical
- Confidence: low | medium | high
- Status: confirmed
- Location: `path:line`

    <quoted code>

Analysis: where the value comes from, the path to the sink, which protection is missing
and what an attacker gets.

- [x] Reachable: <entry point>
- [x] Attacker-controlled: <source>
- [x] Unprotected: <what was looked for and not found>
```

An unchecked box needs a reason next to it (for example "no caller today").

## 5. Ruled out

Grouped by reason, with counts and locations:

| Reason | Count | Locations |
|---|---|---|
| argv form, no shell | 1 | `internal/x.go:12` |

A candidate dismissed because a specific, different protection is present gets a one-line
note naming that protection; its status is `false positive`.

## 6. Worth a manual check

| Location | Open question | Command a human would run |
|---|---|---|

## 7. Recommendations

1. Immediate fixes, one per variant, in severity order.
2. Preventive: the shared helper, wrapper or lint rule that removes the class.

## 8. Regression guard

The best-yielding pattern turned into a check that runs on every change:

- languages Semgrep parses: a complete rule file, `ruleid`/`ok` examples taken from the
  findings, and where to wire it (the repo's own Semgrep config, a pre-commit hook, a CI job);
- Bash, Jinja2, CI YAML: an `rg` expression with the exit-code convention
  (`! rg -n '<expr>' <paths>` fails the job when it matches) and the same wiring options.
