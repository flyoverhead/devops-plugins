# Semgrep rule syntax, quick reference

## Contents

- Rule skeleton
- Pattern operators
- Metavariables
- Taint keys
- Test annotations
- Exit codes and flags

## Rule skeleton

```yaml
rules:
  - id: lower-kebab-id
    languages: [go]
    severity: HIGH
    message: One short sentence naming $VAR bound in the pattern.
    pattern: ...
```

Exactly one of `pattern`, `patterns`, `pattern-either`, `pattern-regex` or (with `mode: taint`)
the source/sink keys supplies the match. One rule per file.

## Pattern operators

| Operator | Meaning |
|---|---|
| `pattern` | match this code shape |
| `patterns` | all children must match (logical and) |
| `pattern-either` | any child matches (logical or) |
| `pattern-regex` | PCRE over the raw text |
| `pattern-inside` | match only within a surrounding shape |
| `pattern-not-inside` | match only outside a surrounding shape |
| `pattern-not` | drop matches that also fit this shape |
| `pattern-not-regex` | drop matches whose text fits this regex |
| `metavariable-regex` | a bound metavariable must match a regex |
| `metavariable-pattern` | a bound metavariable's code must match a nested pattern |
| `metavariable-comparison` | compare a bound value numerically or by expression |
| `focus-metavariable` | report only the span of one metavariable |

## Metavariables

| Form | Matches |
|---|---|
| `$X` | one expression, name or type, and the same code on every reuse |
| `$_` | one node, no binding |
| `$...X` | a run of arguments or statements |
| `...` | zero or more of anything in that position |
| `<... $X ...>` | `$X` at any depth inside an expression |

Names are uppercase letters, digits and underscore. A typed metavariable written with ` : ` in
a pattern must be quoted in the YAML.

## Taint keys

```yaml
mode: taint
pattern-sources:      # where untrusted data enters
pattern-sinks:        # where it must not arrive
pattern-sanitizers:   # calls that make it safe
pattern-propagators:  # extra ways data moves (optional)
```

- Sources and sanitizers accept `exact` and `by-side-effect` (`true` or `only`).
- Sinks default to `exact: true`: the flagged node must be the tainted expression itself.
- Taint flows through function calls and string concatenation by default.
- `--dataflow-traces` prints the path for each finding.

## Test annotations

```text
// ruleid: <id>     expected finding on the next line   (Go, TypeScript)
// ok: <id>         expected silence on the next line
# ruleid: <id>      same, for Python, Bash, YAML, HCL, Dockerfile
# ok: <id>
```

Name the test file like the rule, with the language's extension, in the same directory.

## Exit codes and flags

| Code | Meaning |
|---|---|
| 0 | scan ran, nothing wrong |
| 1 | findings reported (scan mode) |
| 2 | fatal error, often a pattern that does not parse |
| 7 | invalid rule file |

Always: `--metrics=off --disable-version-check`. Useful: `--test <dir>`, `--dump-ast --lang <l>
<file>`, `--dataflow-traces`, `--config <rule.yaml> <file>`.
