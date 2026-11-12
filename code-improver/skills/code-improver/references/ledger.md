# Findings ledger

## Contents

- [Files in the out directory](#files-in-the-out-directory)
- [ledger.json](#ledgerjson)
- [Finding identity and matching](#finding-identity-and-matching)
- [Merging a review](#merging-a-review)
- [Merging fixer verdicts](#merging-fixer-verdicts)
- [Escalation triggers](#escalation-triggers)
- [Result record](#result-record)
- [ledger.md and status.md](#ledgermd-and-statusmd)
- [Continuing a run](#continuing-a-run)

The ledger is the loop's memory. Every review and every fixer dispatch reads it; it is written to
disk before each of them, so an interrupted run loses one round at most. Write it with the Write
tool as pretty-printed JSON.

## Files in the out directory

| File | Written by | When |
|---|---|---|
| `baseline.json` | `scope_guard.py init` | once per baseline |
| `ledger.json`, `ledger.md` | the skill | before every review and fixer dispatch, and at the end |
| `status.md` | the skill | at every stop |
| `fixes-round-N.diff` | the skill, with `scope_guard.py snapshot` | after fix round N (cumulative against the baseline) |
| `pre-finalize.diff`, `post-finalize.diff` | `scope_guard.py snapshot` | around the finalize pass |

## ledger.json

```json
{
  "version": 1,
  "target": "/abs/path/pkg",
  "reviewer": {"kind": "skill", "name": "golang:review"},
  "scope": ["pkg/**"],
  "baseline": {"sha": "<40 hex>", "git_root": "/abs/path"},
  "decisions": ["<user ruling, verbatim>"],
  "prior_rounds": [],
  "rounds": [],
  "findings": {},
  "finalize": null,
  "result": null
}
```

A finding, keyed by its id:

| Field | Type | Notes |
|---|---|---|
| `id` | str | see identity below |
| `coarse` | str | `<file>::<class>` |
| `file`, `line`, `class` | str, int, str | as first reported |
| `severity` | str | `critical`, `major`, `minor` or `info` |
| `title` | str | at most ~200 characters |
| `evidence` | str | at most ~400 characters |
| `status` | str | `open`, `fixed`, `rejected` or `deferred` |
| `verdict_reason` | str | the fixer's reason; it is the ledger's memory of why |
| `verified` | bool | a reviewer read the current code and confirmed the fix |
| `first_round`, `last_round` | int | rounds this finding was reported in |
| `rounds_seen` | [int] | every review round that reported it |
| `fixed_rounds` | [int] | every fix round that marked it fixed |
| `seen_prior`, `fixed_prior` | [int] | archived copies of the two lists above (continued runs) |
| `refiled_after_verdict` | int | re-reports of a rejected finding without new evidence |
| `structural` | bool | optional; set on a structural rejection |
| `pin` | str | optional; the test or assertion that holds a behaviour fix |
| `notes` | [str] | short events: "fix did not hold", "reopened with new evidence" |

Round entries, appended in order:

- review: `{"round": r, "type": "review", "open": {"critical": n, "major": n, "minor": n, "info": n}, "new": n, "reopened": n, "refiled_rejected": n}`
- fix: `{"round": r, "type": "fix", "verdicts": {"fixed": n, "rejected": n, "deferred": n}, "unaddressed": [id], "failed": bool, "diff_file": "fixes-round-r.diff"}` (`diff_file` names the snapshot the skill wrote)

`finalize`, once the pass ran: `{"narration_sites_removed": n, "version": "x.y.z", "notes": "..."}`.

## Finding identity and matching

- id: `<file>:<line>:<class>`. Drop a leading `./` from the file. Lowercase the class and fold
  every run of characters outside `[a-z0-9]` into one `-`. Example: `./store/disk.go`, line 12,
  class `Unchecked Error` → `store/disk.go:12:unchecked-error`.
- coarse key: `<file>::<class>`, same normalisation.

A reported finding matches an existing entry by the first rule that applies:

1. the reviewer echoed an existing id;
2. its recomputed id exists;
3. its coarse key matches exactly one entry, and no other report in this same review already
   matched that entry. Two findings of one class in one file stay two findings.

No match: it is new.

## Merging a review

| Situation | Result |
|---|---|
| new finding | stored `open`, `verified: false`, `first_round = last_round = r`, `rounds_seen = [r]` |
| id in `verified_fixed[]` and status `fixed` | `verified: true` |
| re-reported, status `open` | `last_round = r`, append `r` to `rounds_seen` |
| re-reported, status `fixed` | back to `open`, `verified: false`, `last_round = r`, append `r` to `rounds_seen`, note "fix did not hold" |
| re-reported, status `rejected`, no `new_evidence` | verdict stands, `refiled_after_verdict += 1` |
| re-reported, status `rejected`, with `new_evidence` | back to `open`, note "reopened with new evidence" |
| re-reported, status `deferred`, now critical or major | back to `open` |
| re-reported, status `deferred`, still minor or info | stays `deferred` |

Every re-report also refreshes `line`, `severity`, `title` and `evidence` from the newest review.
Blocking means critical or major. Minor and info are recorded and reported, never sent to the
fixer.

## Merging fixer verdicts

| Verdict | Effect |
|---|---|
| `fixed` | status `fixed`, `verified: false`, append the round to `fixed_rounds`, store `pin` |
| `rejected` | status `rejected`, store `verdict_reason`; store `structural: true` when given |
| `deferred` on minor or info | status `deferred` |
| `deferred` on critical or major | stays `open` and keeps blocking |
| no verdict for a dispatched id | stays `open`; listed in the round's `unaddressed` |

A rejection whose reason starts `requires out-of-scope change:` is a normal rejection; relay the
path to the user in the notes so they can widen the scope.

If the fixer died or returned nothing usable, record the fix round with `failed: true` and every
dispatched id in `unaddressed`. Do not dispatch a second blind fix; the next review is the judge.

## Escalation triggers

Check after each review merge and after each verdict merge. Any one stops the run:

| Type | Fires when |
|---|---|
| `counts-non-decreasing` | over the last three review rounds the open blocking count never went down, and the first of the three was above 0 |
| `recurrence` | one blocking finding is in `rounds_seen` for three consecutive review rounds |
| `structural-rejection` | the fixer rejected a blocking finding with `structural: true` |
| `relocation` | one finding has two or more distinct rounds in `fixed_rounds` |

Only the current run's `rounds_seen` and `fixed_rounds` count; the archived `seen_prior` and
`fixed_prior` never trigger anything.

The escalation record is `{"type": "...", "round": r, "finding_ids": [...], "message": "..."}`.
`finding_ids` names the findings that tripped it; when none does by itself
(`counts-non-decreasing`), it names every open blocking finding. The message always says three
things: this is a structural problem the loop cannot settle, it needs the user's decision, and how
to resume (the same `target` and `reviewer`, plus `"decision": "<ruling>"`).

## Result record

```json
{
  "converged": false, "capped": false, "halted": "",
  "escalation": null, "violations": [], "finalize_regressions": [],
  "rounds_run": 0, "fix_rounds": 0, "fixer_failed_rounds": [],
  "open_blocking": [{"id": "...", "severity": "major", "title": "..."}],
  "open_minor_count": 0, "new_untracked_files": [],
  "ledger_path": "<out>/ledger.json", "out_dir": "<out>", "notes": []
}
```

`halted` is empty or one of `reviewer-unavailable`, `reviewer-failed`, `scope-violation`,
`scope-check-failed`, `untracked-files-in-scope`, `finalize-regression`, `finalize-check-failed`.
`finalize_regressions` entries are `{"file": "...", "line": n, "why": "..."}`.

## ledger.md and status.md

`ledger.md` is for people: a table with one row per finding (id, severity, status, reason) and
below it one line per round (`round 2 · review · 1 major open, 0 new` or
`round 2 · fix · 1 fixed, 0 rejected, 0 deferred`).

`status.md` says, in this order: the ending (converged, capped, escalated or halted, with the
reason), the open blocking findings, the out directory, and the exact way to resume or what the
user has to do first.

## Continuing a run

When `out/ledger.json` exists at the start:

- it does not parse, or its `target` differs: note it, move it aside as `ledger.prev.json`
  (Write a copy, then overwrite), and start a fresh ledger;
- it parses: keep `findings`, `decisions` and the verdicts. Move `rounds` into `prior_rounds`.
  For every finding, append `rounds_seen` to `seen_prior` and `fixed_rounds` to `fixed_prior`,
  then empty both. Round numbering starts again at 1. Append the new `decision`, verbatim, to
  `decisions`, and clear `result`.

Every entry in `decisions` binds later reviews and fixes: pass them on in every brief.
