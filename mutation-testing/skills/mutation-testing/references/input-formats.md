# Input formats

## Contents

- [mewt and muton](#mewt-and-muton)
- [gremlins](#gremlins)
- [mutmut](#mutmut)
- [Stryker and mutation-testing-elements JSON](#stryker-and-mutation-testing-elements-json)
- [Others](#others)

Identify the format by its field names or line shapes. When unsure, read the first 50 lines.
What the analysis needs from every format: path, line, original, mutated, operator, status.

## mewt and muton

`mewt results --format json` (default view: uncaught only; `--all` for everything):

```json
{"results": [
  {"mutant":  {"id": 7, "target_id": 1, "mutation_slug": "COS", "old_text": ">", "new_text": ">=",
               "byte_offset": 1043, "line_offset": 18},
   "outcome": {"mutant_id": 7, "status": "Uncaught", "duration_ms": 3120,
               "output": "<test stdout and stderr>", "time": "<ISO timestamp>"},
   "target":  {"id": 1, "path": "src/limits.rs", "language": "rust", "file_hash": "<sha256>"}}
]}
```

- `status` is `Uncaught`, `TestFail`, `Skipped` or `Timeout`.
- Confirm the line by reading the source at `line_offset` and finding `old_text` there; if
  `file_hash` no longer matches the file, the code changed after the campaign; say so.
- `mewt status` text gives per-target totals (mutants total, tested, untested), outcomes (caught,
  uncaught, timeout, skipped) and catch rate per severity, then campaign totals. Use it for the
  denominators when the JSON holds survivors only.

## gremlins

Text lines, one per mutant, then a footer:

```text
        LIVED CONDITIONALS_BOUNDARY at pkg/quota/check.go:31:9
       KILLED CONDITIONALS_NEGATION at pkg/quota/check.go:31:9
  NOT COVERED INCREMENT_DECREMENT at pkg/quota/check.go:44:3
Killed: 1, Lived: 1, Not covered: 1
Test efficacy: 50.00%
Mutator coverage: 66.67%
```

- Status: `KILLED`, `LIVED`, `NOT COVERED`, `TIMED OUT`, `NOT VIABLE`.
- Location is `file:line:column`; the mutator name says what changed (`CONDITIONALS_BOUNDARY`
  `<` ↔ `<=`, `CONDITIONALS_NEGATION` `==` ↔ `!=` and `<` ↔ `>=`, `ARITHMETIC_BASE` `+` ↔ `-` and
  `*` ↔ `/`, `INVERT_NEGATIVES` `-x` → `x`, `INCREMENT_DECREMENT`, `INVERT_LOGICAL`,
  `INVERT_LOOPCTRL`, `INVERT_ASSIGNMENTS`, `REMOVE_SELF_ASSIGNMENTS`). Reconstruct the mutated text
  from the source at that column.
- Test efficacy = killed / (killed + lived). Mutator coverage = covered / all.
- `--output` JSON carries the same facts per file.

## mutmut

`mutmut results` lists mutant names grouped by status (killed, survived, timeout, suspicious, no
tests). The name encodes the module and function; `mutmut show <name>` prints the diff, which gives
the line and the change. `mutmut show` is not pre-approved and prompts.

## Stryker and mutation-testing-elements JSON

`reports/mutation/mutation.json`: `files.<path>.mutants[]` with `id`, `mutatorName`,
`replacement`, `location.start.line`, `status` (`Killed`, `Survived`, `NoCoverage`, `Timeout`,
`CompileError`, `RuntimeError`, `Ignored`). `NoCoverage` is a gap with no test touching the line.
The same schema comes out of mull (mutator names start with `cxx_`) and several other tools.

## Others

| Tool | Shape | Survivor marker |
|---|---|---|
| cargo-mutants | `mutants.out/outcomes.json`, plus `missed.txt` with `file:line:col: replace … with …` | `missed` |
| mutahunter | JSON report with file, line, original and mutated code | survived |
| slither-mutate | text blocks: `[XX] Mutation: <name>`, then Original, Mutated, File, Line, Status | `SURVIVED` |
| mull (SQLite) | tables `mutant`, `mutation_point`, `mutation_result`; ask the user to export to JSON first | survived |
| dextool | JSON `mutants[]` with id, file, line, operator (`AOR`, `ROR`, `LCR`, `SDL`, `UOI`), original, mutation, status; or SQLite table `mutation` | `alive` |

For a SQLite database, do not open it with a shell client; ask for the tool's own export.
