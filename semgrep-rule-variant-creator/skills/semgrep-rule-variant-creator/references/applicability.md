# Applicability

## Contents

- Three questions
- Verdicts
- Which classes port
- Can Semgrep read it
- Worked example: a Python subprocess rule

## Three questions

1. Does the bug class exist in the target language and its usual frameworks?
2. For each source, sink and sanitizer of the original, is there an equivalent construct?
3. Would the port flag real risk, or only a lookalike of the original syntax?

## Verdicts

| Verdict | Meaning |
|---|---|
| `APPLICABLE` | Direct translation; only syntax changes |
| `APPLICABLE_WITH_ADAPTATION` | The class exists, but the APIs differ, extra patterns or context are needed |
| `NOT_APPLICABLE` | The class is absent, no equivalent construct exists, or the port would be meaningless |

Judge the specific construct. A C `strcpy`/`strncpy` rule (CWE-676) does not port to Python
because both halves of the pair are absent; that Python's `ctypes.memmove` can still overflow is
a different rule, not a port.

## Which classes port

| Tendency | Examples |
|---|---|
| Usually port | SQL injection, command injection, path traversal, SSRF, XSS |
| Depends on the construct | deserialization, crypto misuse, races, integer overflow |
| Usually language-bound | memory corruption, PHP type juggling, JS prototype pollution, GIL issues |

For a library-specific original, start with the standard library or the most popular library of
the target. Further libraries are separate rules.

## Can Semgrep read it

Different question from the verdict, answered by running Semgrep.

```bash
SEMGREP_ENABLE_VERSION_CHECK=0 semgrep show supported-languages
semgrep --metrics=off --disable-version-check --dump-ast -l <key> probe.<ext>
```

- Perl has no frontend; only `generic` and regex work, and taint silently does nothing.
- Elixir's parser is Pro-only since 1.51.0.

Report these as "Semgrep cannot analyze". They are not `NOT_APPLICABLE`.

## Worked example: a Python subprocess rule

Original: request data reaches `os.system(...)` or `subprocess.call(..., shell=True)`.

```text
TARGET: Go
VERDICT: APPLICABLE_WITH_ADAPTATION
REASONING: Shell injection exists in Go, but only when a shell is started explicitly. There is
  no os.system, and exec.Command alone does not use a shell.
ADAPTATIONS_NEEDED: sink is exec.Command("sh", "-c", $CMD) with a metavariable-regex on the
  shell name; sources are net/http accessors.
EQUIVALENT_CONSTRUCTS:
  flask.request.args.get(...) -> r.URL.Query().Get(...), r.FormValue(...)
  os.system(...) -> exec.Command("sh", "-c", ...)
  shlex.quote(...) -> no stdlib twin; argv elements and strconv.Atoi are the safe forms
```

```text
TARGET: Java
VERDICT: APPLICABLE_WITH_ADAPTATION
REASONING: Runtime.exec with a single string does not use a shell either. The risk appears with
  new String[]{"sh", "-c", cmd}.
EQUIVALENT_CONSTRUCTS:
  flask.request.args.get(...) -> $REQ.getParameter(...)
  os.system(...) -> Runtime.getRuntime().exec(new String[]{"sh","-c",...}), ProcessBuilder("sh","-c",...)
```
