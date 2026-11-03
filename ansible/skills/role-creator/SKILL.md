---
name: role-creator
description: Creates Ansible roles in the classic upstream layout — install/configure/service task files, meta/argument_specs.yml, role-prefixed variables, sentence-case task names, true/false booleans and FQCN modules, passing the ansible-lint production profile — for package, binary or container installs on Debian/Ubuntu, RHEL or Windows. Use when asked to write, generate or automate a service with an Ansible role. Not for checking an existing role — use ansible:role-checker; not for molecule tests — use ansible:molecule-scaffolder.
argument-hint: "[service-name] [platform=debian|rhel|windows|multi-os] [install-method=package|binary|container]"
effort: high
paths: ["**/roles/**"]
allowed-tools: Bash(ansible-lint:*) Bash(yamllint:*) Bash(pre-commit run:*) Bash(ansible-playbook --syntax-check:*) Bash(mkdir:*) Bash(ls:*) Bash(date +%F) Bash(git config user.name) Read Write Edit Glob Grep
---

# Ansible role creator

Role to create: $ARGUMENTS

Resolve any path the user gives (such as `roles/<role>`) from the working directory of their
repository, not from the plugin's install location.

The rules every file follows are in [references/RULES.md](references/RULES.md). Read it
before writing; it is the single source and this skill does not repeat it.

## Checklist

Copy and track:

- [ ] 1. Decide the install method, platform and version ([Inputs](#inputs-to-settle-first)).
- [ ] 2. Read [references/RULES.md](references/RULES.md) and the templates for the chosen method in [references/ROLES.md](references/ROLES.md).
- [ ] 3. Write `defaults/main.yml` and `vars/<os_family>.yml`; every variable starts with `<role>_`.
- [ ] 4. Write `tasks/install.yml`, `tasks/configure.yml`, `tasks/service.yml`, optional `tasks/assert.yml`, then `tasks/main.yml` and `handlers/main.yml`.
- [ ] 5. Write `meta/main.yml`, `meta/argument_specs.yml` (one option per default) and `templates/*.j2`.
- [ ] 6. Write `README.md` and `CHANGELOG.md` (`## <date +%F>`).
- [ ] 7. Run the [Lint gate](#lint-gate) and repeat until it reports no findings.
- [ ] 8. Self-check against [Before reporting](#before-reporting).
- [ ] 9. Report the file tree and lint result; tell the user to run `/ansible:molecule-scaffolder` next for the `molecule/default/` scenario, and `ansible:role-checker` to review it.

## Inputs to settle first

| Decision | Options | Default when unstated |
|---|---|---|
| Install method | `package` (distribution or vendor apt/dnf repo), `binary` (release archive), `container` (Docker or Podman) | ask |
| Platform | Debian/Ubuntu, RHEL family, Windows, multi-OS | ask |
| Version | apt/dnf candidate or pin, release tag, image tag | pin the latest stable release and say which |

Ask only for what the prompt leaves open, in one numbered question. When method and
platform are given, start writing.

## Layout

```
roles/<role>/
├── defaults/main.yml
├── vars/<os_family>.yml      # Debian.yml, RedHat.yml, Windows.yml; skip when nothing differs
├── meta/main.yml
├── meta/argument_specs.yml
├── tasks/
│   ├── main.yml              # include_vars, then include_tasks per stage, each tagged
│   ├── assert.yml            # optional
│   ├── install.yml           # version-aware; binary installs probe --version here
│   ├── configure.yml
│   └── service.yml
├── handlers/main.yml
├── templates/
├── README.md
└── CHANGELOG.md
```

There is no `detect.yml`, `update.yml` or `config.yml`. Updating is bumping
`<role>_version` and re-running. `molecule/default/` is added afterwards by
`ansible:molecule-scaffolder`; do not write it here.

## Install methods

| Method | `install.yml` | `service.yml` |
|---|---|---|
| `package` | repo + key when needed; `ansible.builtin.apt` / `ansible.builtin.dnf` with `state: present` and the pinned version | start and enable the packaged unit |
| `binary` | `--version` probe (`changed_when: false`, `check_mode: false`), user, then download with checksum to a versioned path, unpack, copy — only when the version differs | unit template, flush handlers, start and enable |
| `container` | pull the pinned image; engine from `<role>_container_engine` (`docker` default, or `podman`) | `community.docker.docker_container` or `containers.podman.podman_container`, `state: started` |

## Lint gate

Lint every file under the role, including untracked ones:

1. If the repo has `.pre-commit-config.yaml`: `pre-commit run --files <every file under roles/<role>>`.
2. Otherwise run the linters directly:
   - `ansible-lint roles/<role>` when the repo has `.ansible-lint`, else
     `ansible-lint --profile production roles/<role>`;
   - `yamllint roles/<role>` when the repo has `.yamllint` (without one, ansible-lint's
     built-in yamllint pass covers `yaml[truthy]`).
3. `ansible-playbook --syntax-check` on a playbook that applies the role, when the repo
   has one.

Fix findings in the code, never with `skip_list` or a blanket `# noqa`. If a linter is
not installed, say so and do not report the role as validated.

## Before reporting

ansible-lint does not catch these (see [RULES.md](references/RULES.md#what-ansible-lint-does-not-catch)); check them yourself:

- no task or handler name has a `<file> |` prefix;
- `meta/argument_specs.yml` exists and lists every variable in `defaults/main.yml` with
  the same default;
- facts are read as `ansible_facts['…']`;
- every read-only probe has `changed_when: false` and `check_mode: false`;
- download paths include the version.

## References

- [references/RULES.md](references/RULES.md) — the rules, with do/don't examples and the
  lint config. Shared with `ansible:role-checker` and `ansible:molecule-scaffolder`.
- [references/ROLES.md](references/ROLES.md) — lint-clean templates for every file and
  install method, README and CHANGELOG.
- [references/CREATION.md](references/CREATION.md) — per-file contents and `meta/` fields;
  open it whenever you are unsure what a file needs.
