# Translation guide

## Contents

- Dump the AST first
- Metavariables and typed metavariables
- Choosing sources, sinks and sanitizers
- Imports and full paths
- Example intents

## Dump the AST first

```bash
semgrep --metrics=off --disable-version-check --dump-ast -l go <id>-go/<id>-go.go
```

Write the pattern against the tree. `a.b()` and `a().b` differ; a concatenation is a binary
operation, not a literal; a keyword argument can sit in a different node than a positional one.

## Metavariables and typed metavariables

- `$X` binds an expression, `$...ARGS` a run of arguments, `...` anything.
- Go typed form: `($R : *http.Request)` binds a declared parameter, so the test needs a whole
  function with that parameter. YAML reads ` : ` as a mapping key: quote the pattern.
- `metavariable-regex` constrains a binding (`^"(sh|bash)"$` for a string literal, quotes included).

## Choosing sources, sinks and sanitizers

Re-pick all three in the ecosystem of the target; never rename the original ones.

| Category | Ask |
|---|---|
| Sources | Which framework hands request data to a handler here? |
| Sinks | Which call actually executes, queries, opens or fetches with that data? |
| Sanitizers | Which of the target's own quoting or validation functions neutralise it? |

Per ecosystem: Flask `request.args`, Servlet `getParameter`, Go net/http `r.URL.Query()` and
`r.FormValue()`, Express `req.query` and `req.body`. Terraform and Dockerfile rules usually have
no sources: they are pattern rules on a setting or an instruction.

## Imports and full paths

A match on `exec.Command` needs `import "os/exec"`; a match on `child_process.exec` needs the
module bound by `require` or `import`. Semgrep resolves aliases for common forms, but a test
that uses an alias is worth one `ruleid` case. Write the full call path (`os.system`, not bare
`system`) wherever the language allows.

## Example intents

| Original (Python) | Go | TypeScript |
|---|---|---|
| `os.system(cmd)`, `subprocess.call(cmd, shell=True)` | `exec.Command("sh", "-c", cmd)` | `child_process.exec(cmd)`, `execSync(cmd)` |
| `flask.request.args.get(k)` | `r.URL.Query().Get(k)`, `r.FormValue(k)` | `req.query.k`, `req.params.k` |
| `shlex.quote(x)` | argv elements; `strconv.Atoi` | `execFile` with an argv array; numeric coercion |

There is no literal `os.system` in Go or TypeScript; translate the intent: a shell string built
from request data.
