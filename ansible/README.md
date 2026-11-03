# ansible

Ansible roles in the classic upstream layout, a checker that fixes and restructures them, and a molecule scaffolder.

```text
/plugin install ansible@devops
```

## Skills

| Skill | Use it to |
|---|---|
| `role-creator` | Write a role: `install`/`configure`/`service` task files, `meta/argument_specs.yml`, role-prefixed variables, sentence-case task names, `true`/`false` booleans, FQCN modules |
| `role-checker` | Check a role against the same rules, auto-fix cosmetic issues, report the rest as `path:line`, restructure stage-file roles (`detect.yml`/`update.yml`/`config.yml`) into the recommended layout after a confirmed plan |
| `molecule-scaffolder` | Add a `default` molecule scenario (Debian 12 and Ubuntu 24.04 by default; Debian 13 and Ubuntu 22.04 on request; Docker or Podman containers), a GitHub Actions workflow and a check-mode and idempotence audit |

## Agent

`ansible-engineer`: inventory layout, role boundaries, variable precedence and rollout design across many hosts.

## Hooks

| Event | Hook | Behaviour |
|---|---|---|
| Before `Bash` | `guard-playbook.sh` | Blocks `ansible-playbook` unless every invocation in the command has `--check`, `-C` (also in `-vC`, `-CD`), `--syntax-check`, `--list-tasks`, `--list-hosts` or `--list-tags`. Finds invocations after `;`, `&&`, `||`, pipes, in subshells, `$( )`, backticks, `bash -c` and behind wrappers such as `sudo`, `env`, `timeout`, `xargs`, `uv run`. A flag in a shell comment does not count. Needs `jq` or `python3`; without either it warns and allows. |
| After `Edit`/`Write` | `lint-yaml.sh` | yamllint on `.yml`/`.yaml` files with the project's `.yamllint`, or a built-in config. Skips `.git/`, `.venv/`, `.cache/` and `molecule/`. |
| After `Edit`/`Write` | `lint-ansible.sh` | ansible-lint on `.yml`/`.yaml` files that belong to Ansible content (under `tasks/`, `handlers/`, `defaults/`, `vars/`, `meta/`, `playbooks/`, or next to `roles/`, `site.yml`, `playbook.yml`), with the project's `.ansible-lint` or `--profile production`. |
| Session start | `session-start.sh` | Adds the installed ansible-core and Python versions to the context. |

Lint findings exit with code 2 so the model sees them. A missing linter is skipped silently.

Known limits of the guard: it also blocks `ansible-playbook --version`, `--help` and the text of a here-document that starts a line with the command, and it does not look inside `ssh host '…'`. Command names held in variables or substitutions (`$a`, `$(which ansible-playbook)`, `$SHELL -c`) are not resolved.

## Required tools

`ansible-core`, `ansible-lint`, `yamllint`. For the molecule scaffolder: `molecule` with `molecule-plugins[docker]`, and Docker or Podman.

## Molecule: Docker or Podman

The scenario uses `driver.name: ${CONTAINER_ENGINE:-docker}`:

```bash
molecule test                            # Docker
CONTAINER_ENGINE=podman molecule test    # Podman, needs molecule-plugins[podman]
```

The switch is not named `MOLECULE_DRIVER`: molecule resolves the driver before it expands `MOLECULE_*` variables. The Podman path passes `molecule syntax`; a full Podman run is not verified. Docker without `cgroupns: host` and rootless Podman need a cgroup v2 host, and rootless Podman also needs cgroup v2 delegation.
