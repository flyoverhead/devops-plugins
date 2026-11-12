# Review brief

What every review round hands the reviewer, and what it must hand back. Fill the placeholders;
send the whole brief each round, because an agent reviewer starts with no memory.

## Brief

```text
Review round <r> of an automated review-and-fix loop.

Target: <absolute target path>
Scope (repo-relative globs; only these files may be fixed): <scope list>
Repository root: <git root>
Baseline commit: <sha>   (`git diff --no-ext-diff --no-textconv <sha>` shows what the loop has changed so far)
Reviewer notes from the user: <notes or "none">
User decisions (binding): <decisions or "none">
Ledger so far: <path to ledger.json>, summary below
<one line per finding: id · severity · status · verdict_reason>

Rules for this review:
- Read only. Do not edit, create, format or auto-fix any file, even if your own method
  normally fixes cosmetic issues; report those as findings instead.
- Report every defect you see at every severity. Map your own scale onto
  critical / major / minor / info.
- When a defect is already in the ledger, reuse its id exactly, even if its line moved.
- For every ledger entry marked fixed, read the current code. List the ids whose fix you
  confirm in verified_fixed. If the defect is still there, report it again under its id.
- A finding the ledger shows as rejected: report it again only with new evidence that the
  rejection reason is wrong, and put that in new_evidence.
- If you cannot run at all, answer with one line starting REVIEWER-UNAVAILABLE: and the error,
  and report zero findings.

Answer with this record and nothing after it.
```

## Record

```json
{
  "mode": "direct",
  "findings": [
    {"id": "pkg/store.go:41:unchecked-error", "file": "pkg/store.go", "line": 41,
     "class": "unchecked-error", "severity": "major",
     "title": "Close error dropped after a write", "evidence": "defer f.Close() on a written file",
     "new_evidence": ""}
  ],
  "verified_fixed": ["pkg/store.go:12:file-mode"],
  "summary": "one paragraph",
  "agents": []
}
```

- `mode` and `agents` matter only for skill reviewers. `mode: "dispatch"` with an `agents` list of
  `{"agentType": "...", "prompt": "...", "label": "..."}` means the reviewer's own method wants
  specialist agents run before it can conclude.
- `id` may be empty for a new finding; the skill computes it (see ledger.md).

## Reading the answer

| Answer | Meaning |
|---|---|
| a record with findings or an empty `findings` list | a review; merge it |
| starts with `REVIEWER-UNAVAILABLE:` | halt `reviewer-unavailable`; quote the error |
| nothing, an error, or text with no record | halt `reviewer-failed` |
| prose findings without the record shape | rebuild the record from the prose once; if you cannot tell file, line and severity for each finding, halt `reviewer-failed` |

An empty review without the sentinel means clean. That is why a reviewer that fails must say so
with the sentinel: a silent empty answer would end the loop as converged.

## Specialist fan-out (skill reviewers)

When a skill reviewer answers `mode: "dispatch"`:

1. Dispatch the listed agents yourself, at most 8 in one wave, in parallel.
2. Hand each report back into the review: continue the reviewer skill's method with the reports
   and ask again for the record.
3. At most 3 waves. A fourth request, or a dispatch wave with an empty `agents` list, is
   `reviewer-failed`.
4. A specialist whose agent type does not exist halts the run like a missing reviewer
   (`reviewer-unavailable`, naming that agent). A specialist that ran and failed goes into the
   merge as a failed report with its error; it is never silently dropped.

Specialists get the same read-only rule as the reviewer.
