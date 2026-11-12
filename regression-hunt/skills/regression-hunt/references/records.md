# Campaign records

## Contents

- [Layout](#layout)
- [Path rules](#path-rules)
- [scope.json](#scopejson)
- [registry.json](#registryjson)
- [campaign.json](#campaignjson)
- [Seals](#seals)
- [runtime/ records](#runtime-records)
- [Fields every stage record has](#fields-every-stage-record-has)
- [prepare.json and source.json](#preparejson-and-sourcejson)
- [hunt.json and candidate files](#huntjson-and-candidate-files)
- [reproduce.json and replay.json](#reproducejson-and-replayjson)
- [decision.json](#decisionjson)
- [report-stage.json and the report](#report-stagejson-and-the-report)

All records are UTF-8 JSON. Timestamps are ISO 8601 with a timezone offset.

## Layout

```
<campaign>/
  scope.json            frozen list of changes (coordinator writes once)
  registry.json         attempt ledger, written only by registry.py
  campaign.json         index of accepted records (coordinator only)
  progress.md           running notes: guidance SHAs, absent files, limits, blockers
  guidance/<change>/<sha>/   instruction files copied from git objects, plus absent.txt
  runtime/              launch and terminal records, raw agent evidence, aNNN-handle files
  attempts/aNNN/        one directory per stage attempt; the sealed record lives here
```

Workers write only inside their own `attempts/aNNN/`. They never write `runtime/`, `scope.json`,
`registry.json` or `campaign.json`.

## Path rules

Every path inside a record is relative to the campaign directory: no leading `/`, no `.` or `..`
segments, no symlinks anywhere on the way. A directory listed as an input or artifact stands for
every file below it.

## scope.json

```json
{"changes": [{"id": "change-1", "input": {"repository": "/abs/repo", "s0": "<40 hex>", "s1": "<40 hex>"}}]}
```

`id`: unique, non-empty, never `campaign`. `input`: a string (PR URL, `owner/repo#N`, a commit) or
an object with exactly `repository`, `s0`, `s1`. A different scope means a new campaign.

## registry.json

Version 3, written by `registry.py` only.

| Key | Shape |
|---|---|
| `version` | `3`; anything else is refused, nothing is migrated |
| `scope` | `null` before init, then `{"file": "scope.json", "hash": sha256, "changes": {id: input}}` |
| `prefixes` | `{"h001-": change id}` |
| `candidates` | `{id: {"prefix", "key", "change", "file"}}`; `file` is set when the hunt is accepted |
| `attempts` | `{aNNN: attempt}` |

An attempt: `id`, `stage` (prepare, hunt, reproduce, replay, adjudicate, report), `change`,
`candidate` (or null), `prefix` (hunts only), `inputs`, `input_hashes` ({path: sha256}, seals of
sealed inputs included), `directory` (`attempts/aNNN`), `agent`, `state` (reserved, running,
accepted, superseded), `record`, `seal` (sha256 of the seal file), `launch` and `terminal`
receipts (`{"record", "hashes", "value"}`), `verification` (`shared-host`; `isolated` is defined
by the format but this version cannot produce it).

## campaign.json

```json
{"title": "...", "changes": [{"id": "change-1", "input": <as in scope>, "prepare": "attempts/a001/prepare.json",
  "hunt": "attempts/a002/hunt.json", "limitations": "...",
  "candidates": [{"id": "h001-001", "candidate": "attempts/a002/candidates/h001-001.json",
                  "decision": "attempts/a005/decision.json"}]}]}
```

Only accepted records go in. `prepare`, `hunt` and `decision` stay `null` until accepted.

## Seals

`evidence.py seal` writes `<record>.seal.json`:

| Key | Holds |
|---|---|
| `record` | sha256 of the record file |
| `inputs` | {file: sha256}, directories expanded |
| `artifacts` | {file: sha256}, directories expanded |
| `dependencies` | {input path: sha256 of that input's own seal}, for sealed inputs only |

A record may not list itself or its seal. Sealing an already sealed record only verifies it; a
sealed attempt is never rewritten or renamed.

## runtime/ records

Launch (`runtime.py launch` writes it): `event` `launch`, `attempt`, `tool` `claude.Agent`, `call`
(the Agent call input; `subagent_type` non-empty and not `fork`), `response` `{"agent_id"}`,
`observed_at`, `evidence` (the raw call and response files under `runtime/`, non-empty).

Terminal (`runtime.py terminal`): `event` `terminal`, `attempt`, `tool` `claude.task_notification`,
`response` `{"task_id", "status"}` with status `completed`, `failed` or `killed`, `observed_at`,
`evidence`. `killed` cannot be used for a retry.

Handle file `runtime/aNNN-handle`: the agent id, plain text, written by `runtime.py publish` after a
successful bind.

## Fields every stage record has

| Field | Rule |
|---|---|
| `stage` | the attempt's stage |
| `agent` | the handle read from the handle file |
| `attempt`, `change` | from the assignment (`campaign` for the report) |
| `status` | `complete` or `blocked` |
| `summary` | findings, or exactly which prerequisite is missing |
| `security_review` | non-empty: paths reviewed and conclusions, or the search and access limits |
| `inputs` | exactly the assigned inputs |
| `artifacts` | paths inside the attempt directory, enough to inspect or repeat the work |

No secrets or live credentials anywhere; configs are sanitised.

## prepare.json and source.json

`prepare.json` adds `source`: `attempts/aNNN/snapshot/source.json`, or `null` when blocked.
Artifacts: the snapshot (S0/, S1/, change.patch, change-message.txt, source.json), the frozen PR
context or commit messages with collection time and URLs, the boundary explanation, the
security-document search result.

`source.json`: `repository` (path), `s0`, `s1` (full 40-hex commits), `tree0`, `tree1`.

## hunt.json and candidate files

`hunt.json` adds `candidates` (exactly the ids reserved under the attempt's prefix, no repeats),
`candidate_files` ({id: path inside the attempt directory, each sealed}) and `coverage` (free text:
what was traced, supplied leads, what was not inspected). An empty list is a valid result.

A candidate file, one per id, sealed on its own: `id`, `key` (the registered hypothesis key),
`title`, `patch_intent`, `prior_behavior`, `changed_code`, `reachable_trigger`, `possible_defect`,
`false_positive_checks`, `proof_needed` (strings or string lists), plus `change`, `stage` (`hunt`),
`agent`, `inputs` (the prepare record) and `artifacts` (`[]`) so it can be sealed.

## reproduce.json and replay.json

| Field | Rule |
|---|---|
| `candidate` | the assigned candidate |
| `source` | the prepare stage's `source.json` |
| `setup` | repeatable deployment steps |
| `poc` | the runnable entry, unchanged between reproduction and replay |
| `workload` | input and config without revision-specific addresses |
| `runs` | exactly two, S0 first: `state` (`S0`/`S1`), `revision` (= source s0/s1), `deployment` (the real interface used), `command`, `log`, `behavior` (`correct`, `failure`, `unknown`) |
| `build_dirs` | non-empty when complete, all inside the attempt directory |

Replay also: its inputs include the reproduction record; `poc` and `workload` hash equal to the
reproduction's; its log paths differ from the reproduction's. In both, the S0 and S1 logs are
non-empty and differ. Blocked records may leave `runs` empty and omit what never ran. Only
S0 `correct` with S1 `failure` supports a confirmation.

## decision.json

Adds `candidate`, `outcome` (`REPRODUCED_REGRESSION`, `INCOMPLETE_FIX`, `LATENT_BUG`,
`PREEXISTING_BUG`, `REJECTED`, `UNRESOLVED`), `reason` (cited), `evidence` (non-empty; files of
this package or of a sealed input's package). Inputs include prepare, hunt and the candidate file.
Optional for non-confirmations: `duplicate_of` (a canonical candidate with the same outcome that is
not itself a duplicate).

`REPRODUCED_REGRESSION` also needs `status` complete and: `reproduction`, `replay` (record paths,
both listed as inputs), `category` (`VULNERABILITY`, `FUNCTIONAL_BUG`, `PERFORMANCE`,
`BUILD_TEST`), `severity` (`Low`..`Critical`), `likelihood` (`Low`..`High`), `severity_reason`,
`likelihood_reason`, and `checks` with exactly nine keys, each
`{"conclusion", "reason", "evidence"}` (evidence may be empty only for `NOT_APPLICABLE`):

| Check | Needed conclusion |
|---|---|
| `supported_behavior`, `reachability`, `introduced_defect` | `SUPPORTED` |
| `incomplete_fix`, `latent_bug`, `preexisting_bug`, `intentional_change`, `unsupported_expectation` | `REFUTED` |
| `security_scope` | `SUPPORTED` for `VULNERABILITY`, otherwise `NOT_APPLICABLE` |

`UNKNOWN` anywhere blocks a confirmation. Reproduction, replay and adjudication must be three
different agents, and both experiments must list prepare and hunt as inputs.

## report-stage.json and the report

`report-stage.json`: the common fields with `change` `campaign`; artifacts are the generated report
directory. Blocked lists the validation errors in `summary`.

`report.json`: `title`; `counts` (each outcome, rows with `duplicate_of` left out); `changes`
(`id`, `input`, `status` COMPLETE/INCOMPLETE, `limitations`); `findings` (`id`, `change`, `input`,
`title`, `outcome`, `reason`, `evidence`, `verification` (confirmed only), `unresolved_reason`, and
the optional rating fields and `duplicate_of` copied from the decision). `report.md` and
`index.html` show the same with relative evidence links; a structured input reads
`repo @ s0..s1`.
