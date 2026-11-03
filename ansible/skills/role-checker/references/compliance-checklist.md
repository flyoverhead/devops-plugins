# Compliance checklist

How to find each violation of [RULES.md](../../role-creator/references/RULES.md) in an
existing role: what to look at, a grep that finds it, the ansible-lint rule that also
reports it (if any), and whether the checker fixes it or asks. The rules themselves are
defined only in RULES.md.

Run the greps from the repository root with `R=roles/<role>`.

## Contents

1. [Structure](#structure)
2. [Names](#names)
3. [Booleans and conditions](#booleans-and-conditions)
4. [Modules](#modules)
5. [Variables](#variables)
6. [Facts and templating](#facts-and-templating)
7. [Idempotence and check mode](#idempotence-and-check-mode)
8. [Meta](#meta)
9. [Templates](#templates)
10. [README and CHANGELOG](#readme-and-changelog)
11. [Quick reference](#quick-reference)

## Structure

- [ ] `tasks/main.yml`, `tasks/install.yml`, `tasks/configure.yml`, `tasks/service.yml`,
      `handlers/main.yml`, `defaults/main.yml`, `meta/main.yml`, `meta/argument_specs.yml`,
      `README.md`, `CHANGELOG.md` exist (`ls -R $R`). A role without a service has no
      `service.yml` or handlers.
- [ ] No `tasks/detect.yml` or `tasks/update.yml`, and no `<role>_installed` /
      `<role>_update` facts — otherwise the role uses the stage-file layout: go to
      `RESTRUCTURE.md` (linked from SKILL.md).
- [ ] `tasks/config.yml` alone → rename to `configure.yml` (ask).
- [ ] `vars/` files are named after `ansible_facts['os_family']` values (`Debian.yml`,
      `RedHat.yml`, `Windows.yml`) and carry the same keys.
- [ ] `molecule/default/` exists; if not, point to `ansible:molecule-scaffolder`.
- [ ] No stray files in the role root.

## Names

- [ ] Every task, handler and block has a name (`name[missing]`).
- [ ] First letter is a capital (`name[casing]`): `grep -nE '^\s*- name:\s*["'"'"']?[a-z]' -r $R/tasks $R/handlers` — fix.
- [ ] No `<file> |` prefix (not flagged by ansible-lint): `grep -nE '^\s*- name:\s*["'"'"']?[A-Za-z_]+ \| ' -r $R/tasks $R/handlers` — fix.
- [ ] Handlers are `<Action> <service>`; every `notify:` matches a handler name or
      `listen:` — fix inside the role, ask for references outside it.
- [ ] Jinja only at the end of a name (`name[template]`) — ask.

## Booleans and conditions

- [ ] Only `true` / `false` (`yaml[truthy]`):
      `grep -nE '(:|^\s*-)\s+(True|TRUE|False|FALSE|yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)\s*(#.*)?$' -r $R`
      (values, list items, trailing comments) — fix.
- [ ] No comparison with a boolean literal (`literal-compare`):
      `grep -nE '==\s*(true|false|True|False)' -r $R` — fix (bare variable, or `not`).
- [ ] No `{{ }}` in `when:` (`no-jinja-when`) — ask.
- [ ] A `when:` evaluates to a real boolean under ansible-core 2.19 (`| length > 0`,
      `| bool`), never a bare string or list — ask.

## Modules

- [ ] FQCN on every action (`fqcn[action-core]`, `fqcn[action]`): a task key such as
      `apt:`, `copy:`, `debug:`, `systemd:`, `include_tasks:` directly under `- name:` —
      fix for `ansible.builtin`, ask for other collections.
- [ ] FQCN in lookups (not flagged): `grep -nE "lookup\('[a-z_]+'" -r $R` — fix.
- [ ] No free-form `key=value` or `command: <string>` arguments (`no-free-form`) — ask.
- [ ] `command` / `shell` only where no module exists (`command-instead-of-module`), with
      `changed_when:` (`no-changed-when`) and `set -o pipefail` on pipes
      (`risky-shell-pipe`) — ask.
- [ ] Files and templates set a quoted `mode`, `owner` and `group` (`risky-file-permissions`;
      owner and group are not flagged) — ask.
- [ ] No `state: latest` (`package-latest`) — ask.

## Variables

- [ ] Every default, var, `register:` and `set_fact:` starts with `<role>_`
      (`var-naming[no-role-prefix]`) — ask: renaming a default breaks callers.
- [ ] Every variable used in tasks and templates is defined in `defaults/`, `vars/` or by
      a `register:` / `set_fact:` — ask: adding a default changes which tasks run.
- [ ] `meta/argument_specs.yml` lists every key of `defaults/main.yml` with the same
      default and a `type` (not flagged; `role-argument-spec` is opt-in) — ask when missing.

## Facts and templating

- [ ] Facts as `ansible_facts['…']`: `grep -nE 'ansible_(os_family|distribution|architecture|hostname|default_ipv4)' -r $R` — ask.
- [ ] No nested `{{ }}` inside an expression; strings built with `~` — ask.
- [ ] Possibly undefined variables have an explicit `| default(...)` — ask.

## Idempotence and check mode

- [ ] Read-only probes (`--version`, `apt-cache policy`, `systemctl is-active`) have
      `changed_when: false` and `check_mode: false` — ask.
- [ ] Download paths include the version (`get_url` does not replace an existing file) — ask.
- [ ] `state: touch` has `modification_time: preserve` and `access_time: preserve` — ask.
- [ ] A binary install only downloads when the installed `--version` differs — ask (or
      restructure, when it uses stage-file detect facts).

## Meta

- [ ] `galaxy_info` has `role_name`, `author`, `description`, `license`,
      `min_ansible_version`, `platforms`, `galaxy_tags` (lowercase letters and digits,
      `meta-no-tags`), and `dependencies` is a list — ask.

## Templates

- [ ] Every template starts with `{{ ansible_managed | comment }}`:
      `grep -L 'ansible_managed' $R/templates/*.j2` — ask (the rendered file changes).
- [ ] Every template is used by a task and every `src:` exists.

## README and CHANGELOG

- [ ] README has purpose, requirements, a variables table that matches
      `argument_specs.yml`, an example playbook and the tags — ask.
- [ ] CHANGELOG sections are ISO dates (`## 2026-11-02`) — ask.

## Quick reference

| Issue | Fix | Who |
|---|---|---|
| `True`, `yes`, `on` | `true` / `false` | auto |
| `when: x == true`, `x` has a boolean default | `when: x` | auto |
| `when: x == true`, no boolean default | `when: x \| bool` (differs for string values) | ask |
| `install nginx` | `Install nginx` | auto |
| `config \| template nginx.conf` | `Template nginx.conf` | auto |
| `restart \| nginx` | `Restart nginx` + every `notify:` | auto |
| `apt:` / `lookup('file', …)` | `ansible.builtin.apt` / `lookup('ansible.builtin.file', …)` | auto |
| no `meta/argument_specs.yml` | generate from `defaults/main.yml` | ask |
| `ansible_os_family` | `ansible_facts['os_family']` | ask |
| no `ansible_managed` header | add `{{ ansible_managed \| comment }}` | ask |
| `detect.yml` / `update.yml` | `RESTRUCTURE.md` (linked from SKILL.md) | plan, then ask |
