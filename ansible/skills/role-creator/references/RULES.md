# Ansible rules

The single source of the rules every skill in this plugin writes and checks. Classic
upstream style: the official Ansible documentation and the ansible-lint `production`
profile, with no local exceptions.

## Contents

- [Rules](#rules)
- [Names](#names)
- [Booleans and conditions](#booleans-and-conditions)
- [Modules](#modules)
- [Variables](#variables)
- [Facts and templating](#facts-and-templating)
- [Idempotence and check mode](#idempotence-and-check-mode)
- [Role layout](#role-layout)
- [Lint](#lint)
- [What ansible-lint does not catch](#what-ansible-lint-does-not-catch)

## Rules

| Area | Rule |
|---|---|
| Task and handler names | Sentence case with a capital first letter and no `<file> \|` prefix (`Install nginx package`, `Restart nginx`) |
| Booleans | `true`/`false` only. Use the variable or `\| bool`, never `== true` |
| Modules | FQCN everywhere, `ansible.builtin.*` included |
| Lint | ansible-lint `production` profile with an empty `skip_list`. yamllint `truthy` with `allowed-values: ['true', 'false']` |
| Facts and templating | `ansible_facts['…']`, ansible-core 2.19-safe templating, `{{ ansible_managed \| comment }}` |
| Role layout | `defaults/main.yml`, `vars/<os_family>.yml`, `meta/main.yml`, `meta/argument_specs.yml`, `tasks/{main,assert?,install,configure,service}.yml`, `handlers/main.yml`, `molecule/default/` |

There is no `update.yml`. A separate detect step exists only for binary installs.

## Names

Every task, handler, block and play has a name. Names are sentence case, start with a
capital letter and describe the outcome. The role name is added by Ansible in the output
(`node_exporter : Install node_exporter binary`), so a file prefix only repeats context.

| Do | Don't | ansible-lint |
|---|---|---|
| `Install nginx package` | `install nginx package` | `name[casing]` |
| `Template nginx.conf` | `config \| template nginx.conf` | not flagged; this rule |
| `Restart nginx` | `restart \| nginx` | `name[casing]` |
| `Download node_exporter {{ node_exporter_version }}` | `Download {{ node_exporter_version }} archive` | `name[template]`: Jinja only at the end |
| (named) | `- ansible.builtin.debug:` with no `name:` | `name[missing]` |

Handler names are what `notify:` refers to, so keep them short and stable: `Restart
nginx`, `Reload nginx`, `Reload systemd`. Include tasks are named after what they include
(`Include install tasks`) so they never collide with task names inside the file.

## Booleans and conditions

```yaml
nginx_ssl_enabled: true          # not True, yes, on
when: nginx_ssl_enabled          # not == true, not == True
when: not nginx_ssl_enabled      # not == false
when: nginx_ssl_enabled | bool   # when the value may arrive as a string (extra vars, inventory INI)
when: nginx_extra_config | length > 0
```

- Module arguments too: `update_cache: true`, `enabled: true`, `remote_src: true`.
- `literal-compare` flags `== true` / `== false`; `yaml[truthy]` flags `True`, `yes`, `on`.
- `when:` never contains `{{ }}` (`no-jinja-when`).

## Modules

- FQCN for every action: `ansible.builtin.apt`, `ansible.builtin.template`,
  `ansible.builtin.systemd_service`, `community.docker.docker_container`
  (`fqcn[action-core]`, `fqcn[action]`).
- FQCN for lookups and filters from collections too:
  `lookup('ansible.builtin.first_found', …)`, `community.general.json_query`. No linter
  checks this; it is this rule.
- Arguments as a YAML mapping, never `key=value` free form (`no-free-form`).
- A module over `command`/`shell` whenever one exists (`command-instead-of-module`).
  A remaining `command` gets `changed_when:`; `shell` with a pipe gets `set -o pipefail`
  (`no-changed-when`, `risky-shell-pipe`).
- Files and templates set a quoted `mode` (`'0644'`) (`risky-file-permissions`,
  `risky-octal`), and an explicit `owner` and `group` (no linter checks those; it is this
  rule).
- Packages use `state: present` with a pinned version, never `state: latest`
  (`package-latest`).

## Variables

- Every variable the role defines, registers or sets starts with `<role>_`: defaults,
  vars, `register:`, `set_fact:` (`var-naming[no-role-prefix]` checks all of them).
- Lowercase with underscores (`var-naming[pattern]`); related values may be grouped in a
  dict (`nginx_paths.config`), but a flat variable is easier to override from inventory.
- `defaults/main.yml` holds everything a user may change; `vars/<os_family>.yml` holds
  values that depend on the platform (package names, paths), loaded with
  `ansible.builtin.include_vars` and the `ansible.builtin.first_found` lookup.
- `meta/argument_specs.yml` documents every variable in `defaults/main.yml` with `type`,
  `description` and the same `default`; `required: true` only for inputs without a
  default. Ansible validates role input against it before the first task runs.

## Facts and templating

- Read facts as `ansible_facts['os_family']`, `ansible_facts['architecture']`. The
  injected `ansible_os_family` form disappears when `inject_facts_as_vars` is off.
- ansible-core 2.19+ templating:
  - a `when:` must evaluate to a real boolean: `x | length > 0`, `x | bool`, never a bare
    string or list;
  - no nested `{{ }}` inside an expression; build strings with `~`;
  - a variable that may be undefined gets `| default(...)` explicitly;
  - templates are not re-templated, so do not store Jinja in data you template later.
- Every template starts with `{{ ansible_managed | comment }}`.

## Idempotence and check mode

- A second run reports `changed=0`. A task that reports `changed` on a re-run is a bug.
- Read-only probes (`--version`, `apt-cache policy`, `systemctl is-active`) get
  `changed_when: false` and `check_mode: false`, so `--check` sees real output.
- Updating is installing a newer pinned version: bump `<role>_version` and re-run. There
  is no `update.yml`.
- Binary installs are the exception that needs an explicit detect step: probe the
  installed `--version` in `install.yml` and download, unpack and install only when it
  differs. Download paths carry the version, because `get_url` does not replace an
  existing file at the same path.
- `ansible.builtin.file` with `state: touch` needs `modification_time: preserve` and
  `access_time: preserve` to stay idempotent.

## Role layout

```
roles/<role>/
├── defaults/main.yml        every variable, prefixed with the role name
├── vars/<os_family>.yml     per-platform values (Debian.yml, RedHat.yml, Windows.yml)
├── meta/main.yml            galaxy_info, platforms, dependencies
├── meta/argument_specs.yml  role argument validation
├── tasks/main.yml           include_vars, then include_tasks per stage, each tagged
├── tasks/assert.yml         optional: checks beyond argument_specs
├── tasks/install.yml        package / binary / container; version-aware
├── tasks/configure.yml      config files and directories
├── tasks/service.yml        unit file, flush handlers, started and enabled
├── handlers/main.yml
├── templates/  files/
├── molecule/default/        added by ansible:molecule-scaffolder
├── README.md
└── CHANGELOG.md
```

Stages and tags in `tasks/main.yml`: `<role>_install`, `<role>_configure`,
`<role>_service`, plus the role name on every include so `--tags <role>` runs all of it.
A role with no per-platform values may omit `vars/` and the `include_vars` task.

## Lint

- `.ansible-lint` with `profile: production` and no `skip_list` entries; or
  `ansible-lint --profile production` when the repo has no config.
- yamllint `truthy` allows only `true` and `false`. Without a `.yamllint`, ansible-lint's
  built-in yamllint pass already reports `yaml[truthy]`.
- A `# noqa: <rule>` is allowed only on the line it applies to, with the rule named, and
  only when the code cannot be written the compliant way.

Repo config for new projects:

```yaml
---
profile: production
skip_list: []
exclude_paths:
  - .cache/
  - .git/
```

## What ansible-lint does not catch

Review these by hand; the production profile passes them:

- a `<file> |` prefix on a capitalised name (`Install | download archive` passes
  `name[casing]`; `name[prefix]` is opt-in and asks for the opposite);
- a missing `meta/argument_specs.yml` (`role-argument-spec` is opt-in);
- injected facts (`ansible_os_family`) and `| default('')` used as a check-mode guard;
- a `command` probe without `check_mode: false`;
- a version-agnostic download path;
- short-form lookups (`lookup('first_found', …)`) and a missing `owner`/`group`;
- re-run idempotence: only `molecule test` proves it.
