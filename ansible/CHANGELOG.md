# Changelog

## 2026-11-12

### Changed

- `molecule-scaffolder` and `role-checker`: a `## Limits` section forbids `--output` and `--ext-diff` on the pre-allowed `git diff`/`git show`.
- `molecule-scaffolder` and `role-checker`: `## Limits` also forbids `--textconv`; every documented `git diff`/`git show` passes `--no-ext-diff --no-textconv`.
- `role-checker`: `python3 -c` is no longer pre-allowed. The restructure verify step compares old and new defaults with the bundled `scripts/yaml_equal.py`, pre-allowed by its exact path.
- Agent `ansible-engineer`: read-only, with tools limited to Read, Grep, Glob, `ansible-lint`, `yamllint`, `ansible-playbook --syntax-check` and `git log`; `--check` and real runs are handed to the user. A `## Limits` section names the forbidden flags.

## 2026-11-03

- Skill `role-creator`: Ansible roles in the classic layout (`install`/`configure`/`service` task files, `meta/argument_specs.yml`, role-prefixed variables) with sentence-case task names, `true`/`false` booleans and FQCN modules, for package, binary or container installs, linted with the ansible-lint `production` profile.
- Skill `role-checker`: checks a role against the same rules, auto-fixes booleans, name casing and `<file> |` prefixes, handler names (keeping the old name as a `listen:` alias) and FQCN, rewrites `when: x == true` to `when: x` only for variables with a boolean default, asks before writing `x | bool` (it changes results for string values), reports the rest with `path:line`, and restructures stage-file roles (`detect.yml`, `update.yml`, `config.yml`, `*_installed` / `*_update` facts) into the recommended `install`/`configure`/`service` layout after a confirmed plan, keeping every variable and default.
- Skill `molecule-scaffolder`: a `default` molecule scenario for an existing role on systemd-capable containers built from pinned official images (Debian 12 and Ubuntu 24.04 by default; Debian 13 and Ubuntu 22.04 on request), running on Docker or Podman (`CONTAINER_ENGINE=podman`), with prepare, converge, idempotence and `ansible.builtin.assert` verify steps, `requirements.yml` when the role needs collections, a GitHub Actions workflow, and a check-mode and idempotence audit of the role's tasks. Stops on stage-file roles and points to `role-checker`.
- Shared rules reference `role-creator/references/RULES.md`.
- Agent `ansible-engineer`.
- Hook `guard-playbook.sh` (before `Bash`): blocks `ansible-playbook` unless every invocation in the command carries `--check`, `-C` (also inside grouped short flags), `--syntax-check`, `--list-tasks`, `--list-hosts` or `--list-tags`. It finds invocations after `;`, `&&`, `||`, pipes and newlines, in subshells, `$( )`, backticks and `bash -c`, and behind `sudo`, `env`, `nohup`, `time`, `timeout`, `nice`, `exec`, `command`, `xargs`, `uv run`, `poetry run`, `pipx run` and `pipenv run`; shell comments do not count as flags.
- Hooks `lint-yaml.sh` and `lint-ansible.sh` (after `Edit`/`Write`): yamllint on `.yml`/`.yaml` files and ansible-lint on those that belong to Ansible content, using the project's `.yamllint` and `.ansible-lint` when present; findings are returned to the model.
- Hook `session-start.sh`: reports the installed ansible-core and Python versions.
