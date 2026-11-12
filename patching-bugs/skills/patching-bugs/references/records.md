# Run directory and record fields

## Contents

- Layout
- Common rules
- finding.json
- run.json
- reproduce/reproduce.json
- validate/validate.json
- patch/attempt-N/patch.json
- prove/attempt-N/prove.json
- regression/regression.json
- report-input.json
- manifest.json
- Files the arms helper writes
- Marker lines

`records.py check <run>` enforces all of this. When this page and the script disagree, the script
wins; report the difference.

## Layout

```text
<run>/
  plan.md  run.json  finding.json  report-input.json  report.md  [handoff.md]
  guidance/<baseline-sha>/      copies + source.md, outside every manifest
  preflight/                    build-only receipts, outside every manifest
  reproduce/   reproduce.json  poc/  receipts/  manifest.json
  validate/    validate.json   receipts/  manifest.json
  patch/attempt-N/   patch.json  fix.patch  tests.patch  receipts/  manifest.json
  prove/attempt-N/   prove.json  receipts/  manifest.json
  regression/  regression.json  receipts/  manifest.json
```

`N` is 1, 2 or 3 and must equal the record's `attempt`. Nothing else may sit under `patch/` or
`prove/`.

## Common rules

- Every record has `schema_version`: integer 1, except `prove.json`, which has 2.
- Unknown fields are rejected. Strings are non-empty unless a range below says `0..`.
- Commit ids: 40 lowercase hex. Hashes: 64 lowercase hex.
- Written as indented JSON with a trailing newline. Use the Write tool.

## finding.json

| Field | Type |
|---|---|
| `title` | string 1..120 |
| `claim` | string 1..400 |
| `affected_code` | list of `{path` 1..400, `start_line` int ≥0, `end_line` int ≥0`}` |
| `invariant` | string 1..300 |
| `poc` | string or null |
| `source` | string 1..200 |
| `status` | `hypothesis` · `reproduced` · `not_reproduced` · `confirmed` · `not_confirmed` |
| `reported` (optional) | object; optional strings `impact`, `expected_behavior`, `observed_behavior`, `severity`, `priority`; optional `reproduction_steps` list of strings |
| `repair_scope` (optional, required before any repair) | see below |

`repair_scope` has all four of:

- `mode`: `bounded_class` or `exact_example`;
- `boundary`: string 1..400, the behaviour the class covers;
- `cases`: list of `{check_id, role (representative|control), input (any JSON), expected (any JSON), why (1..300)}`;
- `exclusions`: list of strings 1..300, may be empty.

Plan gaps (the before-repair gate and the proof both refuse them): no representative; a
`bounded_class` with fewer than two representatives or no control; a repeated `check_id`; a
`bounded_class` repeating an input (compared as canonical JSON).

## run.json

`finding_id` 1..400; `status` `in_progress` · `not_reproduced` · `not_ready` ·
`ready_with_concerns` · `ready`; `attempts` 0..3; `steps` with exactly `intake`, `reproduce`,
`validate`, `patch`, `prove`, `regression`, `report`, each `pending` · `done` · `failed` · `skipped`.

## reproduce/reproduce.json

| Field | Type |
|---|---|
| `outcome` | `reproduced` · `not_reproduced` · `blocked` |
| `baseline_commit` | commit id |
| `build_argv`, `poc_argv` | lists of strings 1..400 |
| `target_artifact` | string 1..400 or null |
| `observed` | string 1..400 |
| `blocker` | string or null |
| `agent` | string 1..100 |
| `failure_type` (optional, always set it) | `runtime` · `compile`; absent means runtime |
| `expected_diagnostic` (optional) | string 1..400 |

Runtime needs a `target_artifact`. Compile needs a non-blank `expected_diagnostic`, a null
artifact, an empty `poc_argv` and a non-empty `build_argv`.

## validate/validate.json

`outcome` `confirmed` · `not_confirmed` · `inconclusive`; `agent` 1..100; `reason` 1..400.

## patch/attempt-N/patch.json

`attempt` 1..3; `baseline_commit`; `patch_commit` commit id or null; `files_changed`,
`lines_added`, `lines_removed` ints ≥0; `variants` list of `{location 1..400, status fixed|not_fixed,
reason 1..200}`; `suite_before` and `suite_after` each `{command 1..400, passed, failed, skipped}`
(ints ≥0); `agent` 1..100.

## prove/attempt-N/prove.json

| Field | Type |
|---|---|
| `attempt` | 1..3 |
| `failure_type` | `runtime` · `compile` |
| `baseline_commit`, `patch_commit` | commit ids |
| `reverted` | `pass` · `fail` · `inconclusive` |
| `build_identity` | `pass` · `fail` · `not_applicable` |
| `hashes` | `{baseline, patched, reverted}`, each sha256 or null, all three keys present |
| `reverted_hash_note` | string or null |
| `cases` | list, below |
| `project_checks` | list, below |
| `unproven` | list of strings 1..400 |
| `agent` | 1..100 |

- case: `check_id` 1..100, unique, one of the scope's ids; `argv` list of strings 1..400; `source`
  1..400, the `receipts/...` path of the harness; `runs` `{baseline: RUN, patched: RUN}`.
- project check: `check_id` 1..100, unique; `kind` `suite` · `behavior` · `regression` ·
  `security`; `argv` list of strings; `baseline` RUN or null; `patched` RUN.
- RUN: `exit_code` int or null (null: did not finish); `elapsed_ms` int ≥0; `stdout`, `stderr`
  paths 1..400.

Paths are relative to the attempt directory, start with `receipts/`, contain no `..`, and are listed
in the manifest. Runtime: `build_identity` is never `not_applicable`; `pass` needs three hashes with
baseline ≠ patched. Compile: `not_applicable` and three nulls.

## regression/regression.json

`campaign_dir` 1..400; `coverage` `COMPLETE` · `INCOMPLETE`; `outcomes` list of
`{candidate_id 1..400, outcome, decision_receipt 1..400}` with outcome one of
`REPRODUCED_REGRESSION`, `INCOMPLETE_FIX`, `LATENT_BUG`, `PREEXISTING_BUG`, `REJECTED`, `UNRESOLVED`.

## report-input.json

`bug` 1..600; `fix_why` 0..400; `open_risks` up to 5 strings 1..200; `include_poc` boolean.
Optional `baseline_checks` (up to 30): `{check_id 1..100, reproduce: {stdout, exit},
validate: {stdout, exit}}`, each path ≤400 inside that step's `receipts/`, the `exit` one a
`.exit.json` holding `exit_code`. Optional `run_metadata`: `date` (YYYY-MM-DD), `elapsed_seconds`,
`model` (≤100), `reasoning_effort` (≤60), `recorded_tokens`, `run_type` (≤80), all optional.

## manifest.json

`{"schema_version": 1, "files": {"<relative posix path>": "<sha256>"}}`, nothing else. Every
regular file of the step directory except the manifest, sorted. Symlinks are refused. Write it with
`records.py manifest` after the step's last file, never by hand, and never rewrite one to hide a
change.

## Files the arms helper writes

- `arms.py cases`: `receipts/<label>/<check_id>/<side>.stdout`, `.stderr`, `.exit.json`
  (`{"exit_code", "elapsed_ms"}`), build receipts under `receipts/<label>/_build/`, and
  `receipts/<label>/launch.json` with the exact command, commits and tree ids. Its JSON output
  carries ready-made RUN objects.
- `arms.py run`: `receipts/source.json` (`baseline_commit`, `patch_commit`, `trees` with
  `baseline`, `patched`, `reverted` tree ids), and per arm `receipts/<arm>/arm.json` (`name`,
  `commit`, `build_exit`, `diagnostic_matched`, `artifact_sha256`, `loaded_identity`, `reached`,
  `exit_code`) beside `build/` and `poc/` holding `stdout.txt`, `stderr.txt`, `exit.json`
  (`{"exit_code", "elapsed_s"}`). It writes an interim manifest; rewrite it after adding files.

## Marker lines

On a PoC or case harness's stdout:

- `PATCH_LOADED {"path": "<absolute resolved file>", "sha256": "<hex>"}`: once, runtime only, for
  the very file the harness then executes or imports;
- `PATCH_CASE {"input": <json>, "actual": <json>}`: once per run;
- `PATCH_REACHED`: alone, the last stdout line, printed right before the harness decides its exit.

`markers.py loaded|case|reached` prints them; `markers.py check-stdout <file> [--input <json>]
[--runtime-identity <path> <sha256>]` judges a captured stdout.
