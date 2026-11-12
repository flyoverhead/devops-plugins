# semgrep-rule-variant-creator

Ports an existing Semgrep rule to other languages. Each language is an independent cycle:
applicability verdict, test file first, AST-guided rule, `semgrep --test` until green.

```text
/plugin install semgrep-rule-variant-creator@devops
```

## Usage

```text
/semgrep-rule-variant-creator:semgrep-rule-variant-creator sast/flask-os-system/flask-os-system.yaml go typescript
```

Or in plain words: "port this rule to Go and TypeScript", "same detection for our Terraform".

## Output

One directory per applicable language, beside the original rule unless you name another place:

| File | Name | Holds |
|---|---|---|
| Rule | `<original-id>-<language>/<original-id>-<language>.yaml` | the ported rule |
| Tests | same directory and basename, target-language extension | `ruleid` and `ok` cases |

The port keeps the original's mode and intent. Its `id` and `languages` change, and metadata
gains `original-rule` and `ported-from`. A language where the bug class does not exist gets no
directory; a language Semgrep cannot parse is reported as such, not as not applicable.

The final message leads with the outcome per language and records the Semgrep version used. A
port is a candidate for review: the same cycle wrote rule and tests, so a green run shows they
agree, not that the rule is complete.

## Safety

- Every `semgrep` call runs with `--metrics=off --disable-version-check` on local files; no
  registry configs, no `--validate`, no login. `semgrep show supported-languages` rejects
  `--disable-version-check`, so it runs with `SEMGREP_ENABLE_VERSION_CHECK=0` instead.
- No `-o`/`--output`, no `--*-output=` flag, no `--autofix` and no remote `--config http(s)://`:
  results go to stdout and configs are local paths.
- The original rule and its tests are never edited.
- Semgrep must already be installed. Without it the variants are still written, the report says
  nothing was validated, and nothing is installed.

## Related

- Write a new rule from a bug description: `semgrep-rule-creator:semgrep-rule-creator`.
- Run rules over a repository: `static-analysis:semgrep`.

## Evals

`evals/` holds a trigger case, a Python-to-Go-and-TypeScript outcome case that needs a local
`semgrep`, and a negative case for new-rule requests.

## Tests

```bash
python3 -m pytest semgrep-rule-variant-creator/tests -q
```
