# Changelog

## 2026-11-11

### Added

- Skill `patching-bugs` (manual start only): coordinates one bug from report to a proven local fix. Read-only look at the checkout, a run directory under `$TMPDIR`, guidance files copied from the baseline commit's objects, an approval gate before any project code runs (an up-front yes counts only when it explicitly allows running the project's commands; the plan is shown either way), a preflight build, intake into `finding.json` with a `repair_scope`, then fresh agents for reproduce, blind validate, up to three patch-then-prove attempts, an optional `regression-hunt` pass, and `report.md` plus a maintainer handoff for READY results. Verdicts: `NOT_REPRODUCED`, `NOT_READY`, `READY_WITH_CONCERNS`, `READY`.
- Stage skills `reproduce-bug`, `validate-bug`, `implement-patch` and `prove-patch`, each usable on its own and each run by a separate agent so reproducer ≠ validator and patcher ≠ prover; identity strings are recorded and compared.
- Scripts (Python 3 standard library, no project or dependencies): `records.py` (`check [--before-repair]`, `manifest` refusing step directories inside a git work tree or without a run.json, `guidance`), `markers.py` (`loaded`, `case`, `reached`, `check-stdout`), `arms.py` (`run`: baseline / patched / reverted check in temporary detached worktrees kept outside the run directory, with nested `{scratch}` directories and clean-up limited to its own worktree entries; `cases`: planned runs on baseline and patched trees with `{tree}` and `{scratch}` placeholders), `verdict.py` (verdict precedence, three-arm result recomputed from the arm receipts, per-case and project-check judgement, proof-wide gaps, claim breadth).
- Reference pages: record fields, agent briefs, report layout, stack recipes with the harness contract, proof judging rules.
- Tests: pytest suites for every script, an end-to-end run over a demo repository, and plugin structure tests; `tests/run-all.sh`.
- Evals: a reproduce-first trigger, a plain-fix negative, an approval-gate outcome where "fix and commit it" runs nothing without a yes, an up-front-yes outcome where the plan is still shown before the first build, and `outcome-go-path-escape`, a Go snippet store whose `../` names escape the vault directory, carried from reproduction to one signed-off local commit and a three-arm proof without a push.
- Every documented `git diff`, `git show` and patch-showing `git log` passes `--no-ext-diff --no-textconv`.
