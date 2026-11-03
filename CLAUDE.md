# devops

Claude Code plugin marketplace. Each plugin lives in its own top-level directory with `.claude-plugin/plugin.json`, `skills/`, optional `agents/`, `evals/`, a `README.md` and a `CHANGELOG.md`.

## Plugins

| Plugin | Skills | Agents |
|---|---|---|
| `ansible` | `role-creator`, `role-checker`, `molecule-scaffolder` | `ansible-engineer` |
| `api` | `api-designer` | `api-designer` |
| `golang` | `golang-patterns`, `golang-concurrency`, `golang-optimization`, `review`, `test`, `scaffold` | `golang-architect`, `golang-performance`, `golang-pro` |
| `terraform` | `module-creator`, `provider-creator` | `terraform-engineer` |

## Rules

- Semver bumps update `plugin.json` and `.claude-plugin/marketplace.json` together.
- CHANGELOG sections are keyed by ISO date (`## 2026-11-02`), written in the same change.
- Update the plugin README and docs with every behaviour change.
- Run `python3 scripts/lint_skills.py` before committing.
- Lint with `pre-commit run --all-files` (yamllint, ansible-lint, terraform fmt, shellcheck).
- Run evals by path: `claude plugin eval ./<plugin> --trust-plugin --scaffold --no-publish`. Cases that write files need `--allow-tools Write Edit Bash`.
- Commits: conventional (`feat`, `fix`, `chore`, `docs`, `test`), `git commit -s`, no AI attribution.
