# Results, assessment and the final answer

## Contents

- [Run directory](#run-directory)
- [result.json](#resultjson)
- [Assessment rules](#assessment-rules)
- [artifact-manifest.json and report.md](#artifact-manifestjson-and-reportmd)
- [Reviewer records](#reviewer-records)
- [Final answer](#final-answer)

## Run directory

```text
$RUN/
  plan.json
  checks/                      helper scripts
  results/
    result.json                schema 2.0
    report.md
    artifact-manifest.json
    patch.diff                 the exact change that was tested
    plan.snapshot.json         the plan bytes that ran
    helpers/<sha256>           archived argv files
    scratch/<check-id>-<side>/ what each invocation left in its scratch
    NNN-<check-id>-<side>.stdout|.stderr
```

Log numbers follow execution order. Nothing in `results/` is ever overwritten; the runner
refuses a non-empty output directory.

## result.json

| Key | Content |
|---|---|
| `schema_version` | `"2.0"` |
| `case_id`, `finding` | from the plan |
| `inputs` | `base_commit`, `patched_commit` (null in patch mode), `patch_sha256`, `changed_files`, `evidence_level`, `submodules` (`{path: {base_commit, patched_commit}}`), `plan_sha256`, `forwarded_env` |
| `coverage` | count per kind, all seven present |
| `checks[]` | `id`, `kind`, `rationale`, `covers`, `runs.base` / `runs.patched`, `comparison` (behavior only, both runs completed) |
| `cleanup_errors` | strings |
| `assessment` | `status` (`complete`/`incomplete`), `findings[]` (`check_id`, `kind`, `message`), `gaps[]` (`check_id` or null, `reason`), `human_review_required: true` |

A run record: `side`, `argv` (as planned, before placeholders), `argv0_sha256`, `argv_files[]`
(`index`, `argument`, `sha256`, `artifact`, `archive_reason`), `cwd`, `scratch`, `status`
(`completed`/`timeout`/`execution_error`), `exit_code`, `expected` (`zero`/`nonzero`),
`matched`, `marker` (exploit/variant only, else null), `stdout`, `stderr`, their SHA-256s, and
`error`. A run that never started has null outputs.

`suite` checks always have a patched run; the base run exists only after a completed patched
failure.

## Assessment rules

Per check, first rule that applies:

1. A required run missing or not `completed` → gap.
2. exploit/variant without a bare `PPV_REACHED` stdout line on either side → `marker_missing` gap.
3. exploit/variant that passes on base → gap "no reproduction".
4. Any other kind failing on base → gap "unattributable" (suite: only when base also fails
   after a patched failure; both logs kept).
5. control failing on patched → gap.
6. behavior without a comparison → gap.
7. Patched run not as expected, or behavior streams differ → finding, with a fixed message for
   the kind.

Run-wide:

- A failed or missing `control` withholds every finding: each becomes a gap, raw runs stay in
  the file.
- A kind with no check → gap with `check_id: null`.
- Submodule population and cleanup failures → run-level gaps. Findings survive them.
- Any gap makes the status `incomplete` (exit 10), findings or not.

## artifact-manifest.json and report.md

The manifest is `{"schema_version": "1.0", "files": [{path, sha256, bytes}]}` over every file in
`results/` except itself. Reviewers recompute hashes against it.

`report.md` has four sections: Findings, Validation gaps, Evidence (finding, level, commits,
patch and plan hashes, submodules, forwarded env, and a per-check base/patched/comparison
table), Next steps. With no findings and no gaps it says that all supplied checks passed at the
stated evidence level and that human review is still required.

## Reviewer records

Both agents return plain text blocks:

```text
Lens: coverage-completeness | evidence-integrity
Approved: yes | no
Concerns:
- <check id or path:function> — <what is wrong>
Evidence read:
- <every artifact path opened>
```

An empty `Evidence read` list cannot approve; treat it as `Approved: no`. Concerns never merge
into runner findings or gaps; they are listed under their own heading.

## Final answer

```text
Status: NEEDS_REPAIR | BLOCKED | REVIEW_REQUIRED | READY_FOR_HUMAN_REVIEW
Evidence level: runtime

Findings
- variant-nested-dotdot (variant): <what the check asserts>; still fails on patched.
  Log: $RUN/results/012-variant-nested-dotdot-patched.stdout

Gaps
- none | <check id or "run">: <reason>

Reviewer concerns
- none | skipped because a finding already requires repair | <lens>: <concern>

Files
- $RUN/results/result.json
- $RUN/results/report.md

A person still has to review this change before merge.
```

Explain each finding in one or two sentences of plain language: which input still gets through
and why the patch misses it (for example "the strip runs once, so `....//` collapses back into
`../`"). Do not call a fix complete; at best, all supplied checks passed.
