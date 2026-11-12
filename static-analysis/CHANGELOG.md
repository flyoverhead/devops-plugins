# Changelog

## 2026-11-11

### Added

- Skill `semgrep`: local Semgrep audit with language detection by glob, public registry packs (`p/default`, `p/secrets`, language and framework packs) pre-selected, broader packs and third-party rule repositories as unticked opt-ins, a hard approval gate listing every download, `--metrics=off` on every call, run-all and important-only modes, and merged SARIF under `$TMPDIR`.
- Scripts `run-scans.sh` (validated plan runner, bash 3.2 compatible, records success, partial, failed, skipped, coverage and oversized files in `scans.json`), `merge_sarif.py` (dedupe on rule, file and line; refuses a zero-finding merge when the important-only filter and SARIF disagree) and `important-filter.jq`.
- Skill `sarif-parsing`: severity resolution per SARIF 2.1.0 §3.27.10 (rule-level levels, guarded `ruleIndex`, CodeQL extension rule tables), a jq module and query cookbook, the stdlib `sarif_helpers.py` (filters, fingerprints, dedupe, merge, diff, CSV, summary), two fixtures, and a GitHub Actions gate with `upload-sarif`.
- Skill `codeql`: licence gate before anything runs, one plan gate before builds and pack downloads, existing-database discovery, a logged build ladder with the macOS arm64 exit-137 sub-ladder, a database quality gate, data-extension models, explicit run-all and important-only suites with official and community packs, threat models, and output under `$TMPDIR`. `codeql` is not pre-approved, so every call asks.
- Scripts `find_databases.sh`, `build_log.sh`, `check_db_quality.py`, `generate_suite.sh`, `verify_query_suite.py` and `important-only.jq`.
- Pytest suite under `tests/` with stubbed `semgrep` and `codeql`; tests that need the real binaries are skipped when they are missing.
- Evals: trigger, outcome and negative cases for the three skills, including the semgrep and CodeQL plan gates, the CodeQL licence stop and a local open-source checkout without `gh`. Outcome cases carry no-edit graders; the CodeQL outcomes also no-write graders exempting only `$TMPDIR/codeql-<repo>_N/`, anchored at both ends. Skill regexes are scoped `(?:static-analysis:)?<skill>`.
- `semgrep`: the only pre-allowed direct call is `semgrep --version --disable-version-check`, and the skill forbids `-o`/`--output`, `--*-output=` and `--autofix` on it.
