# semgrep-rule-creator

Writes one custom Semgrep rule and proves it. The test file comes first, with `ruleid` and `ok`
cases; the AST is dumped to see how the target code parses; the rule is then iterated until
`semgrep --test` reports every case passing.

```text
/plugin install semgrep-rule-creator@devops
```

## Usage

```text
/semgrep-rule-creator:semgrep-rule-creator request data reaching sh -c in Go handlers
```

Or in plain words: "write a semgrep rule that flags `yaml.load` on user input", "how would I
build a rule so CI catches this pattern?".

## Languages

Go, Python, Bash, TypeScript, Terraform (HCL), YAML (Ansible, CI configs), Dockerfile. Text that
Semgrep has no parser for falls back to `languages: generic`.

## Output

```text
<rule-id>/
  <rule-id>.yaml     one rule
  <rule-id>.<ext>    test file
```

Written under the directory you name, else the current one. The skill reports the paths, the
`semgrep --test` result and the safe forms the rule leaves alone. Enabling the rule in your own
Semgrep config or CI is left to you.

## Safety

- Every `semgrep` call runs with `--metrics=off --disable-version-check`; no registry configs,
  no `--validate`, no login.
- No `-o`/`--output`, no `--*-output=` flag, no `--autofix` and no remote `--config http(s)://`:
  results go to stdout and configs are local paths.
- Semgrep must already be installed. If it is not, the rule and tests are still written, the
  report says nothing was tested, and nothing is installed.
- Test files hold placeholders only, never real secrets.

## Related

- Run existing rules over a repository: `static-analysis:semgrep`.
- Port a finished rule to other languages: `semgrep-rule-variant-creator:semgrep-rule-variant-creator`.

## Evals

`evals/` holds a trigger case, an outcome case that needs a local `semgrep`, and a negative case
for scan requests.

## Tests

```bash
python3 -m pytest semgrep-rule-creator/tests -q
```
