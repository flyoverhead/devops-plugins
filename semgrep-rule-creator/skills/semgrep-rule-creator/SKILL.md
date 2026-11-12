---
name: semgrep-rule-creator
description: Produces a single custom Semgrep detection rule plus its annotated test file, authored tests-first and checked locally with semgrep --test until nothing is missed or wrongly flagged; covers Go, Python, Bash, TypeScript, Terraform HCL, YAML, Ansible and Dockerfile, with taint mode for data-flow bugs. Use when someone wants a new or repaired Semgrep rule or a SAST check for a bug pattern, or asks how to build one so CI catches it. Not for scanning a repo with existing rules — use static-analysis:semgrep; not for translating a rule — use semgrep-rule-variant-creator:semgrep-rule-variant-creator.
argument-hint: "[bug pattern] [language] [output-dir]"
allowed-tools: Read Write Edit Glob Grep Bash(semgrep --metrics=off:*) Bash(SSL_CERT_FILE=/etc/ssl/cert.pem semgrep --metrics=off:*) Bash(command -v semgrep) Bash(mkdir -p:*) WebFetch(domain:raw.githubusercontent.com)
---

Request: $ARGUMENTS

# Custom Semgrep rule, tests first

The deliverable is one rule that a machine has shown to flag the bad code and leave the good
code alone. A rule that "looks right" is a guess; the `--test` run is the evidence.

## Ground rules

- **One rule, one directory.** `<rule-id>/<rule-id>.yaml` holds exactly one rule;
  `<rule-id>/<rule-id>.<ext>` holds its tests. Nothing else is written, and nothing outside that
  directory. The directory goes under the path the user names, else the current directory.
- **Local only.** Every `semgrep` call carries `--metrics=off --disable-version-check`. Never
  `--validate`, `--config auto`, a `p/...` registry config, `semgrep login` or `semgrep ci`.
  Each of those contacts the registry.
- **Probe for the binary first.** Run `command -v semgrep` before anything else. If it prints
  nothing, you still produce the rule and its tests, but you tell the user that none of it was
  parsed, tested or validated, hand over the `--test` command for them to run, and do not
  install semgrep by any route (pip, pipx, uv, brew) or call the result a pass.
- **No secrets in tests.** Fixtures use obvious placeholders (`example-token`, `changeme`).
- **Wiring is the user's.** Say where the two files are. Do not edit their CI or Semgrep config.

On macOS a startup crash about a missing CA trust anchor means prefixing the command with
`SSL_CERT_FILE=/etc/ssl/cert.pem`.

## Limits

- Every `semgrep` run carries `--metrics=off --disable-version-check`.
- Never `-o`/`--output`, any `--*-output=` (`--sarif-output=`, `--json-output=` and the like) or
  `--autofix`. Results go to stdout; only the rule and test files are written, with Write.
- Never a remote `--config http://…` or `--config https://…`; configs are local paths.

## Progress checklist

Copy and tick as you go:

```text
- [ ] 1 Analyse the problem
- [ ] 2 Write the tests
- [ ] 3 Dump the AST
- [ ] 4 Write the rule
- [ ] 5 Iterate until green
- [ ] 6 Simplify
- [ ] 7 Final run
```

## 1. Analyse the problem

State the bug to yourself the way you would to a new colleague: what goes wrong, who can trigger
it, which call is the dangerous one. Then decide:

| Situation | Mode |
|---|---|
| Untrusted input travels to a dangerous call (injection, path traversal, SSRF) | `mode: taint` |
| The flaw is the code shape itself (a banned function, a flag, a setting) | plain `pattern` forms |

If the pattern, the language or the dataflow question is unclear, ask before writing anything.
Use the parser Semgrep has for the language. `languages: generic` is the last resort, for text
it cannot parse, such as Jinja2 templates.

Read [syntax-reference.md](references/syntax-reference.md) for operators and taint keys. Fetch a
page from the Semgrep docs (raw GitHub content only) when a construct is missing from it.

## 2. Write the tests first

No rule exists yet; the file defines what the rule must do. Mark each case with a comment on
the line directly above the code, carrying only the marker:

| Language | Marker |
|---|---|
| Go, TypeScript | `// ruleid: <rule-id>` or `// ok: <rule-id>` |
| Python, Bash, YAML, HCL, Dockerfile | `# ruleid: <rule-id>` or `# ok: <rule-id>` |

Rules for the markers:

- Only `ruleid` and `ok`. `todoruleid` and `todook` are not used.
- The comment line contains nothing but marker and id. No block comments.
- The comment sits immediately above the flagged line. A blank line between them breaks it.

Cover, at least:

1. the plainly vulnerable form;
2. the plainly safe form;
3. style variants of the vulnerable form (different variable names, helper wrappers, quoting);
4. input that was sanitised or validated before the sink;
5. unrelated code that merely looks similar;
6. nesting: inside `if`, loops, `try`/`defer`, closures and callbacks.

A typed metavariable binds only to a declared variable. In Go that means each test is a whole
function with the typed parameter, not loose statements.

## 3. Dump the AST

```bash
semgrep --metrics=off --disable-version-check --dump-ast --lang go <rule-id>/<rule-id>.go
```

Read how the target constructs parse before writing patterns. Typical surprises: `a.b()` is not
`a().b`; a string concatenation is a binary operation, not a literal; a keyword argument may be
a separate node.

## 4. Write the rule

Start from the smallest rule that could work. Required fields: `id`, `languages`, `severity`,
`message`, and one pattern form (or taint block). Severity is `LOW`, `MEDIUM`, `HIGH` or
`CRITICAL`; the older `INFO`, `WARNING`, `ERROR` still load but are discouraged.

Constraints:

- Be specific. A bare `$FUNC(...)` or `$X` matches the world; anchor on a real API.
- Metavariables are uppercase.
- A pattern with a typed metavariable (`(T $X)` style, containing ` : `) must be quoted in YAML
  or the file is rejected.
- Prefer taint mode for injection classes; see the Go example in
  [worked-example.md](references/worked-example.md).

Before judging results, confirm the rule loads by running it on the test file:

```bash
semgrep --metrics=off --disable-version-check --config <rule-id>/<rule-id>.yaml <rule-id>/<rule-id>.go
```

Exit 7 is a rule schema error. Exit 2 is a pattern that does not parse in that language. Fix
those first.

## 5. Iterate until green

```bash
semgrep --metrics=off --disable-version-check --test <rule-id>/
```

Done means the output reports every test passing, with no missed lines and no incorrect lines.
Partial credit does not count. Fixes by symptom:

| Symptom | Likely fix |
|---|---|
| Matches safe code | add `pattern-not` or `pattern-not-inside`, or narrow the pattern |
| Misses a variant | add a branch to `pattern-either` |
| Reports the wrong line | `focus-metavariable` on the node that should be flagged |
| Taint does not reach the sink | a sanitizer is too broad, or a propagator is missing |
| Taint flags sanitised data | add the sanitizer |

For taint rules add `--dataflow-traces` to see the path Semgrep followed.

Excuses that do not apply here: "the pattern looks complete" (run the tests), "it matches the
vulnerable case" (the safe cases decide), "taint is overkill" (then show the pattern version
passes the sanitised and nested cases), "one test is enough", "I will tidy first", "the AST dump
is too long".

You may switch between taint and pattern mode midway if the first choice cannot go green.

## 6. Simplify, only when green

Reduce, re-running the tests after every edit and reverting any edit that breaks one:

- drop quote-style duplicates (`"x"` and `'x'` are normalised);
- drop alternatives already covered by `...`; `f(...)` covers zero or more arguments and a
  trailing `...` is optional;
- delete any `pattern-either` branch that repeats another;
- fold a family of names into one `metavariable-regex`.

## 7. Final run

Run the rule over the test file once more and read the messages. The message is one or two short
sentences, and every `$VAR` it cites must be bound by the pattern, so no raw `$VAR` appears in
the output. If one does, fix and run `--test` again.

## Report

Close with:

- the two paths;
- the `semgrep --test` result, quoted, or the statement that semgrep was missing and nothing
  ran;
- the safe forms the rule deliberately leaves alone;
- how to enable it: where the files are, wiring left to the user.

## Pitfalls

- Annotation not directly above its line, or a comment holding more than the marker.
- Patterns so generic they match everything.
- YAML mistakes: unquoted colon, wrong indentation, tabs.
- Assuming the tree shape instead of reading the dump.

Running a rule over a repository belongs to `static-analysis:semgrep`; extending the finished
rule to more languages belongs to `semgrep-rule-variant-creator:semgrep-rule-variant-creator`.
