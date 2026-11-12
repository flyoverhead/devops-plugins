# Changelog

## 2026-11-11

### Added

- Skill `semgrep-rule-variant-creator`: ports a Semgrep rule to further languages, one independent cycle per language. Four phases each: applicability verdict (`APPLICABLE`, `APPLICABLE_WITH_ADAPTATION`, `NOT_APPLICABLE`, kept apart from "Semgrep cannot analyze"), tests first, AST-guided translation, `semgrep --test` with a three-round fix limit.
- Local-only by construction: every call carries `--metrics=off --disable-version-check`; no `--validate`, `--config auto`, registry configs, login or install; the original rule and tests are never edited.
- `## Limits`: no `-o`/`--output`, `--*-output=`, `--autofix` or remote `--config http(s)://`. The version probe is `semgrep --metrics=off --disable-version-check --version`; `semgrep show supported-languages` rejects `--disable-version-check` and runs with `SEMGREP_ENABLE_VERSION_CHECK=0`.
- References: applicability analysis, workflow mechanics, translation guide.
- Evals: trigger, `semgrep --test` outcome for Go and TypeScript, new-rule negative. Write and Edit exemptions are anchored at both ends and refuse `..` segments.
- `tests/test_plugin.py`: frontmatter, tool list, Limits block, manifest sync, grader anchoring.
