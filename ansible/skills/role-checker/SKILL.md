---
name: role-checker
description: Checks an existing Ansible role against the classic upstream conventions — install/configure/service layout, meta/argument_specs.yml, sentence-case names, true/false booleans, FQCN, role-prefixed variables, ansible-lint production profile — auto-fixes the cosmetic issues, reports the rest with path:line, and restructures stage-file roles (detect.yml, update.yml, config.yml, *_installed / *_update facts) into the recommended layout after a confirmed plan. Use when asked to check, review, lint, fix, modernise or restructure an Ansible role. Not for creating a role — use ansible:role-creator.
argument-hint: "[role-path]"
effort: high
paths: ["roles/**", "ansible/roles/**"]
allowed-tools: Bash(ansible-lint:*) Bash(yamllint:*) Bash(pre-commit run:*) Bash(ansible-playbook --syntax-check:*) Bash(molecule test:*) Bash(git status:*) Bash(git diff:*) Bash(git show:*) Bash(git mv:*) Bash(git rm:*) Bash(python3 -c:*) Bash(date +%F) Bash(ls:*) Read Write Edit Grep Glob
---

# Ansible role checker

Target role: $ARGUMENTS (if empty, the directory under `roles/` the user named, or the
current directory when it has `tasks/main.yml`).

Paths in the request (`roles/<role>`) are relative to the current working directory — the
user's repository — never to this skill's own directory.

The rules are in [RULES.md](../role-creator/references/RULES.md), shared with
`ansible:role-creator`; this skill does not repeat them. How to find each violation is in
[references/compliance-checklist.md](references/compliance-checklist.md).

## Checklist

Copy and track:

- [ ] 1. Inventory: list every file under the role; read `tasks/`, `handlers/`, `defaults/`, `vars/`, `meta/`, `templates/`.
- [ ] 2. Stage-file layout? Apply [Stage-file layout detection](#stage-file-layout-detection). If it matches, stop this checklist and follow [references/RESTRUCTURE.md](references/RESTRUCTURE.md): plan first, no edits before it.
- [ ] 3. Structure: the files of the [role layout](../role-creator/references/RULES.md#role-layout), `meta/argument_specs.yml` matching `defaults/main.yml`.
- [ ] 4. Names: sentence case, capital first letter, no `<file> |` prefix, on tasks and handlers.
- [ ] 5. Booleans and templates: `true`/`false` only, no `== true`; `{{ ansible_managed | comment }}` on every template.
- [ ] 6. Variables and facts: every variable prefixed `<role>_` and defined in `defaults/` or `vars/`; facts read as `ansible_facts['…']`.
- [ ] 7. Lint (see [Lint gate](#lint-gate)); run `ansible-playbook --syntax-check` on a playbook that uses the role when the repo has one.
- [ ] 8. Apply the [safe auto-fixes](#safe-auto-fixes), re-run step 7 until it exits 0 (or only reports [Report, then ask](#report-then-ask) items), then report.

Record every finding with its `path:line` as you go; the report needs them.

## Stage-file layout detection

The role uses the stage-file layout (one task file per stage, gated by detect facts) when
any of these holds:

- `tasks/detect.yml` or `tasks/update.yml` exists;
- a task sets or registers a `<role>_installed` or `<role>_update` fact
  (`grep -rnE '^\s+(\w+_(installed|update):|register:\s*\w+_(installed|update)\s*$)' roles/<role>/tasks`).

A lone `tasks/config.yml` without those is a rename finding (ask), not a restructure.

Restructuring is one role per run. When several roles match, restructure the one the user named
(or the first) and list the others in the report.

## Lint gate

Lint every file under the role, including untracked ones:

1. If the repo has `.pre-commit-config.yaml`: `pre-commit run --files <every file under roles/<role>>`.
2. Otherwise run the linters directly:
   - `ansible-lint roles/<role>` when the repo has `.ansible-lint`, else
     `ansible-lint --profile production roles/<role>`;
   - `yamllint roles/<role>` when the repo has `.yamllint`.

Fix findings in the code, never with `skip_list` or a blanket `# noqa`. If a linter is not
installed or cannot run, say so with the error and do not report the role as clean.

## Safe auto-fixes

Apply these without asking. They change how the role reads, not what it does:

- Booleans → `true` / `false`: `True`, `False`, `yes`, `no`, `on`, `off` as YAML values,
  module arguments included. Quoted strings and Jinja expressions are not booleans; leave
  them.
- `when: x == true` → `when: x`, `when: x == false` → `when: not x`, only when `x` has a
  boolean default in `defaults/main.yml`. Without one the `| bool` rewrite is an ask item
  (see below).
- Names: strip the `<file> | ` prefix (`main | read chrony version` → `Read chrony
  version`) and capitalise the first letter (`install chrony` → `Install chrony`). Do not
  reword beyond that.
- Handler names: `<action> | <service>` → `<Action> <service>` (`restart | nginx` →
  `Restart nginx`), add `listen: <old name>` to the renamed handler so a caller's
  `notify: restart | nginx` keeps working, and update every `notify:` in the role in the
  same pass. Record the alias as deprecated in the role CHANGELOG when it has one (a
  missing CHANGELOG is an ask item). Grep the rest of the repo for the old name and list
  the hits.
- FQCN: short `ansible.builtin` modules and lookups → full names (`debug` →
  `ansible.builtin.debug`, `lookup('file', …)` → `lookup('ansible.builtin.file', …)`). A
  short name from another collection is an ask item unless the repo already uses its FQCN.
- Missing `---` document start, trailing whitespace, missing final newline.

## Report, then ask

List these with a proposed fix and wait for a yes. Each changes behaviour for the role's
callers or hosts:

- Renaming or removing a variable in `defaults/` (callers set it in inventory).
- Adding a default for an undefined variable (it changes which tasks run).
- Adding `{{ ansible_managed | comment }}` to a template: the rendered file changes and
  every host restarts the service once.
- Replacing injected facts (`ansible_os_family`) with `ansible_facts['…']`, `command` or
  `shell` with a module, free-form arguments with a mapping, or any `when:` logic.
- Creating missing files (`meta/argument_specs.yml`, `README.md`, `CHANGELOG.md`).
- Raising `min_ansible_version`.
- `when: x == true` → `when: x | bool` (and `== false` → `when: not (x | bool)`) when `x`
  has no boolean default. Under ansible-core 2.19 a `when:` that evaluates to a string
  such as `"yes"` fails instead of being truthy, and `| bool` makes the same string true,
  so the rewrite changes results for string values.
- Every other ansible-lint finding that is not a safe auto-fix.

## Example

```yaml
# before — roles/chrony/tasks/main.yml:2
- name: main | install chrony
  apt:
    name: chrony
    update_cache: True
  when: chrony_enabled == true
# after (safe fixes)
- name: Install chrony
  ansible.builtin.apt:
    name: chrony
    update_cache: true
  when: chrony_enabled
```

The example assumes `chrony_enabled: true` in `defaults/main.yml`. Without that default
the `when:` is left as it is and reported as an ask item, together with the missing
default: both change whether the task runs.

## Report format

One line per finding, safe fixes first. Every line starts with `path:line`, with no
exceptions. A missing file or a role-wide gap goes at the line that needs it, or at `:1`
of the file that is incomplete; name the missing file in the rule text:

```
roles/chrony/tasks/main.yml:2 — name has a `main |` prefix — renamed to `Install chrony` (fixed)
roles/chrony/tasks/main.yml:6 — boolean compared with `== true` — `when: chrony_enabled` (fixed; `chrony_enabled` has a boolean default)
roles/chrony/tasks/main.yml:9 — `when: chrony_extra == true` on a variable with no boolean default — `when: chrony_extra | bool`? (ask; differs for string values such as "yes")
roles/chrony/tasks/main.yml:6 — `chrony_enabled` is not defined in defaults/main.yml — add `chrony_enabled: true`? (ask)
roles/chrony/meta/main.yml:1 — no meta/argument_specs.yml — generate it from defaults/main.yml? (ask)
```

End with the lint result (command and exit code, or why it did not run), the modified
files, and numbered questions for the ask items.

## References

- [../role-creator/references/RULES.md](../role-creator/references/RULES.md) — the rules,
  including what ansible-lint does not catch.
- [references/compliance-checklist.md](references/compliance-checklist.md) — how to find
  each violation, with grep commands and the matching ansible-lint rule.
- [references/RESTRUCTURE.md](references/RESTRUCTURE.md) — stage-file layout restructure: plan,
  precondition, apply, verify, report.
- [../role-creator/references/ROLES.md](../role-creator/references/ROLES.md) — templates
  for the target layout; `ansible:role-creator` generates missing components once the
  user agrees.
