# devops

Personal DevOps plugins for Claude Code: Ansible, Terraform, Go, API design.

| Plugin | Skills | Agents |
|---|---|---|
| [`ansible`](ansible/README.md) | `role-creator`, `role-checker`, `molecule-scaffolder` | `ansible-engineer` |
| [`api`](api/README.md) | `api-designer` | `api-designer` |
| [`golang`](golang/README.md) | `golang-patterns`, `golang-concurrency`, `golang-optimization`, `review`, `test`, `scaffold` | `golang-architect`, `golang-performance`, `golang-pro` |
| [`terraform`](terraform/README.md) | `module-creator`, `provider-creator` | `terraform-engineer` |

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
/plugin install golang@devops
/plugin install terraform@devops
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

Hooks skip any tool that is not installed.

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
