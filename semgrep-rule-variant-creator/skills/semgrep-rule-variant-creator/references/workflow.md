# Workflow mechanics

## Contents

- Independent cycles
- Test file extensions
- Annotation placement
- Reading failures
- Greens that mean nothing
- Troubleshooting

## Independent cycles

Each language has its own directory, its own tests and its own validation. A failure in one
language never blocks the next; report it and move on. Do not carry a pattern across languages
by copying text: re-derive it from the target's AST.

## Test file extensions

| Language | Test file | Marker |
|---|---|---|
| Go | `<id>.go` | `// ruleid:` |
| Python | `<id>.py` | `# ruleid:` |
| Bash | `<id>.sh` | `# ruleid:` |
| TypeScript | `<id>.ts` | `// ruleid:` |
| JavaScript | `<id>.js` | `// ruleid:` |
| HCL | `<id>.tf` | `# ruleid:` |
| YAML | `<id>.test.yaml` | `# ruleid:` |
| Dockerfile | `<id>.dockerfile` | `# ruleid:` |
| Java | `<id>.java` | `// ruleid:` |

Give the test file the rule's basename plus the target extension. The rule is passed with
`--config` and the test file by path. Two cases differ:

- Dockerfile: `<id>.dockerfile` (a file literally named `Dockerfile` also grades, but keeps no
  basename link to the rule).
- YAML: the rule already owns `<id>.yaml`, so the test is `<id>.test.yaml`. Passing the rule file
  itself as the test target grades zero tests.

## Annotation placement

The marker comment sits on the line directly above the graded code. A blank line, or a second
annotation, between them grades the wrong line. When one statement spans several lines, the
marker goes above the line where the match starts.

## Reading failures

| Output | Meaning | Fix |
|---|---|---|
| Missed lines (expected `ruleid`, no finding) | pattern narrower than the bug | widen sources or sinks, check the AST |
| Incorrect lines (finding on an `ok` line) | pattern broader than the safe form | add a sanitizer or `pattern-not` |

Fix the rule, never the tests. Three failed fix rounds end the language: report failed
validation and paste the last output.

## Greens that mean nothing

1. A rule Semgrep skipped, such as a Pro-only language, still ends "All tests passed".
2. A test file whose extension is not mapped to the rule's language grades zero tests.
3. A pass from a different Semgrep binary than the recorded version.

Check that the run counted at least the number of annotated cases, and that the version matches
the one recorded in preflight.

## Troubleshooting

- Exit 7: the rule YAML does not parse. Exit 2: a pattern does not parse in the target language.
  Run the rule on the test file alone to see which.
- Taint finds nothing: `semgrep --metrics=off --disable-version-check --dataflow-traces -f
  <rule> <file>`; check the source actually matches and that no sanitizer is too broad.
- Start broad, then narrow: a pattern that matches everything proves the load path; add
  constraints one at a time.
- `focus-metavariable` belongs inside the `patterns:` list of the sink or source, after the
  patterns that bind the metavariable.
