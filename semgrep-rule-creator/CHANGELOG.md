# Changelog

## 2026-11-11

### Added

- Skill `semgrep-rule-creator`: writes one custom Semgrep rule test-first for Go, Python, Bash, TypeScript, Terraform (HCL), YAML, Ansible and Dockerfile code. Seven steps: analyse (taint or pattern), annotated test file, AST dump, rule, `semgrep --test` until green, simplification, final run. Output is one directory holding the rule and its test file.
- Local-only by construction: every call carries `--metrics=off --disable-version-check`; `--validate`, `--config auto`, registry configs, `semgrep login` and `semgrep ci` are not used; semgrep is never installed, and a missing binary is reported instead of a pass.
- `## Limits`: no `-o`/`--output`, `--*-output=`, `--autofix` or remote `--config http(s)://`.
- References: syntax quick reference and a tested Go worked example (request data reaching `sh -c`).
- Evals: trigger, `semgrep --test` outcome and a scan-request negative. Write and Edit exemptions are anchored at both ends and refuse `..` segments.
- `tests/test_plugin.py`: frontmatter, tool list, Limits block, manifest sync, grader anchoring.
