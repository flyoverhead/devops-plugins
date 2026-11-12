# plan.json

`print-schema` prints the authoritative JSON Schema; this page explains intent. The scaffold
fills everything except `checks`.

## Contents

- [Top-level fields](#top-level-fields)
- [Evidence levels](#evidence-levels)
- [Check fields](#check-fields)
- [What each kind must show](#what-each-kind-must-show)
- [The reach marker](#the-reach-marker)
- [Side-blind checks](#side-blind-checks)
- [Placeholders and environment](#placeholders-and-environment)
- [Helpers](#helpers)
- [A worked check set](#a-worked-check-set)

## Top-level fields

| Field | Meaning |
|---|---|
| `schema_version` | `"1.0"` |
| `case_id` | `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; derived from the finding id unless `--case-id` |
| `evidence_level` | `source`, `build` or `runtime` |
| `finding` | `{id, summary}` |
| `repository` | repository path relative to the plan file |
| `base_ref`, `expected_base_commit` | the base pin |
| `patched_ref` + `expected_patched_commit` | ref mode; or instead |
| `patch_file` | patch mode, path relative to the plan file |
| `expected_patch_sha256` | hash of the patch (in ref mode, of the runner's own `git diff --no-ext-diff --no-textconv --binary`) |
| `changed_files` | sorted, unique, non-empty |
| `submodules` | sorted gitlink paths on either side, `[]` when none |
| `checks` | sorted by `id`, ids unique |

Unknown keys fail validation. Never edit the pins by hand: when a pin no longer matches,
scaffold a new run.

## Evidence levels

| Level | Honest when |
|---|---|
| `source` | only the patch and source invariants were checked (greps, parsers, static assertions) |
| `build` | the code was compiled or analysed (`go vet`, `terraform validate`, `ansible-lint`) but the reported behaviour never executed |
| `runtime` | the reported behaviour itself was executed on both revisions |

Choose the highest level that is true. Passing source checks never implies runtime behaviour.

## Check fields

| Field | Rule |
|---|---|
| `id` | same pattern as `case_id`; also orders execution (lexical) |
| `kind` | one of the seven below |
| `rationale` | a falsifiable statement: "with two line breaks in the actor, the patched writer still emits two lines" |
| `covers` | non-empty: functions, files, entry points or paths this check exercises |
| `argv` | non-empty argv array |
| `cwd` | relative to the checkout, default `"."`; may not leave it |
| `env` | extra string variables; `PPV_*` and loader-hijack names refused |
| `timeout_seconds` | 1–3600, default 300 |
| `compare_stream` | `stdout`, `stderr` or `combined` (stdout then stderr); `behavior` only, required there |

Rejected argv: a shell with `-c` (or `-ec`, `--command`…), `env -S`/`--split-string`, or a first
element containing whitespace. Put logic in a helper script instead.

## What each kind must show

| Kind | Base | Patched | Notes |
|---|---|---|---|
| `control` | 0 | 0 | benign input through the changed component; proves the harness works |
| `exploit` | nonzero | 0 | the original safety assertion |
| `variant` | nonzero | 0 | a different root-cause path, same assertion style |
| `behavior` | 0 | 0 | chosen stream byte-identical on both sides |
| `regression` | 0 | 0 | targeted non-security behaviour |
| `security` | 0 | 0 | a weakness next to the fix or added by it; base must pass for blame to land on the patch |
| `suite` | only after a patched failure | 0 | project suite, sanitizer build or fixed-seed fuzz |

How the runner turns these into findings and gaps: [results.md](results.md#assessment-rules).

Keep exploit and variant assertions on the security invariant only (one line in, one line out;
no bytes past the buffer; caller denied). Error wording, timing and compatibility belong in
`behavior` or `regression`.

Make behaviour output deterministic inside the harness: fixed seeds, sorted maps, no clock, no
addresses, no temp paths. Do not post-process output to hide differences.

## The reach marker

`exploit` and `variant` helpers print `PPV_REACHED` (also in `$PPV_REACHED_MARKER`) on stdout,
alone on its line, flushed, immediately before the assertion, on both revisions. No marker →
`marker_missing` gap, whatever the exit code. stderr is ignored for this.

A nonzero exit without the marker might be a compile error, an import error or a missing file;
it proves nothing. The marker only proves the harness got to the assertion. Whether the
assertion itself is right stays a human question, which is why helpers are archived.

## Side-blind checks

`exploit` and `variant` checks may not mention `{side}` or `PPV_SIDE` anywhere in argv, env or
cwd; validation rejects it. The runner checks both revisions out under random names, runs the
two sides in random order, and gives each invocation a private random scratch and plan copy, so
the helper cannot tell where it is. Do not work around this (e.g. reading `git log` to decide
what to assert).

## Placeholders and environment

| Placeholder | Environment | Value |
|---|---|---|
| `{checkout}` | `PPV_CHECKOUT` | this side's worktree |
| `{plan_dir}` | `PPV_PLAN_DIR` | a private copy of the plan directory (plan file, patch and earlier results left out) |
| `{scratch}` | `PPV_SCRATCH` | an empty private directory, archived afterwards |
| `{side}` | `PPV_SIDE` | `base` or `patched`; not for exploit/variant |
| | `PPV_CASE_ID` | the plan's `case_id` |
| | `PPV_REACHED_MARKER` | `PPV_REACHED` |

`TMPDIR`, `TEMP` and `TMP` point at the scratch directory. Everything else is fixed: `PATH`,
`HOME`, `USER`/`LOGNAME`, `LANG=C`, `LC_ALL=C`, `TZ=UTC`, `PYTHONHASHSEED=0`, `NO_COLOR=1`,
`TERM=dumb`. More variables only through `run --allow-env NAME`; the value is recorded in
`result.json`, an unset name fails the run, and names that look like credentials or can hijack
code loading (`LD_PRELOAD`, `DYLD_*`, `NODE_OPTIONS`, `GIT_*`, `BASH_ENV`, `PYTHONSTARTUP`, …)
are refused.

## Helpers

- Live in `$RUN/checks/`; referenced as `{plan_dir}/checks/<file>`.
- Drive the project's own code: `go run ./cmd/...`, `go test -run`, `python3 -m <pkg>`, the
  built binary. A helper that copies the vulnerable function and tests the copy proves nothing.
- Every file named in argv is hashed; files under the plan copy or the checkout (≤ 16 MiB) are
  archived as `results/helpers/<sha256>` so a reviewer can read exactly what ran.
- Symlinks in the plan directory are refused.

## A worked check set

A Python service whose `safe_join(root, name)` was patched to strip `../` once. Helper
`checks/probe.py` imports the package from `$PPV_CHECKOUT`, prints the marker, then exits 1 if
the joined path escapes `root`.

```json
[
  {"id": "behavior-listing", "kind": "behavior", "compare_stream": "stdout",
   "rationale": "listing a plain directory prints the same bytes before and after",
   "covers": ["files.list_dir"], "argv": ["python3", "-m", "files", "list", "fixtures/plain"]},
  {"id": "control-plain-name", "kind": "control",
   "rationale": "a plain name joins inside root on both revisions",
   "covers": ["files.safe_join"], "argv": ["python3", "{plan_dir}/checks/probe.py", "notes.txt"]},
  {"id": "exploit-dotdot", "kind": "exploit",
   "rationale": "../etc/passwd escapes root on base and stays inside on patched",
   "covers": ["files.safe_join"], "argv": ["python3", "{plan_dir}/checks/probe.py", "../etc/passwd"]},
  {"id": "regression-unit", "kind": "regression",
   "rationale": "the existing join tests keep passing",
   "covers": ["tests/test_join.py"], "argv": ["python3", "-m", "unittest", "tests.test_join"]},
  {"id": "security-absolute", "kind": "security",
   "rationale": "an absolute name is still refused after the patch",
   "covers": ["files.safe_join"], "argv": ["python3", "{plan_dir}/checks/absolute.py"]},
  {"id": "suite-all", "kind": "suite",
   "rationale": "the whole unittest suite passes on patched",
   "covers": ["tests/"], "argv": ["python3", "-m", "unittest", "discover", "-s", "tests"]},
  {"id": "variant-nested-dotdot", "kind": "variant",
   "rationale": "....// collapses to ../ after a single strip, so it still escapes on patched",
   "covers": ["files.safe_join"], "argv": ["python3", "{plan_dir}/checks/probe.py", "....//etc/passwd"]}
]
```
