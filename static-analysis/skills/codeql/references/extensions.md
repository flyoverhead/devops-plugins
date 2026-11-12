# Data extensions

## Contents

- When to bother
- a. Existing model packs
- b. Enumerate what CodeQL already knows
- c. Map the project's API surface
- d. Ask
- e. Write the YAML
- f. Prove the models load
- Column formats

## When to bother

CodeQL models common frameworks. It does not know the project's own wrappers: a
`RequestParam()` helper, a `RunShell()` wrapper or a repository-specific DB layer hides the
source or sink, and taint stops there. This step is optional and gated: it is offered in the
plan and runs only on a yes.

## a. Existing model packs

Look before creating anything:

- in-repo `qlpack.yml` or `codeql-pack.yml` with a `dataExtensions` entry;
- standalone YAML files with a top-level `extensions:` key;
- installed model packs (`codeql resolve packs`).

Found → report them, pass them at analysis time, and skip creation.

## b. Enumerate what CodeQL already knows

Write small queries that select the remote flow sources and the sinks CodeQL recognises in
this database, into `$OUTPUT_DIR/diagnostics/`, then:

```bash
codeql query run --database="$DB" --output="$OUTPUT_DIR/diagnostics/sources.bqrs" \
  "$OUTPUT_DIR/diagnostics/sources.ql"
codeql bqrs decode --format=csv --output="$OUTPUT_DIR/diagnostics/sources.csv" \
  "$OUTPUT_DIR/diagnostics/sources.bqrs"
```

Same for sinks. The queries need a `qlpack.yml` in `diagnostics/` that depends on
`codeql/<lang>-all`.

## c. Map the project's API surface

Read the code for wrappers and classify them:

| Project code | Model | Kind |
|---|---|---|
| request parsing helpers | `sourceModel` | `remote` |
| database wrappers taking SQL text | `sinkModel` | `sql-injection` |
| shell or process wrappers | `sinkModel` | `command-injection` |
| file open/read/write by path | `sinkModel` | `path-injection` |
| template or HTML output | `sinkModel` | `html-injection` / `xss` |
| deserialisers | `sinkModel` | `unsafe-deserialization` |
| outbound HTTP clients taking a URL | `sinkModel` | `request-forgery` / `ssrf` |
| validators and escapers | `neutralModel` (or a barrier model where supported) | |
| pass-through wrappers | `summaryModel` | `taint` |

Cross-check against the CSVs from step b. Nothing missing → say coverage looks adequate and
skip to analysis.

## d. Ask

Show the proposed models and ask: create all, select some, or skip.

## e. Write the YAML

Under `$OUTPUT_DIR/extensions/` (`sources.yml`, `sinks.yml`, `summaries.yml`) with a
`qlpack.yml` that marks them as a model pack (`library: true`, `extensionTargets`,
`dataExtensions: ["*.yml"]`), so `--additional-packs "$OUTPUT_DIR/extensions"` picks them up.

```yaml
extensions:
  - addsTo:
      pack: codeql/go-all
      extensible: sinkModel
    data:
      - ["example.com/svc/sys", "Runner", true, "Exec", "", "", "Argument[1]", "command-injection", "manual"]
```

## f. Prove the models load

Analyse twice — without and with the extensions — after `codeql database cleanup "$DB"` and
with `--rerun`, and add `-vvv` once to see the extension files being loaded. The finding count
with extensions must not drop. If it is unchanged, check the log shows the files loaded
before claiming they had no effect.

## Column formats

Source model: `[package, type, subtypes, name, signature, ext, output, kind, provenance]`.
Sink model: `[package, type, subtypes, name, signature, ext, input, kind, provenance]`.
Summary model: `[package, type, subtypes, name, signature, ext, input, output, kind, provenance]`.
Neutral model: `[package, type, name, signature, kind, provenance]`.

Language quirks:

- Java: `subtypes` is `True`/`False` (capitalised); a method parameter as a source is
  `Parameter[N]` (ranges like `Parameter[0..2]`); `signature` is required, e.g.
  `(String,int)`.
- Other languages use `Argument[N]` and lowercase `true`/`false` in YAML where booleans are
  plain YAML; follow the examples shipped in the `codeql/<lang>-all` pack's `ext/` directory
  for the exact package and type spelling.
