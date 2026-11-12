# Pattern ladder

## Contents

- [Levels](#levels)
- [Picking the starting level](#picking-the-starting-level)
- [One change per step](#one-change-per-step)
- [Abstract or keep literal?](#abstract-or-keep-literal)
- [Noise and when to stop](#noise-and-when-to-stop)
- [Which tool](#which-tool)
- [Semgrep without the network](#semgrep-without-the-network)
- [Worked climb](#worked-climb)

## Levels

| Level | What varies | Typical match count | Example (branch name into a shell) |
|---|---|---|---|
| 0 | nothing: the literal text | 1 | `rg -nF '"git fetch --depth 1 origin "+branch'` |
| 1 | names become placeholders | 3–5 | `rg -n '"git [a-z-]+ .*"\s*\+\s*\w+'` |
| 2 | structure: any shell, any string building | 10–30 | Semgrep `exec.Command($SH, "-c", $X, ...)` |
| 3 | data flow from a source to the sink | 50+ before triage | Semgrep `mode: taint` from the bundled template |

The counts are a guide for what "normal" looks like. Ten hits at level 0 means the literal is
boilerplate; one hit at level 3 means the sources or sinks are too narrow.

## Picking the starting level

| Goal | Start at |
|---|---|
| Check that a fix covered every copy of the literal code | 0 |
| Find copy-paste siblings | 1 |
| Audit one component for the bug class | 2 |
| Whole-repository assessment | 3 |

Every hunt still passes level 0 first (SKILL.md step 3): the exact pattern must hit the known
bug, or the pattern is wrong.

## One change per step

From the exact match, change **one** element, run the pattern, read every new match, then
decide on the next change. A sensible order:

1. variable and function names → metavariables or `\w+`;
2. structure → any shell binary, any string-building form (`+`, `Sprintf`, `fmt.Sprint`,
   template literal, f-string);
3. operation → sibling sinks for the same effect (`exec.CommandContext`, `os.system`, `eval`);
4. data flow → taint from real sources instead of a syntactic shape.

Changing two elements at once hides which change produced the noise. Record every step,
including the ones you reverted, as a row in the methodology table (`v1`, `v2`, …).

## Abstract or keep literal?

- Abstract a name when another name could carry the same bug.
- Keep a literal when only that value is dangerous (`"-c"`, `shell=True`, `InsecureSkipVerify: true`).
- Use `...` when the argument position does not matter.
- Use taint only when the flow itself has to be shown; a syntactic match that is obviously
  fed by a request parameter does not need it.

## Noise and when to stop

Noise = matches that are clearly not the bug (constant strings, tests, dead code).

- Past about 50 % noise: stop climbing. Revert to the previous version and widen a
  different element instead of pushing the same one higher.
- Standard filters: exclude `*_test.go`, `test/`, `tests/`, `testdata/`, `fixtures/`,
  `vendor/`, `node_modules/`; `pattern-not` the sanitised form; `pattern-not` calls whose
  dangerous argument is a string literal; skip branches behind a constant `false`.
- Tests are not candidates, but a test that asserts the unsafe behaviour is worth one line
  in the report: it shows intent.

## Which tool

| Need | Tool |
|---|---|
| Recon, counting, literals, Bash, Jinja2, CI YAML, Dockerfiles | `rg` (or `grep -rnE` if `rg` is missing) |
| Structure in Go, Python, TS/JS, HCL | `semgrep scan --metrics=off --disable-version-check --config <file>` |
| Data flow inside one function | Semgrep `mode: taint` |
| Data flow across functions | taint to find the sink side, then read the callers by hand |
| Other local clones | `rg` or the Grep tool over their paths (`git grep` in each checkout asks first) |
| Other repositories of a GitHub owner | `gh search code --owner <owner> '<literal>'` |

Semgrep taint is intraprocedural: it will not follow a value through a helper function into
another file. When the source is in one function and the sink in another, find each with its
own pattern and connect them by reading the call sites.

`gh search code` matches literal tokens, not regular expressions. Search for the most
distinctive literal (`"-c"` plus the wrapper's name, the config key, the helper function) and
narrow with `--language`, `--filename` or `--extension`.

## Semgrep without the network

- Write each rule version to `$TMPDIR/variants-<repo>-<short-sha>/vN.yaml` and run
  `semgrep scan --metrics=off --disable-version-check --config <that file> <repo root>`.
  Results go to stdout. Never `-o`, `--output` or any `--*-output=` flag (`--json-output`,
  `--sarif-output`, `--text-output`, `--junit-xml-output`, `--emacs-output`, `--vim-output`,
  `--gitlab-*-output`): each writes a file or posts to a URL. Never `--autofix`.
- For level 3, copy a bundled template from `templates/` (Go, Python, TS/JS), set the
  message to the root-cause sentence, narrow the sources and sinks to the ones the original
  uses, and add the protection Z as a `pattern-sanitizers` entry.
- `--config auto`, `--config p/<pack>` and `--config r/<rule>` download rules from the Semgrep
  registry. Before using one, tell the user that it downloads rules from semgrep.dev and
  wait for a yes. Without a yes, stay on local files.
- No semgrep on the machine: say so once, keep going with `rg`, and write the regression
  guard as an `rg` expression. Do not install it.

## Worked climb

A mirror-sync daemon builds `sh -c "cd /mirrors/x && git fetch --depth 1 origin "+branch`, with
`branch` taken from a webhook payload.

| Version | Pattern | Tool | Matches | TP | FP | Note |
|---|---|---|---|---|---|---|
| v1 | `"git fetch --depth 1 origin "+branch` | ripgrep | 1 | 1 | 0 | the literal hits only the report |
| v2 | `"git [a-z-]+ [^"]*"\s*\+` | ripgrep | 4 | 3 | 1 | `git checkout`, `git log` siblings; 1 in a test helper |
| v3 | `$SH "-c" $X` with `$X` not a string literal | semgrep | 5 | 4 | 1 | adds a `Sprintf` caller |
| v4 | any `exec.Command*` call | ripgrep | 19 | 0 new | 14 new | argv calls drown it; reverted to v3 |
| v5 | `\$\{?(branch\|ref)\}?` inside `*.sh` | ripgrep | 2 | 1 | 1 | other-layer axis: hook script |

The v4 row stays in the table: a failed widening is evidence of where the bug class ends.
