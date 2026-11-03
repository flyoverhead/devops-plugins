# Restructuring a stage-file role

Many roles split their tasks into one file per stage — `detect.yml`, `install.yml`,
`update.yml`, `config.yml` — gated by `<role>_installed` / `<role>_update` facts. This
reference restructures such a stage-file role into the recommended layout in
[RULES.md](../../role-creator/references/RULES.md#role-layout). The role's public
interface does not change: every variable name and default value stays as it is.

One role per run. Five phases, in order; nothing under the role is edited before phase 3.

## Contents

- [1. Read](#1-read)
- [2. Plan, then stop](#2-plan-then-stop)
- [3. Apply](#3-apply)
- [4. Verify](#4-verify)
- [5. Report](#5-report)
- [Mapping reference](#mapping-reference)

## 1. Read

Read every file of the role and record:

- the install method (`package`, `binary`, `container`) and which tasks download, unpack,
  install, stop or start;
- every `set_fact` and `register` in `detect.yml` / `update.yml`, and where each is used:
  `grep -rnE '<role>_(installed|update)\b' .` over the whole repo, not only the role;
- every service start, stop, enable and restart task, in any file;
- every handler name and every `notify:` / `listen:` that refers to it;
- every tag on the includes in `tasks/main.yml`;
- the keys and values of `defaults/main.yml` and each `vars/*.yml`.

## 2. Plan, then stop

Print the plan before any edit. Three tables:

**Files**

| Change | From | To |
|---|---|---|
| fold | `tasks/detect.yml`, `tasks/install.yml`, `tasks/update.yml` | `tasks/install.yml`, version-aware |
| rename | `tasks/config.yml` | `tasks/configure.yml` |
| move | service start/enable tasks (name the files and lines) | `tasks/service.yml` |
| new | — | `meta/argument_specs.yml`, one option per default |
| rewrite | `tasks/main.yml` | `include_vars` + tagged `include_tasks` per stage |
| rename | handler `restart \| <svc>` | `Restart <svc>`, with every `notify:` |

**Removed facts and changed tags** — each fact the restructure drops (`<role>_installed`,
`<role>_update`, the version-output register) with every place it was used, and each tag
that changes (`<role>.install` → `<role>_install`). Say that the new `install.yml`
reinstalls whenever the installed version differs from `<role>_version`, so lowering the
variable downgrades. Facts and tags used outside the role
are interface changes; they go into the role CHANGELOG.

**Variables** — every key of `defaults/main.yml` with its default and `kept`, plus the
`vars/*.yml` keys. A variable the new tasks no longer use stays in `defaults/` and is
listed as unused. Do not add, rename or remove variables during the restructure; propose
new ones (a checksum URL, a container engine switch) in the report instead.

Then list the cosmetic fixes the apply step makes (counts per kind are enough) and the ask
items it does not make, and stop: ask the user to confirm.

If the request already confirms the restructure ("yes, apply the restructure",
"restructure it without asking"), print the plan and continue to phase 3 in the same turn. The plan still
comes before the first edit.

## 3. Apply

**Precondition:** `git status --porcelain` prints nothing. Otherwise stop, show the output
and ask the user to commit or stash first: a clean tree is what makes the restructure
reviewable with `git diff` and revertible with `git restore`. Outside a git repository,
stop and ask the user to commit the role first.

Then, using the templates in [ROLES.md](../../role-creator/references/ROLES.md):

1. **install.yml** — rewrite it from the template for the role's install method, keeping
   the role's own variables (its download URL variable, its paths, its user and group):
   - `binary`: the `--version` probe with `changed_when: false`, `check_mode: false` and
     `failed_when: false`; the `<role>_installed_version` fact; user and group; then
     download, unpack and copy only `when: <role>_installed_version != <role>_version`.
     The download path carries the version; unpack and copy skip in check mode
     (`when: not ansible_check_mode`). The `update.yml` stop-copy-start sequence
     becomes the copy task notifying `Restart <svc>`.
   - `package`: one `ansible.builtin.apt` / `ansible.builtin.dnf` task with the pinned
     version and `state: present`. Keep a `dpkg_selections` hold when the role held
     the package; the unhold/upgrade/re-hold in `update.yml` becomes unhold, install
     pinned, hold.
   - `container`: pull the pinned image; the update path is the same task with a new
     tag.
   Then `git rm tasks/detect.yml tasks/update.yml`.
2. **configure.yml** — `git mv tasks/config.yml tasks/configure.yml`; remove the service
   start/enable tasks from it.
3. **service.yml** — the systemd unit template (moved from wherever it was), a
   `meta: flush_handlers` task, and one `ansible.builtin.systemd_service` task with
   `state: started` and `enabled: true`. Carry over the start/enable conditions
   unchanged in meaning (`when: <role>_service_enabled`). For binary installs add the
   check-mode guard from ROLES.md on the start task and the restart handler:
   `not ansible_check_mode or (<role>_installed_version is defined and
   <role>_installed_version | length > 0)`. The `is defined` test covers runs whose tags
   skip `install.yml`.
4. **handlers/main.yml** — rename handlers (`Restart <svc>`) and add `listen: <old name>`
   to each renamed handler, so a `notify: restart | <svc>` outside the role keeps
   working; `ansible.builtin.systemd` → `ansible.builtin.systemd_service` (same module);
   update every `notify:` inside the role.
5. **tasks/main.yml** — the ROLES.md template: `include_vars` with the
   `ansible.builtin.first_found` lookup on `ansible_facts['os_family']` over the existing
   `vars/` files, then `include_tasks` for install, configure and service, each tagged
   `<role>` and `<role>_<stage>`. No `when:` on the includes: the facts that gated them
   are gone. Keep `assert.yml` only if the role already had platform checks.
6. **meta/argument_specs.yml** — one option per key of `defaults/main.yml`, with `type`
   (`str`, `bool`, `int`, `path`, `list` with `elements`, `dict`), the identical default
   and a one-line description (from the README table when there is one).
7. **Cosmetic fixes** — the [safe auto-fixes](../SKILL.md#safe-auto-fixes) on every file
   of the role, `defaults/` and `vars/` included (`True` → `true` keeps the value). In
   `defaults/main.yml` change formatting only where a linter requires it (a long line
   folded for `yaml[line-length]`); step 1 of [Verify](#4-verify) proves the parsed
   values are identical.
8. **README.md** — update the file list, the tags and the variables table if present.
9. **CHANGELOG.md** — a new `## <date +%F>` section: the layout change; removed facts,
   changed tags and renamed handlers, each by old and new name, with the old handler name
   kept as a deprecated `listen:` alias; that `install.yml` installs whenever the
   installed version differs from `<role>_version`, so lowering it downgrades; any removed or renamed
   variable (normally none); and that `meta/argument_specs.yml` now validates inputs, so
   a value of the wrong type fails before the first task.

The confirmed plan covers the files it lists, `meta/argument_specs.yml` and `CHANGELOG.md`
included (create the CHANGELOG when the role has none). Leave out the other
[Report, then ask](../SKILL.md#report-then-ask) items — `ansible_managed` headers, new
variables, `command` → module, `min_ansible_version` — unless the user confirmed them
too; list them in the report.

## 4. Verify

1. Defaults unchanged: compare `git show HEAD:roles/<role>/defaults/main.yml` with the
   working copy after YAML parsing, for example
   `python3 -c 'import sys, yaml; a, b = (yaml.safe_load(open(p)) for p in sys.argv[1:]); sys.exit(a != b)' <old> <new>`.
   Keys and values must be equal; quoting and `True` → `true` are not changes.
2. Removed facts: `grep -rnE '<role>_(installed|update)\b' .` finds nothing outside the
   CHANGELOG.
3. The [lint gate](../SKILL.md#lint-gate) exits 0.
4. `ansible-playbook --syntax-check` on a playbook that applies the role, when the repo
   has one.
5. `molecule test` when the role has `molecule/`; it includes the idempotence step. A
   scenario whose `converge.yml` or `verify.yml` used the removed facts or old tags is
   updated in the same run.

Do not run the role against real hosts.

## 5. Report

- The plan tables, marked done or skipped, with `path:line` for anything left.
- Each verification step: command and exit code, or why it did not run.
- **Not verified**, explicitly: idempotence when there is no `molecule/` (suggest
  `ansible:molecule-scaffolder`), platforms in `vars/` no test covered, check-mode runs,
  references to removed facts, tags or handlers in other repositories.
- Review with `git diff HEAD -- roles/<role>`; revert with
  `git restore --source=HEAD --staged --worktree roles/<role> && git clean -fd roles/<role>`
  (this also undoes the staged `git mv` and `git rm`).
- Numbered questions for the ask items.

## Mapping reference

| Stage-file layout | Recommended layout |
|---|---|
| `detect \| …` tasks, `<role>_installed`, `<role>_update` | `--version` probe and `<role>_installed_version` in `install.yml` (binary); module idempotence (package, container) |
| `when: not <role>_installed` / `when: <role>_update` on includes | no condition; `install.yml` decides by version |
| `update.yml` | removed; bump `<role>_version` and re-run |
| `config.yml` | `configure.yml` |
| start/enable in `install.yml` or `config.yml` | `service.yml` |
| `restart \| <svc>` | `Restart <svc>` |
| tags `<role>.install`, `<role>.config` | `<role>_install`, `<role>_configure`, `<role>_service`, plus `<role>` |
| `include_vars: "{{ ansible_os_family }}.yml"` | `include_vars` + `first_found` on `ansible_facts['os_family']` |
| `/tmp/<svc>.tar.gz` | `/tmp/<svc>-{{ <role>_version }}….tar.gz` |
