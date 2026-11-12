# jq queries for SARIF 2.1.0

## Contents

- Severity definitions (paste first)
- Exploration
- Results
- Filtering
- Locations
- Rules
- Fingerprints
- Aggregation
- Formatting
- Comparison
- Transformation
- Validation
- Fixtures

Every level filter below goes through `sarif_level`. A bare `select(.level == "error")` is
wrong for CodeQL output: CodeQL leaves `level` off results and puts it on the rule, so that
filter counts zero on a failing repository.

## Severity definitions (paste first)

The same definitions ship as a jq module: `jq -L "${CLAUDE_SKILL_DIR}/resources" 'include "sarif"; …'`.
To paste instead, put this block at the start of the program:

```jq
def sarif_rules($run; $r):
  $r.rule.toolComponent.index as $c
  | (if ($c | type) == "number" then $run.tool.extensions[$c] else $run.tool.driver end)
  | .rules // [];
def sarif_rule($run; $r):
  sarif_rules($run; $r) as $table
  | ([$r.rule.index, $r.ruleIndex] | map(numbers) | first) as $at
  | if $at != null and $at >= 0 and $at < ($table | length) then $table[$at]
    else first($table[] | select(.id == ($r.ruleId // $r.rule.id))) // null end;
def sarif_level($run; $r):
  if (($r | has("kind")) and $r.kind != "fail") then "none"
  else [$r.level, sarif_rule($run; $r).defaultConfiguration.level, "warning"] | map(strings) | first end;
def sarif_results:
  .runs[]? as $run | ($run.results // [])[] | . + {_level: sarif_level($run; .)};
```

Order follows SARIF 2.1.0 §3.27.10: a `kind` other than `fail` means `none`; otherwise the first
string among the result's `level`, the rule's `defaultConfiguration.level`, and `warning`. The index guard matters:
`ruleIndex: -1` means "no rule", and a negative jq index silently reads the last rule.

The examples below write `S='include "sarif";'` and run `jq -L "${CLAUDE_SKILL_DIR}/resources"`.

## Exploration

```bash
jq '{version, runs: (.runs | length)}' results.sarif
jq -r '.runs[] | "\(.tool.driver.name) \(.tool.driver.semanticVersion // .tool.driver.version // "?") results=\(.results | length)"' results.sarif
jq 'reduce .runs[] as $run (0; . + ($run.results // [] | length))' results.sarif
```

## Results

```bash
jq -L "$R" "$S"' [sarif_results] | map({rule: .ruleId, level: ._level, msg: .message.text}) | .[:10]' results.sarif
```

## Filtering

```bash
jq -L "$R" "$S"' [sarif_results | select(._level == "error")] | length' results.sarif
jq -L "$R" "$S"' [sarif_results | select(._level == "error" or ._level == "warning")]' results.sarif
jq '[.runs[].results[] | select(.ruleId | test("injection"))]' results.sarif
jq --arg dir cmd/ '.runs[].results[] | select(any(.locations[]?; .physicalLocation.artifactLocation.uri // "" | startswith($dir)))' results.sarif
```

## Locations

```bash
jq -L "$R" -r "$S"' sarif_results | select(._level == "error")
  | "\(.locations[0].physicalLocation.artifactLocation.uri // "?"):\(.locations[0].physicalLocation.region.startLine // "?") \(.ruleId)"' results.sarif
```

`artifactLocation.uri` may be absolute, `file://`-prefixed, percent-encoded, or relative to a
`uriBaseId` such as `%SRCROOT%`. Normalise before comparing (see the Python helper).

## Rules

```bash
jq -r '.runs[].tool.driver.rules[]? | "\(.id)\t\(.defaultConfiguration.level // "warning")\t\(.properties["security-severity"] // "-")"' results.sarif
jq -r '.runs[].tool.extensions[]?.rules[]? | .id' results.sarif   # CodeQL keeps rules on extensions
```

## Fingerprints

```bash
jq '[.runs[].results[] | (.fingerprints // .partialFingerprints // {} | to_entries[0].value)] | unique | length' results.sarif
```

When no tool fingerprint exists, compute one with the Python helper; jq has no hash function.

## Aggregation

```bash
jq -L "$R" "$S"' [sarif_results] | group_by(._level) | map({level: .[0]._level, n: length})' results.sarif
jq 'reduce .runs[].results[] as $x ({}; .[$x.ruleId // "?"] += 1) | to_entries | sort_by(-.value) | limit(5; .[])' results.sarif
jq '[.runs[].results[] | .locations[0]?.physicalLocation.artifactLocation.uri // empty] | unique | length' results.sarif
```

## Formatting

```bash
jq -L "$R" -r "$S"' ["level","rule","file","line"], (sarif_results
  | [._level, .ruleId, .locations[0].physicalLocation.artifactLocation.uri, .locations[0].physicalLocation.region.startLine]) | @csv' results.sarif
```

## Comparison

By location key (rule, file, line). Prefer tool fingerprints when both files carry them.

```bash
jq -n --slurpfile a baseline.sarif --slurpfile b current.sarif '
  def keys($d): [$d[0].runs[].results[] | "\(.ruleId)|\(.locations[0].physicalLocation.artifactLocation.uri)|\(.locations[0].physicalLocation.region.startLine)"];
  (keys($a)) as $old | (keys($b)) as $new
  | {new: ($new - $old), fixed: ($old - $new)}'
```

## Transformation

Concatenate runs (each keeps its own rule table, so `ruleIndex` stays valid):

```bash
jq -s '{version: "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", runs: (map(.runs) | add)}' a.sarif b.sarif
```

## Validation

```bash
jq -e '.version == "2.1.0" and (.runs | type == "array")' results.sarif
```

Exit 1 means not SARIF 2.1.0: say so and stop. Full schema checks need `jsonschema`, which the
user installs in a venv; the skill never installs it.

## Fixtures

`resources/fixtures/codeql-no-level.sarif` (levels only on rules, one `ruleIndex: -1`) and
`resources/fixtures/levels-on-results.sarif` (levels on results, one `kind: pass`) each hold
exactly one error-level result. Use them to check a new query before trusting it.
