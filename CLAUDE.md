# devops

Claude Code plugin marketplace. Each plugin lives in its own top-level directory with `.claude-plugin/plugin.json`, `skills/`, optional `agents/`, `evals/`, a `README.md` and a `CHANGELOG.md`.

## Plugins

| Plugin | Skills | Agents |
|---|---|---|
| `ansible` | `role-creator`, `role-checker`, `molecule-scaffolder` | `ansible-engineer` |
| `api` | `api-designer` | `api-designer` |
| `audit-context-building` | `audit-context-building` | `function-analyzer` |
| `code-improver` | `code-improver` | `fixer`, `finalize-auditor` |
| `differential-review` | `differential-review` | `adversarial-modeler` |
| `fp-check` | `fp-check` | `data-flow-analyzer`, `exploitability-verifier`, `poc-builder` |
| `git-cleanup` | `git-cleanup` | `branch-investigator` |
| `golang` | `golang-patterns`, `golang-concurrency`, `golang-optimization`, `review`, `test`, `scaffold` | `golang-architect`, `golang-performance`, `golang-pro` |
| `insecure-defaults` | `audit` | `default-verifier` |
| `mutation-testing` | `mutation-testing` | |
| `patching-bugs` | `patching-bugs`, `reproduce-bug`, `validate-bug`, `implement-patch`, `prove-patch` | |
| `post-patch-validation` | `post-patch-validation` | `coverage-mapper`, `evidence-reviewer` |
| `property-based-testing` | `property-based-testing` | |
| `regression-hunt` | `regression-hunt`, `prepare-regression`, `hunt-regressions`, `reproduce-regression`, `replay-regression`, `adjudicate-regression`, `report-regressions` | |
| `semgrep-rule-creator` | `semgrep-rule-creator` | |
| `semgrep-rule-variant-creator` | `semgrep-rule-variant-creator` | |
| `sharp-edges` | `sharp-edges` | `sharp-edges-analyzer` |
| `spec-to-code-compliance` | `spec-to-code-compliance` | `spec-compliance-checker`, `divergence-refuter` |
| `static-analysis` | `semgrep`, `sarif-parsing`, `codeql` | |
| `terraform` | `module-creator`, `provider-creator` | `terraform-engineer` |
| `variant-analysis` | `variant-analysis` | `axis-sweeper` |
| `vulnerability-triage-brocards` | `vulnerability-triage-brocards` | |

## Rules

- Semver bumps update `plugin.json` and `.claude-plugin/marketplace.json` together.
- CHANGELOG sections are keyed by ISO date (`## 2026-11-02`), written in the same change.
- Update the plugin README and docs with every behaviour change.
- Run `python3 scripts/lint_skills.py` before committing.
- Lint with `pre-commit run --all-files` (yamllint, ansible-lint, terraform fmt, shellcheck).
- Run evals by path: `claude plugin eval ./<plugin> --trust-plugin --scaffold --no-publish`. Cases that write files need `--allow-tools Write Edit Bash`.
- Commits: conventional (`feat`, `fix`, `chore`, `docs`, `test`), `git commit -s`, no AI attribution.
- No GitHub write (comment, review, push, PR) without an explicit yes.
- `gh api` is never in `allowed-tools`.
- `Bash(git:*)`, `Bash(git *)` and `Bash(git -C:*)` are never pre-allowed, nor is `git grep`; every agent has a scoped `tools:` line.
- Documented `git diff`, `git show` and patch-showing `git log` calls carry `--no-ext-diff --no-textconv` (lint rule `S11-no-ext-diff`).
