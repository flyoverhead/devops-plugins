# Changelog

## 2026-11-11

### Added

- Skill `mutation-testing` with three jobs: campaign setup (targets, mutant count, time estimate, test command and timeout, speed-up options), survivor analysis into `$TMPDIR/mutation-testing-<repo>-N/mutation-testing-report.md` (never inside the repository; scratch notes go in the same directory), and a bug hunt that follows survivors to reproduced bugs.
- Tools: mewt and muton, gremlins (Go), mutmut (Python) and Stryker (TypeScript, only when already a devDependency). Saved results are analysed with no tool installed.
- Gates: nothing is installed; every campaign command (`init`, `mutate`, `run`, `test`, `purge`, `gremlins unleash`, `mutmut run`, `npx stryker run`) needs a shown plan with a time estimate and an explicit yes, and is not pre-approved.
- Pre-approved shell is read-only (`command -v`, `mewt|muton status|results|print`, `mutmut results`) plus `printenv TMPDIR` to place the report.
- Analysis rules: five checks before a mutant is called equivalent, unresolved as its own verdict, four impact tiers set by what the code does, statistics with denominators.
- References for setup, analysis, report layout, input formats and the bug hunt.
- `tests/validate_report.py` and `tests/smoke-test.sh` (validator self-test, optional real eval run), with pytest coverage driven by a fake `claude`; evals: a gremlins trigger, a line-coverage negative and a saved mewt campaign analysis.
