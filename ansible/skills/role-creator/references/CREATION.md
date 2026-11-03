# What each role file contains

The content contract for every file the role-creator checklist writes, in writing order.
Templates are in `ROLES.md`; the rules are in `RULES.md`.

## Contents

- [Planning](#planning)
- [defaults/main.yml](#defaultsmainyml)
- [vars/<os_family>.yml](#varsos_familyyml)
- [tasks/install.yml](#tasksinstallyml)
- [tasks/configure.yml](#tasksconfigureyml)
- [tasks/service.yml](#tasksserviceyml)
- [tasks/assert.yml](#tasksassertyml)
- [tasks/main.yml](#tasksmainyml)
- [handlers/main.yml](#handlersmainyml)
- [meta/main.yml](#metamainyml)
- [meta/argument_specs.yml](#metaargument_specsyml)
- [templates/](#templates)
- [README.md and CHANGELOG.md](#readmemd-and-changelogmd)

## Planning

Settle these before writing; they decide which templates apply.

| Item | Values |
|---|---|
| Service name and role name | role name matches `^[a-z][a-z0-9_]*$` and is the variable prefix |
| Install method | `package`, `binary`, `container` |
| Platforms | Debian/Ubuntu; RHEL family; Windows |
| Version | the pinned release; read the upstream release page for the current stable one and say which you pinned |
| Config files | which files the service reads, and which settings become variables |
| Service | systemd unit shipped by the package, written by the role (binary), or the container itself |

## defaults/main.yml

- Every user-facing setting, prefixed `<role>_`, with a working default.
- `<role>_version` pinned to a real release (binary, container) or empty / pinned
  package version (package).
- Booleans `true`/`false`; lists default to `[]`, not `null`.
- No secrets; a password variable defaults to an empty string and is required when the
  feature that uses it is enabled (checked in `assert.yml`).

## vars/<os_family>.yml

- Values that differ per platform and that users should not override: package names,
  config paths, service names.
- One file per supported family, named after `ansible_facts['os_family']`.
- Skip `vars/` entirely for a single-platform role with nothing platform-specific.

## tasks/install.yml

- `package`: optional repository and key, then the package with `state: present` and the
  pinned version when one is given. `ansible.builtin.deb822_repository` needs
  `python3-debian` on the target; install it with `ansible.builtin.apt` first.
- `binary`: probe the installed `--version` (`changed_when: false`, `check_mode: false`,
  `failed_when: false`), system user and group, then a block that downloads with a
  checksum to a versioned path, unpacks and copies the binary, guarded by
  `installed != wanted`. Unpack and copy carry `when: not ansible_check_mode`, because
  `get_url` does not download in check mode.
- `container`: pull the pinned image with the engine chosen by `<role>_container_engine`
  (`docker` default, `podman` alternative).
- Notifies the restart handler when the installed artifact changes.

## tasks/configure.yml

- Directories with owner, group and mode.
- Config files from templates, with `validate:` when the service has a config checker.
- Every change notifies a handler (`Restart <service>` or `Reload <service>`); no task
  restarts the service directly.

## tasks/service.yml

- Binary installs: template the systemd unit and notify the restart handler.
- `ansible.builtin.meta: flush_handlers`, so pending restarts happen before the next task.
- Start and enable: `ansible.builtin.systemd_service` with `state: started` and
  `enabled: true`. For binary installs, this task and the restart handler skip in check
  mode while the binary is not installed yet, since the unit does not exist; containers: the container module with `state: started` and a restart
  policy.

## tasks/assert.yml

Optional. Only checks argument_specs cannot express: supported platform, values that
depend on each other, a required secret when a feature is on. Each is an
`ansible.builtin.assert` with `fail_msg` and `quiet: true`.

## tasks/main.yml

`include_vars` for the platform (when `vars/` exists), then `include_tasks` for `assert`,
`install`, `configure` and `service` in that order, each tagged with the role name and
`<role>_<stage>` both on the include and through `apply:`.

## handlers/main.yml

One handler per service action the tasks notify: `Restart <service>` (with
`daemon_reload: true` when the role writes the unit), `Reload <service>` when supported.
Handler names are sentence case and match the `notify:` strings exactly.

## meta/main.yml

| Field | Value |
|---|---|
| `role_name` | the role directory name |
| `author` | from other roles in the repo, else `git config user.name` |
| `description` | one line: what the role installs and how |
| `license` | the repo's licence (`MIT` when the repo has none) |
| `min_ansible_version` | read from other roles in the repo; `'2.19'` for a new repo |
| `platforms` | the releases the role is tested on: Debian `bookworm`, `trixie`; Ubuntu `noble`; EL `9` |
| `galaxy_tags` | lowercase letters and digits only |
| `dependencies` | `[]`; prefer documenting a required role over a hard dependency |

## meta/argument_specs.yml

- `argument_specs.main` with `short_description`, `description` and `options`.
- One option per variable in `defaults/main.yml`, same name, same `default`, a `type`
  (`str`, `int`, `bool`, `list`, `dict`, `path`), `elements` for lists and `choices` for
  closed sets.
- `required: true` only for inputs with no default.

## templates/

- First line `{{ ansible_managed | comment }}` (use the comment style of the target
  format: `comment('c')` for C-style, `comment('xml')` for XML).
- `.j2` extension, named after the destination file.
- No logic that belongs in variables; loops over role variables are fine.

## README.md and CHANGELOG.md

- README in English: purpose, requirements, variables table generated from
  `argument_specs.yml`, example playbook, tags.
- CHANGELOG: `# Changelog`, then `## <today's ISO date>` with the initial features. Later
  changes add a new dated section on top.
