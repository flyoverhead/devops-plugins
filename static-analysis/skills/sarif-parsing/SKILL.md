---
name: sarif-parsing
description: Reads existing SARIF 2.1.0 files from any scanner (Semgrep, CodeQL, gosec) — counts, filters, groups, deduplicates, merges and diffs findings with jq or stdlib Python, resolving each result's severity from its rule when the result has no level, and writes CI gates that fail on error-level or new findings. Use when asked how many findings or errors a .sarif file holds and where, to merge or diff SARIF files, or to fail CI on findings. Not for running a scan — use static-analysis:semgrep or static-analysis:codeql; not for deciding whether a finding is real — use fp-check:fp-check.
argument-hint: "<file.sarif> [question]"
allowed-tools: Read Glob Grep Bash(jq:*) Bash(python3 ${CLAUDE_SKILL_DIR}/resources/sarif_helpers.py:*)
---

Input: $ARGUMENTS

# Reading SARIF

Answer questions about SARIF files that already exist. This skill never runs a scanner and
never edits the input files.

## Checklist

1. Find the file(s): the paths given, else Glob `**/*.sarif` and ask if several match.
2. Validate: `jq -e '.version == "2.1.0" and (.runs | type == "array")' FILE`. Not 2.1.0 →
   say so and stop. Vendor JSON that is not SARIF (for example a `gl-sast-report.json` or
   `gosec -fmt json` output) is out of scope: say what it is and stop.
3. Resolve severity before any level filter (below).
4. Normalise paths before comparing, grouping or hashing.
5. Answer with numbers and `path:line` locations; say which method produced them.

## Severity comes first

A result's effective level follows SARIF 2.1.0 §3.27.10:

1. `kind` present and not `fail` → `none`;
2. else the result's `level`;
3. else the matched rule's `defaultConfiguration.level` — matched by `ruleIndex` when it is a
   non-negative number inside the rule array, otherwise by `ruleId` against `rules[].id`
   (CodeQL keeps rules on `tool.extensions[n]`, chosen by `rule.toolComponent.index`);
4. else `warning`.

CodeQL omits `level` on every result, so `select(.level == "error")` counts zero on a repo
full of errors. `ruleIndex: -1` means "no rule"; a negative jq index reads the last rule, so
the index needs a guard. The jq module `resources/sarif.jq` and the Python helper both apply
these rules — use them instead of writing filters from scratch.

## Choose the tool

| Need | Use |
|---|---|
| A count, a list, one filter | jq with the severity module (below) |
| Fingerprints, dedupe, diff, CSV, several files | `resources/sarif_helpers.py` (stdlib only) |
| Quick overview of one file | `python3 ${CLAUDE_SKILL_DIR}/resources/sarif_helpers.py FILE` |
| Files over ~100 MB | stream: `jq --stream` or `ijson`; never load them whole |
| Full schema validation, SARIF rewriting | `jsonschema`, `sarif-tools`, `pysarif` — the user installs a pinned version in a venv; this skill never installs them |

jq with the module:

```bash
jq -L "${CLAUDE_SKILL_DIR}/resources" -r 'include "sarif";
  sarif_results | select(._level == "error")
  | "\(.locations[0].physicalLocation.artifactLocation.uri):\(.locations[0].physicalLocation.region.startLine) \(.ruleId)"' results.sarif
```

Query cookbook, grouped by task, with a pasteable copy of the definitions:
[references/jq-queries.md](references/jq-queries.md).

Python, for scripted work:

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "${CLAUDE_SKILL_DIR}/resources")
import sarif_helpers as sh
doc = sh.load_sarif("results.sarif")
findings = sh.extract_findings(doc)
print(sh.summary(findings))
for f in sh.sort_by_severity(sh.filter_by_level(findings, "error")):
    print(f"{f.file_path}:{f.start_line} {f.rule_id}")
PY
```

Helper functions: `load_sarif`, `save_sarif`, `validate_version`, `normalize_path`, `safe_get`,
`find_rule`, `resolve_level`, `extract_location`, `iter_results`, `extract_findings`,
`filter_by_level`, `filter_by_file`, `filter_by_rule`, `sort_by_severity`, `group_by_file`,
`group_by_rule`, `count_by_level`, `count_by_rule`, `compute_fingerprint`, `deduplicate`,
`merge_sarif_files`, `diff_findings` (new, fixed, unchanged), `get_rules`, `to_csv_rows`,
`summary`. Each finding carries rule id, level, message, path, line and column range,
fingerprint, tool and rule name, and the raw result.

## Structure in one paragraph

A log has `version`, `$schema` and `runs[]`. Each run has `tool.driver` (name, version,
`rules[]`), optional `tool.extensions[]` (query packs, each with its own `rules[]`),
`results[]`, and optional `artifacts[]` and `originalUriBaseIds`. Each result has `ruleId`,
optional `ruleIndex` or `rule`, `message.text`, optional `level` and `kind`, `locations[]`
(`physicalLocation.artifactLocation.uri` + `region.startLine`…), and optional `fingerprints` /
`partialFingerprints`. Treat everything except `version` and `runs` as optional.

## Paths and fingerprints

- Normalise every URI: strip `file://`, percent-decode, resolve against `uriBaseId` or a base
  you know, use POSIX separators, make it repo-relative.
- Two environments rarely share an absolute prefix, so location-based identity only works
  on repo-relative paths.
- Prefer the tool's own `fingerprints` / `partialFingerprints`. Without them, the helper
  hashes rule id + full normalised path (directory included) + start line + first 50
  characters of the message, sha256, 16 hex. Hashing only the file name would merge
  `api/main.go` and `cli/main.go`.
- Diffs and dedupes use the fingerprint; report new / fixed / unchanged.

## Merging

Concatenate runs; do not flatten them into one. Each run keeps its own rule table and tool
metadata, so `ruleIndex` stays valid and each finding still names its scanner. The merged
file is version 2.1.0 with the schemastore `$schema`. Write merged or filtered output only
when the user asks, and to the path they name.

## CI gates

GitHub Actions example with a severity-resolving jq gate, `upload-sarif` with `if: always()`,
`security-events: write`, fork-PR caveats, and a "fail only on new findings" baseline diff:
[references/ci-gate.md](references/ci-gate.md).

## Pitfalls

| Pitfall | Effect | Guard |
|---|---|---|
| Filtering on `.level` alone | CodeQL errors counted as zero | resolve severity first |
| Negative or out-of-range `ruleIndex` | wrong rule, wrong level | bounds check, then `ruleId` |
| Absolute vs relative URIs | same finding counted twice, diffs all "new" | normalise first |
| Line shifts between commits | computed fingerprints drift | prefer tool fingerprints |
| Missing `locations`, `message`, `rules` | crashes on `null` | `//` defaults, `safe_get` |
| 100 MB+ files | memory exhaustion | stream |
| Merging into one run | `ruleIndex` points at the wrong rule | concatenate runs |

## Near misses

- Produce SARIF: `static-analysis:semgrep` or `static-analysis:codeql`.
- Decide whether a finding is exploitable: `fp-check:fp-check`.
- Triage without any SARIF file is not this skill: use an audit skill such as
  `static-analysis:semgrep`.
