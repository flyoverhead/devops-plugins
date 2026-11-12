# devops

Personal DevOps plugins for Claude Code: Ansible, Terraform, Go, API design, security review and testing.

| Plugin | Skills | Agents |
|---|---|---|
| [`ansible`](ansible/README.md) | `role-creator`, `role-checker`, `molecule-scaffolder` | `ansible-engineer` |
| [`api`](api/README.md) | `api-designer` | `api-designer` |
| [`audit-context-building`](audit-context-building/README.md) | `audit-context-building` | `function-analyzer` |
| [`code-improver`](code-improver/README.md) | `code-improver` | `fixer`, `finalize-auditor` |
| [`differential-review`](differential-review/README.md) | `differential-review` | `adversarial-modeler` |
| [`fp-check`](fp-check/README.md) | `fp-check` | `data-flow-analyzer`, `exploitability-verifier`, `poc-builder` |
| [`git-cleanup`](git-cleanup/README.md) | `git-cleanup` | `branch-investigator` |
| [`golang`](golang/README.md) | `golang-patterns`, `golang-concurrency`, `golang-optimization`, `review`, `test`, `scaffold` | `golang-architect`, `golang-performance`, `golang-pro` |
| [`insecure-defaults`](insecure-defaults/README.md) | `audit` | `default-verifier` |
| [`mutation-testing`](mutation-testing/README.md) | `mutation-testing` | |
| [`patching-bugs`](patching-bugs/README.md) | `patching-bugs`, `reproduce-bug`, `validate-bug`, `implement-patch`, `prove-patch` | |
| [`post-patch-validation`](post-patch-validation/README.md) | `post-patch-validation` | `coverage-mapper`, `evidence-reviewer` |
| [`property-based-testing`](property-based-testing/README.md) | `property-based-testing` | |
| [`regression-hunt`](regression-hunt/README.md) | `regression-hunt`, `prepare-regression`, `hunt-regressions`, `reproduce-regression`, `replay-regression`, `adjudicate-regression`, `report-regressions` | |
| [`semgrep-rule-creator`](semgrep-rule-creator/README.md) | `semgrep-rule-creator` | |
| [`semgrep-rule-variant-creator`](semgrep-rule-variant-creator/README.md) | `semgrep-rule-variant-creator` | |
| [`sharp-edges`](sharp-edges/README.md) | `sharp-edges` | `sharp-edges-analyzer` |
| [`spec-to-code-compliance`](spec-to-code-compliance/README.md) | `spec-to-code-compliance` | `spec-compliance-checker`, `divergence-refuter` |
| [`static-analysis`](static-analysis/README.md) | `semgrep`, `sarif-parsing`, `codeql` | |
| [`terraform`](terraform/README.md) | `module-creator`, `provider-creator` | `terraform-engineer` |
| [`variant-analysis`](variant-analysis/README.md) | `variant-analysis` | `axis-sweeper` |
| [`vulnerability-triage-brocards`](vulnerability-triage-brocards/README.md) | `vulnerability-triage-brocards` | |

## Install

Clone the repository, then add it as a marketplace from inside Claude Code:

```bash
git clone https://github.com/flyoverhead/devops-plugins.git
```

```text
/plugin marketplace add ./devops-plugins
```

Then install the plugins you want:

```text
/plugin install ansible@devops
/plugin install api@devops
/plugin install audit-context-building@devops
/plugin install code-improver@devops
/plugin install differential-review@devops
/plugin install fp-check@devops
/plugin install git-cleanup@devops
/plugin install golang@devops
/plugin install insecure-defaults@devops
/plugin install mutation-testing@devops
/plugin install patching-bugs@devops
/plugin install post-patch-validation@devops
/plugin install property-based-testing@devops
/plugin install regression-hunt@devops
/plugin install semgrep-rule-creator@devops
/plugin install semgrep-rule-variant-creator@devops
/plugin install sharp-edges@devops
/plugin install spec-to-code-compliance@devops
/plugin install static-analysis@devops
/plugin install terraform@devops
/plugin install variant-analysis@devops
/plugin install vulnerability-triage-brocards@devops
```

## Using alongside another marketplace with the same plugin names

When another marketplace ships a plugin with the same name and both are enabled, both copies load. Enable only one of them; per project, in `.claude/settings.json`:

```json
{"enabledPlugins": {"ansible@devops": false, "ansible@<other-marketplace>": true}}
```

The reverse, to prefer this marketplace, goes in user-level settings (`~/.claude/settings.json`):

```json
{"enabledPlugins": {"ansible@devops": true, "ansible@<other-marketplace>": false}}
```

Repeat the pair for every plugin name both marketplaces share. `claude plugin list` shows which copy is enabled.

## Required tools

| Plugin | Needed | Optional |
|---|---|---|
| `ansible` | `ansible-core`, `ansible-lint`, `yamllint` | `molecule` with `molecule-plugins`, Docker or Podman (see the [Docker or Podman caveat](ansible/README.md#molecule-docker-or-podman)) |
| `api` | none | `spectral`, `redocly`, `swagger-cli` |
| `golang` | `go` | `gopls`, `staticcheck`, `golangci-lint`, `govulncheck`, `gosec`, `benchstat` |
| `terraform` | `terraform` | `terraform-ls`, `tflint`, `go` for providers |
| `static-analysis`, `semgrep-rule-creator`, `semgrep-rule-variant-creator` | none | `semgrep`, `codeql` |
| `mutation-testing` | none | `mewt`, `muton`, `gremlins`, `mutmut`, Stryker |
| `property-based-testing` | none | Hypothesis, fast-check, `go` |
| `patching-bugs`, `regression-hunt`, `post-patch-validation`, `code-improver` | `git`, `python3` | `gh` (not `code-improver`), the target project's own toolchain such as `go` |
| `differential-review`, `git-cleanup` | `git` | `gh` |
| `audit-context-building`, `fp-check`, `insecure-defaults`, `sharp-edges`, `spec-to-code-compliance`, `variant-analysis`, `vulnerability-triage-brocards` | none | `git`, `gh` |

`git` and `python3` are required by the script-backed plugins (`patching-bugs`,
`regression-hunt`, `post-patch-validation`, `code-improver`): their bundled Python scripts drive
git worktrees, records and scope checks, and the plugins stop without them. `git-cleanup` and
`differential-review` need `git` only. No plugin installs any tool; hooks and scripts skip any tool that is not installed, and a missing one is reported as not proven.

The molecule scaffolder targets Debian 12 and Ubuntu 24.04 by default; Debian 13 and Ubuntu 22.04 on request.

## Development

```bash
python3 -m pytest scripts/tests -q          # script tests
python3 scripts/lint_skills.py --require-claude   # skill frontmatter and structure
claude plugin validate . && claude plugin validate ansible   # manifests, per plugin
pre-commit run --all-files                  # yamllint, ansible-lint, terraform fmt, tflint, shellcheck
python3 scripts/bump_plugin.py <plugin> <version>   # bump plugin.json and marketplace.json together
```

Evals live in `<plugin>/evals/`. Run them by path; cases that write files need the write tools allowed, and ansible-lint may not be importable inside the eval sandbox:

```bash
claude plugin eval ./ansible --runs 3 --trust-plugin --scaffold --threshold 0.8 \
  --no-publish --allow-tools Write Edit Bash
```

Use `--runs 1 --case <name>` while developing.

## Licence

MIT, see [LICENSE](LICENSE).
